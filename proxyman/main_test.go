package main

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func example() Host {
	return Host{Domain: "app.example.it", Target: "127.0.0.1", Port: 3000, Scheme: "http", Enabled: true}
}
func TestValidation(t *testing.T) {
	good := example()
	if err := validate([]Host{good}); err != nil {
		t.Fatal(err)
	}
	for _, s := range []string{"a; include /tmp/x;", "a\nb", "*.example.it", "a/b"} {
		h := good
		h.Domain = s
		if validate([]Host{h}) == nil {
			t.Fatalf("accepted %q", s)
		}
	}
	h := good
	h.Domain = "APP.EXAMPLE.IT"
	if validate([]Host{good, h}) == nil {
		t.Fatal("duplicate accepted")
	}
	h = good
	h.Certificate = "/tmp/a.pem"
	if validate([]Host{h}) == nil {
		t.Fatal("missing key accepted")
	}
}
func TestRender(t *testing.T) {
	h := example()
	h.Target = "::1"
	h.Websocket = true
	h.Certificate = "/tmp/cert.pem"
	h.Key = "/tmp/key.pem"
	output := render([]Host{h})
	for _, text := range []string{"proxy_pass http://[::1]:3000;", "listen 443 ssl;", "return 301 https://$host$request_uri;", "proxy_set_header Upgrade"} {
		if !strings.Contains(output, text) {
			t.Fatal(text)
		}
	}
	h.Enabled = false
	if strings.Contains(render([]Host{h}), "server {") {
		t.Fatal("disabled host rendered")
	}
}
func TestApplyRollback(t *testing.T) {
	for _, mode := range []string{"test-fail", "reload-fail", "ok"} {
		t.Run(mode, func(t *testing.T) {
			dir := t.TempDir()
			conf := filepath.Join(dir, "proxyman.conf")
			binary := filepath.Join(dir, "nginx")
			old := "# Gestito da Proxyman.\n# previous\n"
			os.WriteFile(conf, []byte(old), 0644)
			script := "#!/bin/sh\nexit 0\n"
			if mode == "test-fail" {
				script = "#!/bin/sh\nexit 1\n"
			}
			if mode == "reload-fail" {
				script = "#!/bin/sh\n[ \"$1\" = -t ] && exit 0\nexit 1\n"
			}
			os.WriteFile(binary, []byte(script), 0700)
			a := App{config: conf, nginx: binary, live: true, state: State{Hosts: []Host{example()}}}
			err := a.apply()
			now, _ := os.ReadFile(conf)
			if mode == "ok" {
				if err != nil {
					t.Fatal(err)
				}
				if string(now) != render(a.state.Hosts) {
					t.Fatal("not applied")
				}
			} else {
				if err == nil {
					t.Fatal("failure ignored")
				}
				if string(now) != old {
					t.Fatal("rollback failed")
				}
			}
		})
	}
}
func TestRefuseUnmanaged(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "existing.conf")
	os.WriteFile(path, []byte("# user configuration"), 0644)
	a := App{config: path, live: true}
	if a.apply() == nil {
		t.Fatal("unmanaged config overwritten")
	}
}
func TestAuthAndRevision(t *testing.T) {
	a := App{data: filepath.Join(t.TempDir(), "hosts.json"), state: State{Hosts: []Host{}, Revision: 2}}
	handler := secure(http.HandlerFunc(a.api), "admin", "test-password-123")
	r := httptest.NewRequest("GET", "/api/hosts", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	if w.Code != 401 {
		t.Fatal(w.Code)
	}
	r = httptest.NewRequest("POST", "/api/hosts", strings.NewReader(`{"hosts":[],"revision":1}`))
	r.SetBasicAuth("admin", "test-password-123")
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("X-Proxyman", "1")
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	if w.Code != 409 {
		t.Fatal(w.Code)
	}
	r = httptest.NewRequest("POST", "/api/hosts", strings.NewReader(`{"hosts":[],"revision":2}`))
	r.SetBasicAuth("admin", "test-password-123")
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	if w.Code != 403 {
		t.Fatal(w.Code)
	}
	r = httptest.NewRequest("POST", "/api/hosts", strings.NewReader(`{"hosts":[],"revision":2}`))
	r.SetBasicAuth("admin", "test-password-123")
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("X-Proxyman", "1")
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, r)
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	if _, err := os.Stat(a.data); errors.Is(err, os.ErrNotExist) {
		t.Fatal(err)
	}
}
