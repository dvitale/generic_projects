package main

import (
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/ssh"
)

// An actual SSH server on loopback exercises encryption, authentication and exec.
func testSSH(t *testing.T) (*Remote, *atomic.Int32) {
	t.Helper()
	_, key, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	signer, err := ssh.NewSignerFromKey(key)
	if err != nil {
		t.Fatal(err)
	}
	authCalls := &atomic.Int32{}
	config := &ssh.ServerConfig{PasswordCallback: func(c ssh.ConnMetadata, password []byte) (*ssh.Permissions, error) {
		authCalls.Add(1)
		if c.User() != "tester" || string(password) != "test-only-password" {
			return nil, errors.New("bad credentials")
		}
		return nil, nil
	}}
	config.AddHostKey(signer)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	var connections sync.WaitGroup
	done := make(chan struct{})
	go func() {
		defer close(done)
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			connections.Add(1)
			go func() {
				defer connections.Done()
				defer conn.Close()
				conn.SetDeadline(time.Now().Add(10 * time.Second))
				server, chans, reqs, err := ssh.NewServerConn(conn, config)
				if err != nil {
					return
				}
				defer server.Close()
				go ssh.DiscardRequests(reqs)
				for incoming := range chans {
					if incoming.ChannelType() != "session" {
						incoming.Reject(ssh.UnknownChannelType, "session only")
						continue
					}
					channel, requests, err := incoming.Accept()
					if err != nil {
						continue
					}
					for request := range requests {
						if request.Type != "exec" {
							request.Reply(false, nil)
							continue
						}
						var payload struct{ Command string }
						if ssh.Unmarshal(request.Payload, &payload) != nil {
							request.Reply(false, nil)
							break
						}
						request.Reply(true, nil)
						cmd := exec.Command("sh", "-c", payload.Command)
						cmd.Stdin = channel
						cmd.Stdout = channel
						cmd.Stderr = channel.Stderr()
						code := uint32(0)
						if cmd.Run() != nil {
							code = 1
						}
						channel.SendRequest("exit-status", false, ssh.Marshal(struct{ Code uint32 }{code}))
						break
					}
					channel.Close()
				}
			}()
		}
	}()
	t.Cleanup(func() { listener.Close(); <-done; connections.Wait() })
	return &Remote{id: "test", host: "127.0.0.1", port: listener.Addr().(*net.TCPAddr).Port, user: "tester", password: "test-only-password", fingerprint: ssh.FingerprintSHA256(signer.PublicKey()), hostKeyType: ssh.KeyAlgoED25519, live: true}, authCalls
}
func TestRemoteEnvironment(t *testing.T) {
	env := map[string]string{
		"PROXYMAN_REMOTE_IDS":     "prod backup",
		"PROXYMAN_REMOTE_PROD_IP": "192.0.2.10", "PROXYMAN_REMOTE_PROD_USER": "root", "PROXYMAN_REMOTE_PROD_PASSWORD": "secret",
		"PROXYMAN_REMOTE_PROD_HOST_KEY": "SHA256:" + strings.Repeat("A", 43),
		"PROXYMAN_REMOTE_BACKUP_IP":     "2001:db8::1", "PROXYMAN_REMOTE_BACKUP_USER": "ops", "PROXYMAN_REMOTE_BACKUP_PASSWORD": "secret2",
		"PROXYMAN_REMOTE_BACKUP_HOST_KEY": "SHA256:" + strings.Repeat("A", 43),
		"PROXYMAN_REMOTE_BACKUP_PORT":     "2222", "PROXYMAN_REMOTE_BACKUP_SUDO": "1",
	}
	get := func(key string) string { return env[key] }
	remotes, err := loadRemotes(get)
	if err != nil {
		t.Fatal(err)
	}
	if len(remotes) != 2 || remotes[1].port != 2222 || !remotes[1].sudo {
		t.Fatal("environment not loaded")
	}
	for _, tc := range []struct{ key, value string }{
		{"PROXYMAN_REMOTE_IDS", "local"}, {"PROXYMAN_REMOTE_IDS", "prod prod"}, {"PROXYMAN_REMOTE_IDS", "../escape"},
		{"PROXYMAN_REMOTE_PROD_PORT", "70000"}, {"PROXYMAN_REMOTE_PROD_PASSWORD", ""},
		{"PROXYMAN_REMOTE_PROD_HOST_KEY", "SHA256:invalid"}, {"PROXYMAN_REMOTE_PROD_HOST_KEY_TYPE", "ssh-rsa"},
		{"PROXYMAN_REMOTE_PROD_CONFIG", "/tmp/a;touch /tmp/injected"}, {"PROXYMAN_REMOTE_PROD_SUDO", "yes"},
	} {
		old, exists := env[tc.key]
		env[tc.key] = tc.value
		if _, err := loadRemotes(get); err == nil {
			t.Errorf("accepted invalid %s", tc.key)
		}
		if exists {
			env[tc.key] = old
		} else {
			delete(env, tc.key)
		}
	}
}
func TestSSHIdentityBeforePassword(t *testing.T) {
	r, auth := testSSH(t)
	r.fingerprint = "SHA256:" + strings.Repeat("A", 43)
	if err := r.run(context.Background(), "true", ""); err == nil || !strings.Contains(err.Error(), "HOST_KEY") {
		t.Fatalf("host identity not rejected: %v", err)
	}
	if auth.Load() != 0 {
		t.Fatal("password sent before host identity verified")
	}
}
func TestSSHWrongPassword(t *testing.T) {
	r, _ := testSSH(t)
	r.password = "wrong-secret-password"
	err := r.run(context.Background(), "true", "")
	if err == nil {
		t.Fatal("wrong password accepted")
	}
	if strings.Contains(err.Error(), r.password) {
		t.Fatal("password exposed")
	}
}
func TestSSHRemoteApply(t *testing.T) {
	for _, mode := range []string{"ok", "test-fail", "reload-fail", "not-included", "unmanaged", "new-file-fail"} {
		t.Run(mode, func(t *testing.T) {
			r, _ := testSSH(t)
			dir := t.TempDir()
			r.config = filepath.Join(dir, "proxyman.conf")
			r.nginx = filepath.Join(dir, "nginx")
			old := "# Gestito da Proxyman.\n# previous configuration\n"
			if mode == "unmanaged" {
				old = "# user configuration\n"
			}
			if mode != "new-file-fail" {
				if err := os.WriteFile(r.config, []byte(old), 0644); err != nil {
					t.Fatal(err)
				}
			}
			dump := "# configuration file " + r.config + ":"
			if mode == "not-included" {
				dump = "# some other configuration"
			}
			testCode := "0"
			if mode == "test-fail" || mode == "new-file-fail" {
				testCode = "1"
			}
			reload := "exit 0"
			if mode == "reload-fail" {
				reload = "if [ ! -e " + shellQuote(filepath.Join(dir, "attempt")) + " ]; then touch " + shellQuote(filepath.Join(dir, "attempt")) + "; exit 1; fi\nexit 0"
			}
			script := "#!/bin/sh\ncase \"$1\" in\n-T) printf '%s\\n' " + shellQuote(dump) + "; exit " + testCode + ";;\n-t) exit 0;;\n-s) " + reload + ";;\nesac\n"
			if err := os.WriteFile(r.nginx, []byte(script), 0755); err != nil {
				t.Fatal(err)
			}
			next := render([]Host{example()})
			err := r.apply(context.Background(), next)
			now, readErr := os.ReadFile(r.config)
			if mode == "ok" {
				if err != nil {
					t.Fatal(err)
				}
				if string(now) != next {
					t.Fatal("wrong config")
				}
				if err = r.check(context.Background()); err != nil {
					t.Fatal(err)
				}
			} else {
				if err == nil {
					t.Fatal("failure ignored")
				}
				if mode == "new-file-fail" {
					if !os.IsNotExist(readErr) {
						t.Fatal("new file not removed")
					}
				} else if string(now) != old {
					t.Fatal("original not restored")
				}
			}
			leftovers, _ := filepath.Glob(filepath.Join(dir, ".proxyman-*"))
			if len(leftovers) != 0 {
				t.Fatal("temporary files left behind")
			}
		})
	}
}
func TestServersIsolationAndSecrets(t *testing.T) {
	dir := t.TempDir()
	local := &App{data: filepath.Join(dir, "hosts.json"), state: State{Hosts: []Host{}}}
	remote := &Remote{id: "prod", host: "192.0.2.1", port: 22, user: "secret-user", password: "secret-password", fingerprint: "secret-fingerprint"}
	servers, err := newServers(local, []*Remote{remote})
	if err != nil {
		t.Fatal(err)
	}
	w := httptest.NewRecorder()
	servers.ServeHTTP(w, httptest.NewRequest("GET", "/api/servers", nil))
	for _, secret := range []string{remote.user, remote.password, remote.fingerprint} {
		if strings.Contains(w.Body.String(), secret) {
			t.Fatal("secret leaked")
		}
	}
	payload, _ := json.Marshal(State{Hosts: []Host{example()}})
	r := httptest.NewRequest("POST", "/api/hosts?server=prod", strings.NewReader(string(payload)))
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("X-Proxyman", "1")
	w = httptest.NewRecorder()
	servers.ServeHTTP(w, r)
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	if len(local.state.Hosts) != 0 || local.state.Revision != 0 {
		t.Fatal("remote change affected local")
	}
	if _, err = os.Stat(filepath.Join(dir, "remote-prod.json")); err != nil {
		t.Fatal(err)
	}
	restored, err := newServers(local, []*Remote{remote})
	if err != nil {
		t.Fatal(err)
	}
	if restored.apps["prod"].state.Revision != 1 || len(restored.apps["prod"].state.Hosts) != 1 {
		t.Fatal("remote state not persisted")
	}
	w = httptest.NewRecorder()
	servers.ServeHTTP(w, httptest.NewRequest("GET", "/api/hosts?server=missing", nil))
	if w.Code != 404 {
		t.Fatal("unknown target accepted")
	}
}
func TestSSHDeadline(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	done := make(chan struct{})
	go func() {
		defer close(done)
		c, err := listener.Accept()
		if err == nil {
			defer c.Close()
			buf := make([]byte, 256)
			for {
				if _, err = c.Read(buf); err != nil {
					return
				}
			}
		}
	}()
	r := &Remote{id: "stalled", host: "127.0.0.1", port: listener.Addr().(*net.TCPAddr).Port}
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	start := time.Now()
	if r.run(ctx, "true", "") == nil {
		t.Fatal("stalled SSH accepted")
	}
	if time.Since(start) > 2*time.Second {
		t.Fatal("SSH timeout ignored")
	}
	<-done
}
func TestRemoteGeneratedConfigWithNginx(t *testing.T) {
	nginx, err := exec.LookPath("nginx")
	if err != nil {
		t.Skip("nginx unavailable")
	}
	dir := t.TempDir()
	// Use a high port to make the test independent of the installed service.
	h := example()
	generated := strings.ReplaceAll(render([]Host{h}), "listen 80;", "listen 18080;")
	conf := filepath.Join(dir, "generated.conf")
	if err = os.WriteFile(conf, []byte(generated), 0600); err != nil {
		t.Fatal(err)
	}
	main := filepath.Join(dir, "nginx.conf")
	text := fmt.Sprintf("pid %s;\nerror_log stderr;\nevents {}\nhttp { access_log off; include %s; }\n", filepath.Join(dir, "nginx.pid"), conf)
	os.WriteFile(main, []byte(text), 0600)
	output, err := exec.Command(nginx, "-t", "-p", dir+"/", "-c", main, "-e", "stderr").CombinedOutput()
	if err != nil {
		t.Fatalf("nginx validation: %v\n%s", err, output)
	}
}
func TestShellQuote(t *testing.T) {
	value := "a' b;$(echo unsafe)\nnext"
	output, err := exec.Command("sh", "-c", "printf %s "+shellQuote(value)).Output()
	if err != nil || string(output) != value {
		t.Fatal("shell argument changed", err)
	}
}
