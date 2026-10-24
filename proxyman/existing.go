package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

type EditField struct {
	ID                string `json:"id"`
	Label             string `json:"label"`
	Kind              string `json:"kind"`
	Value             string `json:"value"`
	Section           string `json:"section"`
	Step              int    `json:"step"`
	Help              string `json:"help"`
	ReadOnly          bool   `json:"readOnly"`
	node              *confNode
	scope             confNode
	directive, prefix string
}
type EditModel struct {
	File             string      `json:"file"`
	Line             int         `json:"line"`
	Version          string      `json:"version"`
	Fields           []EditField `json:"fields"`
	Warnings         []string    `json:"warnings"`
	Live             bool        `json:"live"`
	source, resolved string
	server           confNode
}
type AddedRoute struct {
	Location    string `json:"location"`
	Destination string `json:"destination"`
	Websocket   bool   `json:"websocket"`
}
type EditRequest struct {
	File    string            `json:"file"`
	Line    int               `json:"line"`
	Version string            `json:"version"`
	Values  map[string]string `json:"values"`
	Routes  []AddedRoute      `json:"routes"`
	Preview string            `json:"preview"`
}
type EditChange struct {
	Label  string `json:"label"`
	Before string `json:"before"`
	After  string `json:"after"`
}
type EditPreview struct {
	Changes []EditChange `json:"changes"`
	Hash    string       `json:"hash"`
}

func digest(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

func (a *App) sourceFile(ctx context.Context, file string) (string, string, error) {
	if !certPath.MatchString(file) || filepath.Clean(file) != file {
		return "", "", errors.New("percorso file non valido")
	}
	if a.remote != nil {
		remote := *a.remote
		remote.config = file
		var output dumpBuffer
		err := remote.execute(ctx, remote.command(`set -eu
target=$(readlink -f -- "$1")
test -f "$target"
printf '%s\n' "$target"
head -c 2097153 -- "$target"
`), "", &output)
		if err != nil {
			return "", "", err
		}
		parts := strings.SplitN(string(output.data), "\n", 2)
		if len(parts) != 2 || !certPath.MatchString(parts[0]) || len(parts[1]) > 2<<20 {
			return "", "", errors.New("file non supportato o superiore a 2 MB")
		}
		return parts[1], parts[0], nil
	}
	resolved, err := filepath.EvalSymlinks(file)
	if err != nil {
		return "", "", err
	}
	f, err := os.Open(resolved)
	if err != nil {
		return "", "", err
	}
	defer f.Close()
	raw, err := io.ReadAll(io.LimitReader(f, (2<<20)+1))
	if err != nil {
		return "", "", err
	}
	if len(raw) > 2<<20 {
		return "", "", errors.New("file superiore a 2 MB")
	}
	return string(raw), resolved, nil
}
func (a *App) openExisting(ctx context.Context, req EditRequest) (EditModel, error) {
	// Derive allowed files from the live inventory, never accept arbitrary paths.
	inventory, err := a.inventory(ctx)
	if err != nil {
		return EditModel{}, err
	}
	found := false
	for _, p := range inventory.Proxies {
		if p.File == req.File && p.Line == req.Line {
			if p.Managed {
				return EditModel{}, errors.New("usa il modulo Proxy gestiti da Proxyman per questo file")
			}
			found = true
			break
		}
	}
	if !found {
		return EditModel{}, errors.New("proxy non più presente: aggiorna l'elenco")
	}
	source, resolved, err := a.sourceFile(ctx, req.File)
	if err != nil {
		return EditModel{}, err
	}
	model, err := makeEditModel(req.File, req.Line, source)
	if err != nil {
		return model, err
	}
	model.resolved = resolved
	model.Live = a.live
	return model, nil
}
func makeEditModel(file string, line int, source string) (EditModel, error) {
	model := EditModel{File: file, Line: line, Version: digest(source), Fields: []EditField{}, Warnings: []string{}, source: source}
	tokens, err := lexConfig(source)
	if err != nil {
		return model, err
	}
	nodes, err := parseNodes(tokens, file)
	if err != nil {
		return model, err
	}
	var selected *confNode
	var find func([]confNode)
	find = func(nodes []confNode) {
		for _, n := range nodes {
			if n.name == "server" && n.block && n.line == line {
				v := n
				selected = &v
			}
			find(n.children)
		}
	}
	find(nodes)
	if selected == nil {
		return model, errors.New("blocco server non trovato: aggiorna l'elenco")
	}
	model.server = *selected
	add := func(scope confNode, name, label, kind, section string, step int, help, prefix string) {
		matches := []confNode{}
		for _, n := range scope.children {
			if n.name == name && (prefix == "" || (len(n.args) > 0 && n.args[0] == prefix)) {
				matches = append(matches, n)
			}
		}
		if len(matches) == 0 {
			model.Fields = append(model.Fields, EditField{ID: fmt.Sprintf("%d:%s:%s:new", scope.start, name, prefix), Label: label, Kind: kind, Section: section, Step: step, Help: help, scope: scope, directive: name, prefix: prefix})
		}
		for i, n := range matches {
			args := n.args
			if prefix != "" {
				// Preserve the explicit location modifier.[1:]
			}
			value := strings.Join(args, " ")
			readonly := false
			if kind == "destination" {
				u, _ := url.Parse(value)
				if u != nil && u.User != nil {
					value = "[destinazione con credenziali: conservata]"
					readonly = true
				}
			}
			node := n
			model.Fields = append(model.Fields, EditField{ID: fmt.Sprintf("%d:%s:%s:%d", scope.start, name, prefix, i), Label: label, Kind: kind, Value: value, Section: section, Step: step, Help: help, ReadOnly: readonly, node: &node, scope: scope, directive: name, prefix: prefix})
		}
	}
	add(*selected, "server_name", "Domini", "domains", "Dominio e ascolto", 1, "Separa più domini con spazi. Sono accettati anche wildcard come *.example.it.", "")
	add(*selected, "listen", "Ascolto", "listen", "Dominio e ascolto", 1, "Indirizzo, porta e TLS. Le opzioni aggiuntive del listener sono conservate.", "")
	add(*selected, "ssl_certificate", "Certificato TLS", "path", "Certificati TLS", 3, "Percorso PEM sul server Nginx.", "")
	add(*selected, "ssl_certificate_key", "Chiave privata TLS", "path", "Certificati TLS", 3, "Percorso della chiave sul server; il contenuto non viene letto.", "")
	var scopes func(confNode, string)
	scopes = func(scope confNode, section string) {
		hasProxy := false
		for _, n := range scope.children {
			if n.name == "proxy_pass" {
				hasProxy = true
			}
		}
		if scope.name == "location" {
			model.Fields = append(model.Fields, EditField{ID: fmt.Sprintf("%d:location", scope.start), Label: "Percorso pubblico", Kind: "location", Value: strings.Join(scope.args, " "), Section: section, Step: 2, Help: "Percorso /..., oppure = /... per una corrispondenza esatta.", node: &scope, scope: scope, directive: "location"})
		}
		if hasProxy {
			add(scope, "proxy_pass", "Destinazione del servizio", "destination", section, 2, "Mantieni il percorso finale: una barra finale può cambiare l'inoltro delle richieste.", "")
			add(scope, "proxy_http_version", "Versione HTTP verso il servizio", "httpversion", section, 2, "Vuoto: conserva l'ereditarietà Nginx.", "")
			add(scope, "proxy_set_header", "Header WebSocket Upgrade", "upgrade", section, 2, "Per WebSocket usa $http_upgrade; vuoto rimuove la direttiva locale.", "Upgrade")
			add(scope, "proxy_set_header", "Header WebSocket Connection", "connection", section, 2, "Per WebSocket usa upgrade oppure $connection_upgrade.", "Connection")
		}
		if scope.name == "server" || hasProxy {
			for _, field := range []struct{ name, label, kind string }{
				{"proxy_connect_timeout", "Timeout connessione", "duration"},
				{"proxy_read_timeout", "Timeout lettura", "duration"},
				{"proxy_send_timeout", "Timeout invio", "duration"},
				{"client_max_body_size", "Dimensione massima richiesta", "size"},
			} {
				add(scope, field.name, field.label, field.kind, section, 3, "Vuoto: usa il valore ereditato. Specifica unità come 60s o 20m.", "")
			}
		}
		for _, n := range scope.children {
			if n.name == "include" {
				model.Warnings = append(model.Warnings, "Include conservato: "+strings.Join(n.args, " ")+". Le direttive nel file incluso restano invariate.")
			}
			if n.name == "location" {
				scopes(n, "Percorso "+strings.Join(n.args, " "))
			}
		}
	}
	scopes(*selected, "Impostazioni del server")
	return model, nil
}
func nginxToken(s string) string {
	if regexp.MustCompile(`^[a-zA-Z0-9_./:$\[\]*~^?=&%+@,!()-]+$`).MatchString(s) && !strings.Contains(s, "${") {
		return s
	}
	return "\"" + strings.NewReplacer("\\", "\\\\", "\"", "\\\"").Replace(s) + "\""
}
func formatField(f EditField, value string) (string, error) {
	if strings.ContainsAny(value, "\x00\r\n;{}#") {
		return "", errors.New("caratteri non validi nel campo " + f.Label)
	}
	if value == "" {
		return "", nil
	}
	args := []string{value}
	switch f.Kind {
	case "domains":
		args = strings.Fields(value)
		for _, s := range args {
			v := strings.TrimPrefix(strings.TrimPrefix(s, "*."), ".")
			if s != "_" && (!validHost(v) || strings.Contains(v, ":")) {
				return "", errors.New("dominio non valido")
			}
		}
	case "listen":
		args = strings.Fields(value)
		endpoint := args[0]
		port := endpoint
		if strings.Contains(endpoint, ":") {
			host, p, err := net.SplitHostPort(endpoint)
			if err != nil || host != "" && !validHost(host) {
				return "", errors.New("indirizzo di ascolto non valido")
			}
			port = p
		}
		number, err := strconv.Atoi(port)
		if err != nil || number < 1 || number > 65535 {
			return "", errors.New("porta di ascolto non valida")
		}
		for _, option := range args[1:] {
			if !regexp.MustCompile(`^[a-zA-Z0-9_=]+$`).MatchString(option) {
				return "", errors.New("opzione listener non valida")
			}
		}
	case "destination":
		u, err := url.Parse(value)
		if err != nil || u.Host == "" || u.User != nil || u.Fragment != "" || (u.Scheme != "http" && u.Scheme != "https") || strings.ContainsAny(value, " \t\"'\\$") {
			return "", errors.New("destinazione HTTP/HTTPS non valida")
		}
		if u.Port() != "" {
			port, e := strconv.Atoi(u.Port())
			if e != nil || port < 1 || port > 65535 {
				return "", errors.New("porta destinazione non valida")
			}
		}
	case "location":
		args = strings.Fields(value)
		if len(args) == 2 && (args[0] == "=" || args[0] == "^~") {
			// Preserve the explicit location modifier.
		} else if len(args) != 1 {
			return "", errors.New("modifica guidata disponibile per percorsi /..., = /... e ^~ /...")
		}
		if !strings.HasPrefix(args[len(args)-1], "/") || strings.ContainsAny(value, "\"'\\") {
			return "", errors.New("percorso non valido")
		}
	case "path":
		if !certPath.MatchString(value) || filepath.Clean(value) != value {
			return "", errors.New("percorso certificato non valido")
		}
	case "duration":
		if !regexp.MustCompile(`^[0-9]+(ms|s|m|h|d)?$`).MatchString(value) {
			return "", errors.New("timeout non valido (esempio: 60s)")
		}
	case "size":
		if !regexp.MustCompile(`^[0-9]+[kKmMgG]?$`).MatchString(value) {
			return "", errors.New("dimensione non valida (esempio: 20m)")
		}
	case "httpversion":
		if value != "1.0" && value != "1.1" && value != "2" {
			return "", errors.New("versione HTTP non valida")
		}
	case "upgrade":
		if value != "$http_upgrade" {
			return "", errors.New("Upgrade deve essere $http_upgrade oppure vuoto")
		}
	case "connection":
		if value != "upgrade" && value != "close" && value != "$connection_upgrade" {
			return "", errors.New("Connection non valido")
		}
	default:
		return "", errors.New("campo non supportato")
	}
	for i, s := range args {
		args[i] = nginxToken(s)
	}
	if f.prefix != "" {
		args = append([]string{f.prefix}, args...)
	}
	return strings.Join(args, " "), nil
}

type sourcePatch struct {
	start, end int
	text       string
}

func prepareEdit(model EditModel, req EditRequest) (string, EditPreview, error) {
	preview := EditPreview{Changes: []EditChange{}}
	if req.Version != model.Version {
		return "", preview, errors.New("il file è cambiato sul server: riapri il modulo")
	}
	known := map[string]bool{}
	patches := []sourcePatch{}
	insertions := map[int]string{}
	for _, field := range model.Fields {
		known[field.ID] = true
		value, exists := req.Values[field.ID]
		if !exists || value == field.Value {
			continue
		}
		if field.ReadOnly {
			return "", preview, errors.New("campo non modificabile nel modulo")
		}
		value = strings.TrimSpace(value)
		formatted, err := formatField(field, value)
		if err != nil {
			return "", preview, err
		}
		if field.Kind == "location" && value == "" {
			return "", preview, errors.New("il percorso non può essere vuoto")
		}
		if field.node != nil {
			n := field.node
			if value == "" {
				patches = append(patches, sourcePatch{n.start, n.end, ""})
			} else {
				patches = append(patches, sourcePatch{n.argsStart, n.argsEnd, formatted})
			}
		} else if value != "" {
			indent := nodeIndent(model.source, field.scope) + "    "
			insertions[field.scope.close] += "\n" + indent + field.directive + " " + formatted + ";\n" + nodeIndent(model.source, field.scope)
		}
		preview.Changes = append(preview.Changes, EditChange{Label: field.Section + " · " + field.Label, Before: field.Value, After: value})
	}
	for id := range req.Values {
		if !known[id] {
			return "", preview, errors.New("campo sconosciuto: riapri il modulo")
		}
	}
	if len(req.Routes) > 50 {
		return "", preview, errors.New("troppi nuovi percorsi")
	}
	locations := map[string]bool{}
	for _, field := range model.Fields {
		if field.Kind == "location" {
			v := field.Value
			if next, ok := req.Values[field.ID]; ok {
				v = next
			}
			locations[v] = true
		}
	}
	for _, route := range req.Routes {
		loc, err := formatField(EditField{Kind: "location", Label: "Percorso"}, route.Location)
		if err != nil || loc == "" {
			return "", preview, errors.New("nuovo percorso non valido")
		}
		dest, err := formatField(EditField{Kind: "destination", Label: "Destinazione"}, route.Destination)
		if err != nil || dest == "" {
			return "", preview, errors.New("destinazione del nuovo percorso non valida")
		}
		if locations[route.Location] {
			return "", preview, errors.New("percorso duplicato")
		}
		locations[route.Location] = true
		indent := nodeIndent(model.source, model.server) + "    "
		block := "\n" + indent + "location " + loc + " {\n" + indent + "    proxy_pass " + dest + ";\n"
		if route.Websocket {
			block += indent + "    proxy_http_version 1.1;\n" + indent + "    proxy_set_header Upgrade $http_upgrade;\n" + indent + "    proxy_set_header Connection upgrade;\n"
		}
		block += indent + "}\n" + nodeIndent(model.source, model.server)
		insertions[model.server.close] += block
		preview.Changes = append(preview.Changes, EditChange{Label: "Nuovo percorso", After: route.Location + " → " + route.Destination})
	}
	for pos, text := range insertions {
		patches = append(patches, sourcePatch{pos, pos, text})
	}
	sort.Slice(patches, func(i, j int) bool { return patches[i].start > patches[j].start })
	next := model.source
	limit := len(next)
	for _, p := range patches {
		if p.start < 0 || p.end > limit || p.end < p.start {
			return "", preview, errors.New("modifiche sovrapposte")
		}
		next = next[:p.start] + p.text + next[p.end:]
		limit = p.start
	}
	tokens, err := lexConfig(next)
	if err != nil {
		return "", preview, err
	}
	if _, err = parseNodes(tokens, model.File); err != nil {
		return "", preview, err
	}
	preview.Hash = digest(next)
	return next, preview, nil
}
func nodeIndent(source string, n confNode) string {
	start := strings.LastIndex(source[:n.start], "\n") + 1
	prefix := source[start:n.start]
	if strings.TrimSpace(prefix) != "" {
		return ""
	}
	return prefix
}

func (a *App) existingAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		w.WriteHeader(405)
		return
	}
	if r.Header.Get("Content-Type") != "application/json" || r.Header.Get("X-Proxyman") != "1" {
		reply(w, 403, map[string]string{"error": "richiesta non valida"})
		return
	}
	var req EditRequest
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 256<<10))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		reply(w, 400, map[string]string{"error": "richiesta non valida"})
		return
	}
	if dec.Decode(new(any)) != io.EOF {
		reply(w, 400, map[string]string{"error": "contenuto aggiuntivo non valido"})
		return
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	ctx, cancel := context.WithTimeout(r.Context(), 50*time.Second)
	defer cancel()
	if r.URL.Path != "/api/existing/open" && r.URL.Path != "/api/existing/preview" && r.URL.Path != "/api/existing/apply" {
		http.NotFound(w, r)
		return
	}
	model, err := a.openExisting(ctx, req)
	if err != nil {
		reply(w, 400, map[string]string{"error": err.Error()})
		return
	}
	if r.URL.Path == "/api/existing/open" {
		reply(w, 200, model)
		return
	}
	if req.Version != model.Version {
		reply(w, 409, map[string]string{"error": "il file è cambiato sul server: riapri il modulo"})
		return
	}
	next, preview, err := prepareEdit(model, req)
	if err != nil {
		reply(w, 400, map[string]string{"error": err.Error()})
		return
	}
	if r.URL.Path == "/api/existing/preview" {
		reply(w, 200, preview)
		return
	}
	if !a.live {
		reply(w, 403, map[string]string{"error": "applicazione disabilitata per questo server"})
		return
	}
	if req.Preview != preview.Hash || len(preview.Changes) == 0 {
		reply(w, 409, map[string]string{"error": "genera una nuova anteprima prima di applicare"})
		return
	}
	backup, err := a.applyExisting(ctx, model, next)
	if err != nil {
		reply(w, 400, map[string]string{"error": err.Error()})
		return
	}
	reply(w, 200, map[string]string{"message": "Configurazione verificata e ricaricamento richiesto. Backup: " + backup, "backup": backup})
}
func (a *App) applyExisting(ctx context.Context, model EditModel, next string) (string, error) {
	var output dumpBuffer
	var err error
	if a.remote != nil {
		remote := *a.remote
		remote.config = model.File
		command := remote.command(existingApplyScript) + " " + shellQuote(model.Version) + " " + shellQuote(model.resolved)
		err = remote.execute(ctx, command, next, &output)
	} else {
		ctx, cancel := context.WithTimeout(ctx, 45*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, "sh", "-c", existingApplyScript, "--", model.File, a.nginx, model.Version, model.resolved)
		var diagnostics diagnostics
		cmd.Stdin = strings.NewReader(next)
		cmd.Stdout = &output
		cmd.Stderr = &diagnostics
		if e := cmd.Run(); e != nil {
			err = fmt.Errorf("applicazione fallita: %w\n%s", e, diagnostics.text)
		}
	}
	if err != nil {
		return "", err
	}
	backup := strings.TrimSpace(string(output.data))
	if backup == "" {
		return "", errors.New("esito non confermato: controlla il server")
	}
	return backup, nil
}

const existingApplyScript = `set -eu
source=$1
nginx=$2
expected=$3
resolved=$4
target=$(readlink -f -- "$source")
if [ "$target" != "$resolved" ]; then echo "Il collegamento al file è cambiato: riaprire il modulo" >&2; exit 1; fi
test -f "$target"
dir=$(dirname "$target")
exec 9>"$dir/.proxyman-edit.lock"
flock -w 5 9
work=$(mktemp -d "$dir/.proxyman-edit-XXXXXX")
installed=0
committed=0
reload_attempted=0
backup=''
cleanup() {
 code=$?
 trap - EXIT HUP INT TERM
 if [ "$installed" = 1 ] && [ "$committed" = 0 ]; then
  if ! cp -p "$backup" "$work/restore" || ! mv -f "$work/restore" "$target"; then
   echo "RIPRISTINO FALLITO. Backup conservato: $backup" >&2
   exit 1
  fi
  if [ "$reload_attempted" = 1 ]; then
   if ! timeout 10 "$nginx" -s reload; then echo "Ricaricamento precedente fallito; controllare Nginx" >&2; code=1; fi
  fi
 fi
 rm -rf "$work"
 exit "$code"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
cp -p "$target" "$work/next"
cat >"$work/next"
actual=$(sha256sum "$target")
actual=${actual%% *}
if [ "$actual" != "$expected" ] || [ "$(readlink -f -- "$source")" != "$resolved" ]; then
 echo "Il file è cambiato: riaprire il modulo" >&2; exit 1
fi
backupdir="$dir/.proxyman-backups"
if [ -L "$backupdir" ]; then echo "Cartella backup non valida" >&2; exit 1; fi
mkdir -p "$backupdir"
chmod 700 "$backupdir"
backup=$(mktemp "$backupdir/$(basename "$target").XXXXXXXX")
cp -p "$target" "$backup"
installed=1
mv -f "$work/next" "$target"
timeout 15 "$nginx" -t
reload_attempted=1
timeout 10 "$nginx" -s reload
committed=1
printf '%s\n' "$backup"
`
