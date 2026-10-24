package main

import (
	"context"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"golang.org/x/crypto/ssh"
)

// Private fields deliberately prevent accidental serialization of credentials.
type Remote struct {
	id, host, user, password, fingerprint, config, nginx, hostKeyType string
	port                                                              int
	sudo, live                                                        bool
}

var remoteID = regexp.MustCompile(`^[a-z][a-z0-9_]{0,31}$`)

func loadRemotes(getenv func(string) string) ([]*Remote, error) {
	var result []*Remote
	seen := map[string]bool{}
	for _, id := range strings.Fields(getenv("PROXYMAN_REMOTE_IDS")) {
		if !remoteID.MatchString(id) || id == "local" || seen[id] {
			return nil, errors.New("PROXYMAN_REMOTE_IDS: identificativo duplicato o non valido")
		}
		seen[id] = true
		prefix := "PROXYMAN_REMOTE_" + strings.ToUpper(id) + "_"
		get := func(key, fallback string) string {
			v := getenv(prefix + key)
			if v == "" {
				return fallback
			}
			return v
		}
		r := &Remote{id: id, host: get("IP", ""), user: get("USER", ""), password: get("PASSWORD", ""), fingerprint: get("HOST_KEY", ""), config: get("CONFIG", "/etc/nginx/conf.d/proxyman.conf"), nginx: get("NGINX", "/usr/sbin/nginx")}
		if !validHost(r.host) || r.user == "" || strings.ContainsAny(r.user, "\x00\r\n") || r.password == "" {
			return nil, fmt.Errorf("server %s: IP, USER e PASSWORD sono obbligatori e devono essere validi", id)
		}
		port, err := strconv.Atoi(get("PORT", "22"))
		if err != nil || port < 1 || port > 65535 {
			return nil, fmt.Errorf("server %s: porta non valida", id)
		}
		r.port = port
		r.hostKeyType = get("HOST_KEY_TYPE", "ssh-ed25519")
		switch r.hostKeyType {
		case "ssh-ed25519", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521", "rsa-sha2-256", "rsa-sha2-512":
		default:
			return nil, fmt.Errorf("server %s: HOST_KEY_TYPE non supportato", id)
		}
		raw, err := base64.RawStdEncoding.DecodeString(strings.TrimPrefix(r.fingerprint, "SHA256:"))
		if !strings.HasPrefix(r.fingerprint, "SHA256:") || err != nil || len(raw) != 32 {
			return nil, fmt.Errorf("server %s: HOST_KEY deve contenere l'impronta SHA256 della chiave SSH del server", id)
		}
		for _, p := range []string{r.config, r.nginx} {
			if !certPath.MatchString(p) || filepath.Clean(p) != p {
				return nil, fmt.Errorf("server %s: CONFIG e NGINX devono essere percorsi assoluti validi", id)
			}
		}
		for key, dest := range map[string]*bool{"SUDO": &r.sudo, "APPLY": &r.live} {
			fallback := "0"
			if key == "APPLY" {
				fallback = "1"
			}
			value := get(key, fallback)
			if value != "0" && value != "1" {
				return nil, fmt.Errorf("server %s: %s deve essere 0 oppure 1", id, key)
			}
			*dest = value == "1"
		}
		result = append(result, r)
	}
	return result, nil
}
func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'" }

// Both SSH output streams can write concurrently. Keep diagnostics bounded.
type diagnostics struct {
	mu   sync.Mutex
	text []byte
}

func (d *diagnostics) Write(p []byte) (int, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	n := len(p)
	remain := (16 << 10) - len(d.text)
	if len(p) > remain {
		p = p[:remain]
	}
	d.text = append(d.text, p...)
	return n, nil
}
func (r *Remote) run(ctx context.Context, command, input string) error {
	return r.execute(ctx, command, input, nil)
}
func (r *Remote) execute(ctx context.Context, command, input string, stdout io.Writer) error {
	ctx, cancel := context.WithTimeout(ctx, 45*time.Second)
	defer cancel()
	address := net.JoinHostPort(r.host, strconv.Itoa(r.port))
	conn, err := (&net.Dialer{Timeout: 8 * time.Second}).DialContext(ctx, "tcp", address)
	if err != nil {
		return fmt.Errorf("connessione SSH a %s fallita: %w", r.id, err)
	}
	defer conn.Close()
	deadline, _ := ctx.Deadline()
	conn.SetDeadline(deadline)
	stop := context.AfterFunc(ctx, func() { conn.Close() })
	defer stop()
	config := &ssh.ClientConfig{
		User:              r.user,
		HostKeyAlgorithms: []string{r.hostKeyType},
		Auth:              []ssh.AuthMethod{ssh.Password(r.password)},
		HostKeyCallback: func(_ string, _ net.Addr, key ssh.PublicKey) error {
			actual := ssh.FingerprintSHA256(key)
			if subtle.ConstantTimeCompare([]byte(actual), []byte(r.fingerprint)) != 1 {
				return errors.New("identità SSH non verificata: HOST_KEY non corrisponde")
			}
			return nil
		},
	}
	c, chans, requests, err := ssh.NewClientConn(conn, address, config)
	if err != nil {
		return fmt.Errorf("SSH %s: %w", r.id, err)
	}
	client := ssh.NewClient(c, chans, requests)
	defer client.Close()
	session, err := client.NewSession()
	if err != nil {
		return fmt.Errorf("sessione SSH %s: %w", r.id, err)
	}
	defer session.Close()
	var output diagnostics
	session.Stdout = &output
	if stdout != nil {
		session.Stdout = stdout
	}
	session.Stderr = &output
	session.Stdin = strings.NewReader(input)
	err = session.Run(command)
	if err != nil {
		if ctx.Err() != nil || time.Now().After(deadline) {
			return errors.New("timeout SSH: esito remoto non confermato; verificare Nginx sul server prima di riprovare")
		}
		detail := strings.ReplaceAll(string(output.text), r.password, "[redatto]")
		return fmt.Errorf("SSH %s: %w\n%s", r.id, err, detail)
	}
	return nil
}
func (r *Remote) command(script string) string {
	command := "sh -c " + shellQuote(script) + " -- " + shellQuote(r.config) + " " + shellQuote(r.nginx)
	if r.sudo {
		command = "sudo -n " + command
	}
	return command
}
func (r *Remote) apply(ctx context.Context, config string) error {
	return r.run(ctx, r.command(remoteApplyScript), config)
}
func (r *Remote) check(ctx context.Context) error {
	return r.run(ctx, r.command(`set -eu
command -v flock >/dev/null
command -v timeout >/dev/null
test -d "$(dirname "$1")"
test -w "$(dirname "$1")"
timeout 15 "$2" -t
`), "")
}

// stdin carries the generated configuration, never credentials.
// Temporary files and backups stay on the same filesystem as the destination.
const remoteApplyScript = `set -eu
conf=$1
nginx=$2
dir=$(dirname "$conf")
command -v timeout >/dev/null
command -v flock >/dev/null
test -d "$dir"
exec 9>"$conf.lock"
flock -w 5 9
if [ -L "$conf" ]; then echo "Il file destinazione è un link simbolico" >&2; exit 1; fi
work=$(mktemp -d "$dir/.proxyman-XXXXXX")
existed=0
installed=0
committed=0
reload_attempted=0
cleanup() {
 code=$?
 trap - EXIT HUP INT TERM
 if [ "$installed" = 1 ] && [ "$committed" = 0 ]; then
  if [ "$existed" = 1 ]; then
   if ! mv -f "$work/previous" "$conf"; then echo "RIPRISTINO FALLITO: backup in $work/previous" >&2; exit 1; fi
  else
   if ! rm -f "$conf"; then echo "RIPRISTINO FALLITO" >&2; exit 1; fi
  fi
  if [ "$reload_attempted" = 1 ]; then
   if ! timeout 10 "$nginx" -s reload; then echo "Ricaricamento precedente fallito: controllare Nginx" >&2; code=1; fi
  fi
 fi
 rm -rf "$work"
 exit "$code"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if [ -e "$conf" ]; then
 if [ ! -f "$conf" ] || ! head -n 1 "$conf" | grep -q '^# Gestito da Proxyman\.'; then
  echo "Il file destinazione non appartiene a Proxyman" >&2; exit 1
 fi
 cp -p "$conf" "$work/previous"
 existed=1
fi
cat >"$work/next"
chmod 644 "$work/next"
installed=1
mv -f "$work/next" "$conf"
timeout 15 "$nginx" -T >"$work/dump"
if ! grep -Fqx "# configuration file $conf:" "$work/dump"; then
 echo "Il file Proxyman non è incluso nella configurazione principale Nginx" >&2; exit 1
fi
reload_attempted=1
timeout 10 "$nginx" -s reload
committed=1
echo "Configurazione verificata e ricaricamento richiesto"
`

type ServerInfo struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Address string `json:"address"`
	Remote  bool   `json:"remote"`
}
type Servers struct {
	apps map[string]*App
	info []ServerInfo
}

func newServers(local *App, remotes []*Remote) (*Servers, error) {
	s := &Servers{apps: map[string]*App{"local": local}, info: []ServerInfo{{ID: "local", Name: "Questo server", Address: "locale"}}}
	for _, r := range remotes {
		a := &App{data: filepath.Join(filepath.Dir(local.data), "remote-"+r.id+".json"), config: r.config, nginx: r.nginx, live: r.live, remote: r, state: State{Hosts: []Host{}}}
		raw, err := os.ReadFile(a.data)
		if err == nil {
			if err = json.Unmarshal(raw, &a.state); err != nil {
				return nil, fmt.Errorf("archivio %s non valido", r.id)
			}
		} else if !os.IsNotExist(err) {
			return nil, err
		}
		if err = validate(a.state.Hosts); err != nil {
			return nil, fmt.Errorf("archivio %s: %w", r.id, err)
		}
		s.apps[r.id] = a
		s.info = append(s.info, ServerInfo{ID: r.id, Name: r.id, Address: net.JoinHostPort(r.host, strconv.Itoa(r.port)), Remote: true})
	}
	return s, nil
}
func (s *Servers) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/api/servers" {
		if r.Method != "GET" {
			w.WriteHeader(405)
			return
		}
		reply(w, 200, s.info)
		return
	}
	id := r.URL.Query().Get("server")
	if id == "" {
		id = "local"
	}
	app, ok := s.apps[id]
	if !ok {
		reply(w, 404, map[string]string{"error": "server non configurato"})
		return
	}
	if r.URL.Path == "/api/inventory" {
		app.inventoryAPI(w, r)
		return
	}
	if strings.HasPrefix(r.URL.Path, "/api/existing/") {
		app.existingAPI(w, r)
		return
	}
	app.api(w, r)
}

// Compile-time check for the bounded diagnostic writer.
var _ io.Writer = (*diagnostics)(nil)
