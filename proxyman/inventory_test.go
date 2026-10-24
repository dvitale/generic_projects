package main

import (
	"context"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestInventoryIncludesUpstreamsAndTLS(t *testing.T) {
	dump := `# configuration file /etc/nginx/nginx.conf:
events {}
http {
 include mime.types;
 include /etc/nginx/conf.d/*.conf;
}
# configuration file /etc/nginx/mime.types:
types { text/html html; }
# configuration file /etc/nginx/conf.d/backends.conf:
upstream app_pool { server 127.0.0.1:3000; server 127.0.0.2:3000 backup; }
# configuration file /etc/nginx/conf.d/site.conf:
server {
 listen 443 ssl;
 server_name app.example.test alias.example.test;
 include snippets/proxy.conf;
 location /api { proxy_pass "http://app_pool/api"; }
}
server { listen 80; server_name app.example.test; return 301 https://$host$request_uri; }
# configuration file /etc/nginx/snippets/proxy.conf:
location / {
 proxy_set_header Authorization "secret value";
 proxy_pass http://127.0.0.1:8080;
}
`
	result, err := parseInventory(dump, "/etc/nginx/conf.d/proxyman.conf")
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Proxies) != 1 {
		t.Fatalf("%+v", result)
	}
	p := result.Proxies[0]
	if !p.TLS || p.Managed || len(p.Domains) != 2 || len(p.Routes) != 2 || p.File != "/etc/nginx/conf.d/site.conf" || p.Line != 1 {
		t.Fatalf("%+v", p)
	}
	if len(p.Routes[1].Backends) != 2 {
		t.Fatalf("%+v", p.Routes)
	}
	if len(result.Warnings) != 0 {
		t.Fatal(result.Warnings)
	}
}
func TestInventoryQuotesVariablesCommentsAndManaged(t *testing.T) {
	dump := `# configuration file /etc/nginx/nginx.conf:
http {
 # server { proxy_pass http://fake; }
 server {
 server_name quoted.example;
 listen 8443 ssl;
 location "~ ^/a{1,3}$" { proxy_pass http://${backend}:3000; }
 location /private { proxy_pass http://user:password@example.test; }
 set $value "a } ; # string";
 }
}
`
	result, err := parseInventory(dump, "/etc/nginx/nginx.conf")
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Proxies) != 1 || !result.Proxies[0].Managed {
		t.Fatalf("%+v", result)
	}
	routes := result.Proxies[0].Routes
	if routes[0].Destination != "http://${backend}:3000" {
		t.Fatal(routes)
	}
	if strings.Contains(routes[1].Destination, "password") {
		t.Fatal("URL secret exposed")
	}
}
func TestInventoryMalformedAndEmpty(t *testing.T) {
	for _, dump := range []string{"", "# configuration file /etc/nginx/nginx.conf:\nhttp {", "# configuration file /etc/nginx/nginx.conf:\nhttp { set x \"unterminated; }"} {
		if _, err := parseInventory(dump, ""); err == nil {
			t.Fatal("malformed dump accepted")
		}
	}
	result, err := parseInventory("# configuration file /etc/nginx/nginx.conf:\nhttp { server { return 404; } }", "")
	if err != nil || len(result.Proxies) != 0 {
		t.Fatal(result, err)
	}
}
func TestInventorySSHReadOnly(t *testing.T) {
	remote, _ := testSSH(t)
	dir := t.TempDir()
	remote.config = filepath.Join(dir, "managed.conf")
	remote.nginx = filepath.Join(dir, "nginx")
	original := "existing file untouched"
	os.WriteFile(remote.config, []byte(original), 0600)
	dump := "# configuration file /etc/nginx/nginx.conf:\nhttp { server { server_name real.example; location / { proxy_pass http://127.0.0.1:3000; } } }\n"
	script := "#!/bin/sh\n[ \"$1\" = -T ] || exit 1\nprintf %s " + shellQuote(dump) + "\n"
	os.WriteFile(remote.nginx, []byte(script), 0700)
	app := &App{remote: remote, config: remote.config}
	result, err := app.inventory(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Proxies) != 1 || result.Proxies[0].Domains[0] != "real.example" {
		t.Fatalf("%+v", result)
	}
	now, _ := os.ReadFile(remote.config)
	if string(now) != original {
		t.Fatal("remote file modified")
	}
	r := httptest.NewRequest("POST", "/api/inventory", nil)
	w := httptest.NewRecorder()
	app.inventoryAPI(w, r)
	if w.Code != 405 {
		t.Fatal(w.Code)
	}
}
func TestInventoryDumpLimit(t *testing.T) {
	var buffer dumpBuffer
	data := make([]byte, 9<<20)
	n, err := buffer.Write(data)
	if err != nil || n != len(data) || !buffer.overflow || len(buffer.data) != 8<<20 {
		t.Fatal("limit broken")
	}
}
