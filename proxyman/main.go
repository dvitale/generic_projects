package main

import (
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"embed"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"syscall"
	"time"
)

//go:embed web/*
var web embed.FS

type Host struct {
	Domain      string `json:"domain"`
	Target      string `json:"target"`
	Port        int    `json:"port"`
	Scheme      string `json:"scheme"`
	Enabled     bool   `json:"enabled"`
	Websocket   bool   `json:"websocket"`
	Certificate string `json:"certificate"`
	Key         string `json:"key"`
}
type State struct {
	Hosts    []Host `json:"hosts"`
	Revision int    `json:"revision"`
}
type App struct {
	remote              *Remote
	mu                  sync.Mutex
	state               State
	data, config, nginx string
	live                bool
	applied             string
}

var label = regexp.MustCompile(`^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$`)
var certPath = regexp.MustCompile(`^/[a-zA-Z0-9_./-]+$`)

func validHost(s string) bool {
	if net.ParseIP(s) != nil {
		return true
	}
	if len(s) == 0 || len(s) > 253 {
		return false
	}
	for _, p := range strings.Split(s, ".") {
		if !label.MatchString(p) {
			return false
		}
	}
	return true
}
func validate(hosts []Host) error {
	if hosts == nil {
		return errors.New("hosts deve essere un elenco")
	}
	if len(hosts) > 200 {
		return errors.New("massimo 200 proxy")
	}
	seen := map[string]bool{}
	for _, h := range hosts {
		d := strings.ToLower(h.Domain)
		if !validHost(d) || strings.Contains(d, ":") || seen[d] {
			return errors.New("dominio non valido o duplicato")
		}
		seen[d] = true
		if !validHost(h.Target) || h.Port < 1 || h.Port > 65535 {
			return errors.New("destinazione o porta non valida")
		}
		if h.Scheme != "http" && h.Scheme != "https" {
			return errors.New("protocollo non valido")
		}
		if (h.Certificate == "") != (h.Key == "") {
			return errors.New("specifica sia certificato che chiave TLS")
		}
		for _, p := range []string{h.Certificate, h.Key} {
			if p != "" && (!certPath.MatchString(p) || filepath.Clean(p) != p) {
				return errors.New("percorso TLS non valido: usa un percorso assoluto senza spazi")
			}
		}
	}
	return nil
}
func render(hosts []Host) string {
	var b strings.Builder
	b.WriteString("# Gestito da Proxyman. Non modificare manualmente.\n")
	for _, h := range hosts {
		if !h.Enabled {
			continue
		}
		domain := strings.ToLower(h.Domain)
		b.WriteString("server {\n    listen 80;\n    server_name " + domain + ";\n")
		if h.Certificate != "" {
			b.WriteString("    return 301 https://$host$request_uri;\n}\nserver {\n    listen 443 ssl;\n    server_name " + domain + ";\n    ssl_certificate " + h.Certificate + ";\n    ssl_certificate_key " + h.Key + ";\n    ssl_protocols TLSv1.2 TLSv1.3;\n")
		}
		fmt.Fprintf(&b, "    location / {\n        proxy_pass %s://%s;\n", h.Scheme, net.JoinHostPort(h.Target, fmt.Sprint(h.Port)))
		b.WriteString("        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n")
		if h.Websocket {
			b.WriteString("        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection \"upgrade\";\n")
		}
		if h.Scheme == "https" {
			b.WriteString("        proxy_ssl_server_name on;\n        proxy_ssl_verify on;\n        proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;\n")
		}
		b.WriteString("    }\n}\n")
	}
	return b.String()
}
func atomicWrite(path string, data []byte, mode fs.FileMode) error {
	f, err := os.CreateTemp(filepath.Dir(path), ".proxyman-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err = f.Chmod(mode); err == nil {
		_, err = f.Write(data)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	return os.Rename(f.Name(), path)
}
func (a *App) command(args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, a.nginx, args...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("nginx %s: %w\n%s", strings.Join(args, " "), err, out)
	}
	return nil
}
func (a *App) apply() error { return a.applyContext(context.Background()) }
func (a *App) applyContext(ctx context.Context) error {
	if !a.live {
		return errors.New("applicazione diretta disabilitata; avvia con -apply dopo aver configurato Nginx")
	}
	next := render(a.state.Hosts)
	if a.remote != nil {
		if err := a.remote.apply(ctx, next); err != nil {
			return err
		}
		a.applied = next
		return nil
	}
	old, err := os.ReadFile(a.config)
	exists := err == nil
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if exists && !strings.HasPrefix(string(old), "# Gestito da Proxyman.") {
		return errors.New("il file destinazione non appartiene a Proxyman; scegli un file dedicato")
	}
	if err = atomicWrite(a.config, []byte(next), 0644); err != nil {
		return err
	}
	rollback := func(cause error) error {
		var restore error
		if exists {
			restore = atomicWrite(a.config, old, 0644)
		} else {
			restore = os.Remove(a.config)
		}
		if restore != nil {
			return fmt.Errorf("%v; RIPRISTINO FALLITO: %w", cause, restore)
		}
		return cause
	}
	if err = a.command("-t"); err != nil {
		return rollback(err)
	}
	if err = a.command("-s", "reload"); err != nil {
		original := rollback(err)
		if recovery := a.command("-s", "reload"); recovery != nil {
			return fmt.Errorf("%v; ricaricamento configurazione precedente fallito: %w", original, recovery)
		}
		return original
	}
	a.applied = next
	return nil
}
func reply(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(value)
}
func (a *App) api(w http.ResponseWriter, r *http.Request) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if r.Method == "GET" {
		switch r.URL.Path {
		case "/api/hosts":
			reply(w, 200, map[string]any{"hosts": a.state.Hosts, "revision": a.state.Revision, "live": a.live, "remote": a.remote != nil, "pending": a.applied != render(a.state.Hosts)})
		case "/api/config":
			w.Header().Set("Content-Type", "text/plain; charset=utf-8")
			io.WriteString(w, render(a.state.Hosts))
		default:
			http.NotFound(w, r)
		}
		return
	}
	if r.Method != "POST" {
		w.WriteHeader(405)
		return
	}
	if r.Header.Get("Content-Type") != "application/json" || r.Header.Get("X-Proxyman") != "1" {
		reply(w, 403, map[string]string{"error": "richiesta non valida"})
		return
	}
	var incoming State
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 256<<10))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&incoming); err != nil {
		reply(w, 400, map[string]string{"error": "JSON non valido"})
		return
	}
	if err := decoder.Decode(new(any)); err != io.EOF {
		reply(w, 400, map[string]string{"error": "contenuto aggiuntivo non valido"})
		return
	}
	if incoming.Revision != a.state.Revision {
		reply(w, 409, map[string]string{"error": "configurazione aggiornata in un'altra sessione: ricarica la pagina"})
		return
	}
	switch r.URL.Path {
	case "/api/hosts":
		if err := validate(incoming.Hosts); err != nil {
			reply(w, 400, map[string]string{"error": err.Error()})
			return
		}
		incoming.Revision++
		data, _ := json.MarshalIndent(incoming, "", "  ")
		if err := atomicWrite(a.data, data, 0600); err != nil {
			reply(w, 500, map[string]string{"error": err.Error()})
			return
		}
		a.state = incoming
		reply(w, 200, a.state)
	case "/api/check":
		if a.remote == nil {
			reply(w, 400, map[string]string{"error": "Seleziona un server SSH"})
			return
		}
		if err := a.remote.check(r.Context()); err != nil {
			reply(w, 400, map[string]string{"error": err.Error()})
			return
		}
		reply(w, 200, map[string]string{"message": "Connessione SSH, permessi e configurazione Nginx verificati"})
	case "/api/apply":
		if err := a.applyContext(r.Context()); err != nil {
			reply(w, 400, map[string]string{"error": err.Error()})
			return
		}
		reply(w, 200, map[string]string{"message": "Configurazione verificata e comando di ricaricamento inviato a Nginx"})
	default:
		http.NotFound(w, r)
	}
}
func secure(next http.Handler, user, password string) http.Handler {
	expectedUser, expectedPass := sha256.Sum256([]byte(user)), sha256.Sum256([]byte(password))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
		u, p, ok := r.BasicAuth()
		uh, ph := sha256.Sum256([]byte(u)), sha256.Sum256([]byte(p))
		if !ok || subtle.ConstantTimeCompare(uh[:], expectedUser[:])&subtle.ConstantTimeCompare(ph[:], expectedPass[:]) != 1 {
			w.Header().Set("WWW-Authenticate", `Basic realm="Proxyman", charset="UTF-8"`)
			http.Error(w, "Autenticazione richiesta", 401)
			return
		}
		next.ServeHTTP(w, r)
	})
}
func main() {
	addr := flag.String("listen", "127.0.0.1:8080", "indirizzo interfaccia web")
	data := flag.String("data", "var/hosts.json", "archivio configurazioni")
	config := flag.String("config", "/etc/nginx/conf.d/proxyman.conf", "file Nginx dedicato, incluso nel blocco http")
	binary := flag.String("nginx", "/usr/sbin/nginx", "eseguibile Nginx")
	live := flag.Bool("apply", false, "abilita verifica e ricaricamento del Nginx di sistema")
	flag.Parse()
	password := os.Getenv("PROXYMAN_PASSWORD")
	user := os.Getenv("PROXYMAN_USER")
	if user == "" {
		user = "admin"
	}
	if len(password) < 12 {
		log.Fatal("imposta PROXYMAN_PASSWORD con almeno 12 caratteri")
	}
	if err := os.MkdirAll(filepath.Dir(*data), 0700); err != nil {
		log.Fatal(err)
	}
	a := &App{data: *data, config: *config, nginx: *binary, live: *live, state: State{Hosts: []Host{}}}
	raw, err := os.ReadFile(*data)
	if err == nil {
		if err = json.Unmarshal(raw, &a.state); err != nil {
			log.Fatal(err)
		}
	} else if !os.IsNotExist(err) {
		log.Fatal(err)
	}
	if err = validate(a.state.Hosts); err != nil {
		log.Fatal(err)
	}
	// After restart, runtime application is intentionally considered unconfirmed.
	content, _ := fs.Sub(web, "web")
	mux := http.NewServeMux()
	remotes, err := loadRemotes(os.Getenv)
	if err != nil {
		log.Fatal(err)
	}
	servers, err := newServers(a, remotes)
	if err != nil {
		log.Fatal(err)
	}
	mux.Handle("/api/", servers)
	mux.Handle("/", http.FileServer(http.FS(content)))
	srv := &http.Server{Addr: *addr, Handler: secure(mux, user, password), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 20 * time.Second, WriteTimeout: 60 * time.Second, IdleTimeout: 60 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	shutdownDone := make(chan struct{})
	go func() {
		defer close(shutdownDone)
		<-ctx.Done()
		c, cancel := context.WithTimeout(context.Background(), 65*time.Second)
		defer cancel()
		if err := srv.Shutdown(c); err != nil {
			log.Printf("Arresto: %v", err)
		}
	}()
	log.Printf("Proxyman: http://%s (applicazione Nginx: %v)", *addr, *live)
	if err = srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
	<-shutdownDone
}
