package main

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const existingFixture = `# Keep this exact comment
server {
    listen 443 ssl; # public TLS
    server_name before.example;
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;
    # Unknown settings must survive byte for byte.
    add_header X-Custom "a value";
    proxy_read_timeout 120s;
    location / {
        proxy_pass http://127.0.0.1:3100/;
        proxy_set_header X-Secret "not-returned-in-form";
    }
    location = /redirect { return 301 /redirect/; }
    location /api/ {
        proxy_pass http://127.0.0.1:8090/;
        proxy_set_header Connection "upgrade";
    }
}
server { listen 81; server_name untouched.example; return 404; }
`

func fieldID(t *testing.T, m EditModel, name, section string) string {
	t.Helper()
	for _, f := range m.Fields {
		if f.directive == name && (section == "" || f.Section == section) {
			return f.ID
		}
	}
	t.Fatalf("field %s/%s missing", name, section)
	return ""
}
func TestGuidedNoopAndPreservation(t *testing.T) {
	m, err := makeEditModel("/etc/nginx/sites-enabled/example.conf", 2, existingFixture)
	if err != nil {
		t.Fatal(err)
	}
	req := EditRequest{Version: m.Version, Values: map[string]string{}}
	for _, f := range m.Fields {
		req.Values[f.ID] = f.Value
	}
	next, preview, err := prepareEdit(m, req)
	if err != nil || next != existingFixture || len(preview.Changes) != 0 {
		t.Fatal("no-op changed source", err)
	}
	req.Values[fieldID(t, m, "server_name", "")] = "after.example alias.example"
	req.Values[fieldID(t, m, "proxy_pass", "Percorso /api/")] = "http://127.0.0.1:9090/api/"
	req.Values[fieldID(t, m, "proxy_connect_timeout", "Percorso /")] = "45s"
	req.Routes = []AddedRoute{{Location: "/new/", Destination: "http://127.0.0.1:8081/", Websocket: true}}
	next, preview, err = prepareEdit(m, req)
	if err != nil {
		t.Fatal(err)
	}
	for _, keep := range []string{
		"# Keep this exact comment", "listen 443 ssl; # public TLS",
		`add_header X-Custom "a value";`,
		`proxy_set_header X-Secret "not-returned-in-form";`,
		"location = /redirect { return 301 /redirect/; }",
		"server { listen 81; server_name untouched.example; return 404; }",
	} {
		if !strings.Contains(next, keep) {
			t.Fatalf("lost %q", keep)
		}
	}
	if !strings.Contains(next, "proxy_pass http://127.0.0.1:9090/api/;") || !strings.Contains(next, "proxy_connect_timeout 45s;") || !strings.Contains(next, "location /new/") {
		t.Fatal(next)
	}
	if len(preview.Changes) != 4 || preview.Hash != digest(next) {
		t.Fatal(preview)
	}
	encoded, _ := json.Marshal(m)
	if strings.Contains(string(encoded), "not-returned-in-form") {
		t.Fatal("unrelated secret exposed in form")
	}
}
func TestGuidedRejectsInjectionAndConflicts(t *testing.T) {
	m, err := makeEditModel("/tmp/test.conf", 2, existingFixture)
	if err != nil {
		t.Fatal(err)
	}
	for _, change := range []struct{ name, section, value string }{
		{"server_name", "", "bad; include /tmp/x"},
		{"listen", "", "80; }"},
		{"proxy_pass", "Percorso /", "http://user:secret@example.com"},
		{"proxy_pass", "Percorso /", "file:///tmp/secret"},
		{"ssl_certificate", "", "/tmp/a\ninclude /tmp/b"},
		{"proxy_read_timeout", "Impostazioni del server", "anything"},
	} {
		req := EditRequest{Version: m.Version, Values: map[string]string{fieldID(t, m, change.name, change.section): change.value}}
		if _, _, err = prepareEdit(m, req); err == nil {
			t.Fatalf("accepted %s", change.name)
		}
	}
	if _, _, err = prepareEdit(m, EditRequest{Version: "old"}); err == nil {
		t.Fatal("stale accepted")
	}
	if _, _, err = prepareEdit(m, EditRequest{Version: m.Version, Values: map[string]string{"bogus": "value"}}); err == nil {
		t.Fatal("unknown field accepted")
	}
}
func TestGuidedSymlinkBackupRollbackAndConflict(t *testing.T) {
	for _, mode := range []string{"ok", "test-fail", "reload-fail", "conflict"} {
		t.Run(mode, func(t *testing.T) {
			r, _ := testSSH(t)
			dir := t.TempDir()
			target := filepath.Join(dir, "original.conf")
			link := filepath.Join(dir, "enabled.conf")
			nginx := filepath.Join(dir, "nginx")
			if err := os.WriteFile(target, []byte(existingFixture), 0640); err != nil {
				t.Fatal(err)
			}
			os.Symlink(target, link)
			script := "#!/bin/sh\nexit 0\n"
			if mode == "test-fail" {
				script = "#!/bin/sh\nexit 1\n"
			}
			if mode == "reload-fail" {
				script = "#!/bin/sh\nif [ \"$1\" = -s ] && [ ! -e " + shellQuote(filepath.Join(dir, "failed")) + " ]; then touch " + shellQuote(filepath.Join(dir, "failed")) + "; exit 1; fi\nexit 0\n"
			}
			os.WriteFile(nginx, []byte(script), 0700)
			r.nginx = nginx
			a := &App{remote: r, nginx: nginx}
			m, err := makeEditModel(link, 2, existingFixture)
			if err != nil {
				t.Fatal(err)
			}
			m.resolved = target
			original := existingFixture
			if mode == "conflict" {
				original += "# external change\n"
				os.WriteFile(target, []byte(original), 0640)
			}
			next := strings.Replace(existingFixture, "before.example", "after.example", 1)
			backup, err := a.applyExisting(context.Background(), m, next)
			data, _ := os.ReadFile(target)
			info, _ := os.Lstat(link)
			if info.Mode()&os.ModeSymlink == 0 {
				t.Fatal("symlink replaced")
			}
			stat, _ := os.Stat(target)
			if stat.Mode().Perm() != 0640 {
				t.Fatal("permissions changed")
			}
			if mode == "ok" {
				if err != nil {
					t.Fatal(err)
				}
				if string(data) != next {
					t.Fatal("not applied")
				}
				saved, e := os.ReadFile(backup)
				if e != nil || string(saved) != existingFixture {
					t.Fatal("backup not preserved", e)
				}
			} else {
				if err == nil {
					t.Fatal("failure ignored")
				}
				if string(data) != original {
					t.Fatal("original not restored")
				}
			}
		})
	}
}
func TestGuidedAPIWorkflow(t *testing.T) {
	r, _ := testSSH(t)
	dir := t.TempDir()
	file := filepath.Join(dir, "original.conf")
	r.nginx = filepath.Join(dir, "nginx")
	source := "server { listen 8080; server_name example.test; location / { proxy_pass http://127.0.0.1:3000; } }\n"
	os.WriteFile(file, []byte(source), 0644)
	script := "#!/bin/sh\nif [ \"$1\" = -T ]; then printf '%s\\n' " + shellQuote("# configuration file "+file+":") + "; cat " + shellQuote(file) + "; fi\nexit 0\n"
	os.WriteFile(r.nginx, []byte(script), 0700)
	app := &App{remote: r, live: true, config: filepath.Join(dir, "managed.conf")}
	call := func(endpoint string, body any, headers bool) *httptest.ResponseRecorder {
		data, _ := json.Marshal(body)
		request := httptest.NewRequest("POST", endpoint, strings.NewReader(string(data)))
		if headers {
			request.Header.Set("Content-Type", "application/json")
			request.Header.Set("X-Proxyman", "1")
		}
		w := httptest.NewRecorder()
		app.existingAPI(w, request)
		return w
	}
	if w := call("/api/existing/open", EditRequest{File: file, Line: 1}, false); w.Code != 403 {
		t.Fatal(w.Code)
	}
	if w := call("/api/existing/open", EditRequest{File: "/etc/passwd", Line: 1}, true); w.Code != 400 {
		t.Fatal("arbitrary file allowed")
	}
	w := call("/api/existing/open", EditRequest{File: file, Line: 1}, true)
	if w.Code != 200 {
		t.Fatal(w.Body.String())
	}
	var model EditModel
	json.Unmarshal(w.Body.Bytes(), &model)
	req := EditRequest{File: file, Line: 1, Version: model.Version, Values: map[string]string{}}
	for _, field := range model.Fields {
		if field.Kind == "destination" {
			req.Values[field.ID] = "http://127.0.0.1:4000"
		}
	}
	w = call("/api/existing/preview", req, true)
	if w.Code != 200 {
		t.Fatal(w.Body.String())
	}
	var preview EditPreview
	json.Unmarshal(w.Body.Bytes(), &preview)
	now, _ := os.ReadFile(file)
	if string(now) != source {
		t.Fatal("preview modified file")
	}
	req.Preview = "invalid"
	if w = call("/api/existing/apply", req, true); w.Code != 409 {
		t.Fatal("unreviewed edit accepted", w.Code)
	}
	req.Preview = preview.Hash
	app.live = false
	if w = call("/api/existing/apply", req, true); w.Code != 403 {
		t.Fatal("disabled apply accepted")
	}
	app.live = true
	w = call("/api/existing/apply", req, true)
	if w.Code != 200 {
		t.Fatal(w.Body.String())
	}
	now, _ = os.ReadFile(file)
	if !strings.Contains(string(now), ":4000") {
		t.Fatal("not applied")
	}
	w = call("/api/existing/apply", req, true)
	if w.Code != 409 {
		t.Fatal("stale request accepted", w.Code)
	}
}
func TestGuidedActualNginxReload(t *testing.T) {
	nginx, err := exec.LookPath("nginx")
	if err != nil {
		t.Skip("nginx unavailable")
	}
	dir := t.TempDir()
	before := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "before") }))
	defer before.Close()
	after := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "after") }))
	defer after.Close()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	address := listener.Addr().String()
	listener.Close()
	file := filepath.Join(dir, "proxy.conf")
	source := "server { listen " + address + "; server_name example.test; location / { proxy_pass " + before.URL + "; } }\n"
	os.WriteFile(file, []byte(source), 0644)
	main := filepath.Join(dir, "nginx.conf")
	os.WriteFile(main, []byte("pid "+filepath.Join(dir, "nginx.pid")+";\nerror_log "+filepath.Join(dir, "error.log")+";\nevents {}\nhttp { access_log off; include "+file+"; }\n"), 0600)
	wrapper := filepath.Join(dir, "nginx")
	os.WriteFile(wrapper, []byte("#!/bin/sh\nexec "+shellQuote(nginx)+" -p "+shellQuote(dir+"/")+" -c "+shellQuote(main)+" -e "+shellQuote(filepath.Join(dir, "error.log"))+" \"$@\"\n"), 0700)
	log, _ := os.Create(filepath.Join(dir, "startup.log"))
	defer log.Close()
	command := exec.Command(wrapper)
	command.Stdout = log
	command.Stderr = log
	if err = command.Run(); err != nil {
		t.Fatal("nginx start", err)
	}
	defer exec.Command(wrapper, "-s", "quit").Run()
	client := &http.Client{Timeout: time.Second, Transport: &http.Transport{DisableKeepAlives: true}}
	body := func() string {
		res, e := client.Get("http://" + address)
		if e != nil {
			return ""
		}
		defer res.Body.Close()
		data, _ := io.ReadAll(res.Body)
		return string(data)
	}
	deadline := time.Now().Add(2 * time.Second)
	for body() != "before" && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	if body() != "before" {
		t.Fatal("initial proxy unavailable")
	}
	m, err := makeEditModel(file, 1, source)
	if err != nil {
		t.Fatal(err)
	}
	m.resolved = file
	req := EditRequest{Version: m.Version, Values: map[string]string{fieldID(t, m, "proxy_pass", "Percorso /"): after.URL}}
	next, _, err := prepareEdit(m, req)
	if err != nil {
		t.Fatal(err)
	}
	app := &App{nginx: wrapper}
	if _, err = app.applyExisting(context.Background(), m, next); err != nil {
		t.Fatal(err)
	}
	deadline = time.Now().Add(3 * time.Second)
	for body() != "after" && time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
	}
	if body() != "after" {
		t.Fatal("reloaded proxy not serving new backend")
	}
	m, err = makeEditModel(file, 1, next)
	if err != nil {
		t.Fatal(err)
	}
	m.resolved = file
	invalid := strings.Replace(next, "listen "+address, "listen "+address+" ssl", 1)
	if _, err = app.applyExisting(context.Background(), m, invalid); err == nil {
		t.Fatal("nginx accepted missing TLS certificate")
	}
	now, _ := os.ReadFile(file)
	if string(now) != next || body() != "after" {
		t.Fatal("failed candidate disrupted working proxy")
	}
}
