package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"path"
	"sort"
	"strings"
	"time"
)

type ExistingRoute struct {
	Location    string   `json:"location"`
	Destination string   `json:"destination"`
	Backends    []string `json:"backends"`
}
type ExistingProxy struct {
	Domains   []string        `json:"domains"`
	Listeners []string        `json:"listeners"`
	TLS       bool            `json:"tls"`
	File      string          `json:"file"`
	Line      int             `json:"line"`
	Routes    []ExistingRoute `json:"routes"`
	Managed   bool            `json:"managed"`
}
type Inventory struct {
	Proxies  []ExistingProxy `json:"proxies"`
	Warnings []string        `json:"warnings"`
}
type dumpBuffer struct {
	data     []byte
	overflow bool
}

func (b *dumpBuffer) Write(p []byte) (int, error) {
	n := len(p)
	remain := (8 << 20) - len(b.data)
	if len(p) > remain {
		p = p[:remain]
		b.overflow = true
	}
	b.data = append(b.data, p...)
	return n, nil
}
func (a *App) inventory(ctx context.Context) (Inventory, error) {
	var output dumpBuffer
	var err error
	if a.remote != nil {
		err = a.remote.execute(ctx, a.remote.command(`set -eu
timeout 20 "$2" -T
`), "", &output)
	} else {
		ctx, cancel := context.WithTimeout(ctx, 25*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, a.nginx, "-T")
		var diagnostic diagnostics
		cmd.Stdout = &output
		cmd.Stderr = &diagnostic
		if e := cmd.Run(); e != nil {
			err = fmt.Errorf("lettura Nginx: %w\n%s", e, diagnostic.text)
		}
	}
	if err != nil {
		return Inventory{}, err
	}
	if output.overflow {
		return Inventory{}, errors.New("configurazione Nginx superiore a 8 MB: lettura incompleta")
	}
	return parseInventory(string(output.data), a.config)
}
func (a *App) inventoryAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		w.WriteHeader(405)
		return
	}
	// Serialize with applies on this target to avoid reading a candidate file mid-test.
	a.mu.Lock()
	defer a.mu.Unlock()
	result, err := a.inventory(r.Context())
	if err != nil {
		reply(w, 400, map[string]string{"error": err.Error()})
		return
	}
	reply(w, 200, result)
}

type confToken struct {
	value      string
	line       int
	symbol     bool
	start, end int
}
type confNode struct {
	name                                  string
	args                                  []string
	children                              []confNode
	file                                  string
	line                                  int
	block                                 bool
	start, end, argsStart, argsEnd, close int
}

func lexConfig(text string) ([]confToken, error) {
	var result []confToken
	line := 1
	for i := 0; i < len(text); {
		c := text[i]
		if c == ' ' || c == '\t' || c == '\r' || c == '\n' {
			if c == '\n' {
				line++
			}
			i++
			continue
		}
		if c == '#' {
			for i < len(text) && text[i] != '\n' {
				i++
			}
			continue
		}
		if c == ';' || c == '{' || c == '}' {
			result = append(result, confToken{value: string(c), line: line, symbol: true, start: i, end: i + 1})
			i++
			continue
		}
		start := line
		startOffset := i
		var b strings.Builder
		for i < len(text) {
			c = text[i]
			if c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == ';' || c == '{' || c == '}' || c == '#' {
				break
			}
			if c == '\'' || c == '"' {
				quote := c
				i++
				closed := false
				for i < len(text) {
					c = text[i]
					if c == quote {
						i++
						closed = true
						break
					}
					if c == '\\' && i+1 < len(text) {
						i++
						c = text[i]
					}
					if c == '\n' {
						line++
					}
					b.WriteByte(c)
					i++
				}
				if !closed {
					return nil, fmt.Errorf("stringa non terminata alla riga %d", start)
				}
				continue
			}
			if c == '$' && i+1 < len(text) && text[i+1] == '{' {
				end := strings.IndexByte(text[i+2:], '}')
				if end < 0 {
					return nil, errors.New("variabile Nginx non terminata")
				}
				b.WriteString(text[i : i+end+3])
				i += end + 3
				continue
			}
			if c == '\\' && i+1 < len(text) {
				i++
				c = text[i]
			}
			b.WriteByte(c)
			i++
		}
		result = append(result, confToken{value: b.String(), line: start, start: startOffset, end: i})
	}
	return result, nil
}
func parseNodes(tokens []confToken, file string) ([]confNode, error) {
	pos := 0
	var parse func(bool, int) ([]confNode, error)
	parse = func(nested bool, depth int) ([]confNode, error) {
		if depth > 100 {
			return nil, errors.New("annidamento Nginx eccessivo")
		}
		var nodes []confNode
		for pos < len(tokens) {
			first := tokens[pos]
			pos++
			if first.symbol && first.value == "}" {
				if nested {
					return nodes, nil
				}
				return nil, errors.New("chiusura inattesa")
			}
			if first.symbol {
				return nil, fmt.Errorf("direttiva inattesa alla riga %d", first.line)
			}
			node := confNode{name: first.value, file: file, line: first.line, start: first.start}
			ended := false
			for pos < len(tokens) {
				t := tokens[pos]
				pos++
				if t.symbol {
					switch t.value {
					case ";":
						node.end = t.end
						ended = true
					case "{":
						children, err := parse(true, depth+1)
						if err != nil {
							return nil, err
						}
						node.children = children
						node.end = tokens[pos-1].end
						node.close = tokens[pos-1].start
						node.block = true
						ended = true
					default:
						return nil, fmt.Errorf("direttiva incompleta alla riga %d", first.line)
					}
					break
				}
				if len(node.args) == 0 {
					node.argsStart = t.start
				}
				node.argsEnd = t.end
				node.args = append(node.args, t.value)
			}
			if !ended {
				return nil, fmt.Errorf("direttiva incompleta alla riga %d", first.line)
			}
			nodes = append(nodes, node)
		}
		if nested {
			return nil, errors.New("blocco Nginx non chiuso")
		}
		return nodes, nil
	}
	return parse(false, 0)
}
func parseInventory(dump, managed string) (Inventory, error) {
	result := Inventory{Proxies: []ExistingProxy{}, Warnings: []string{}}
	texts := map[string]string{}
	var order []string
	current := ""
	var body strings.Builder
	flush := func() {
		if current != "" {
			texts[current] = body.String()
			body.Reset()
		}
	}
	for _, line := range strings.Split(dump, "\n") {
		if strings.HasPrefix(line, "# configuration file ") && strings.HasSuffix(line, ":") {
			flush()
			current = strings.TrimSuffix(strings.TrimPrefix(line, "# configuration file "), ":")
			if _, exists := texts[current]; !exists {
				order = append(order, current)
			}
		} else if current != "" {
			body.WriteString(line)
			body.WriteByte('\n')
		}
	}
	flush()
	if len(order) == 0 {
		return result, errors.New("Nginx non ha restituito i file di configurazione")
	}
	files := map[string][]confNode{}
	for _, file := range order {
		tokens, err := lexConfig(texts[file])
		if err != nil {
			return result, fmt.Errorf("%s: %w", file, err)
		}
		nodes, err := parseNodes(tokens, file)
		if err != nil {
			return result, fmt.Errorf("%s: %w", file, err)
		}
		files[file] = nodes
	}
	prefix := path.Dir(order[0])
	var expand func([]confNode, map[string]bool, int) []confNode
	expand = func(nodes []confNode, stack map[string]bool, depth int) []confNode {
		if depth > 100 {
			result.Warnings = append(result.Warnings, "Limite di espansione include raggiunto")
			return nil
		}
		var expanded []confNode
		for _, node := range nodes {
			if node.name == "include" && len(node.args) == 1 {
				pattern := node.args[0]
				if !path.IsAbs(pattern) {
					pattern = path.Join(prefix, pattern)
				}
				var matches []string
				for file := range files {
					if match, _ := path.Match(pattern, file); match {
						matches = append(matches, file)
					}
				}
				sort.Strings(matches)
				if len(matches) == 0 && !strings.ContainsAny(pattern, "*?[") {
					result.Warnings = append(result.Warnings, "Include non risolto: "+pattern)
				}
				for _, file := range matches {
					if stack[file] {
						result.Warnings = append(result.Warnings, "Include ricorsivo: "+file)
						continue
					}
					stack[file] = true
					expanded = append(expanded, expand(files[file], stack, depth+1)...)
					delete(stack, file)
				}
			} else {
				node.children = expand(node.children, stack, depth+1)
				expanded = append(expanded, node)
			}
		}
		return expanded
	}
	nodes := expand(files[order[0]], map[string]bool{order[0]: true}, 0)
	upstreams := map[string][]string{}
	var walk func([]confNode, func(confNode))
	walk = func(nodes []confNode, fn func(confNode)) {
		for _, n := range nodes {
			fn(n)
			walk(n.children, fn)
		}
	}
	walk(nodes, func(n confNode) {
		if n.name == "upstream" && len(n.args) > 0 {
			for _, s := range n.children {
				if s.name == "server" && len(s.args) > 0 {
					upstreams[n.args[0]] = append(upstreams[n.args[0]], strings.Join(s.args, " "))
				}
			}
		}
	})
	walk(nodes, func(n confNode) {
		if n.name != "server" || !n.block {
			return
		}
		item := ExistingProxy{File: n.file, Line: n.line, Domains: []string{}, Listeners: []string{}, Routes: []ExistingRoute{}, Managed: path.Clean(n.file) == path.Clean(managed)}
		for _, c := range n.children {
			switch c.name {
			case "server_name":
				item.Domains = append(item.Domains, c.args...)
			case "listen":
				item.Listeners = append(item.Listeners, strings.Join(c.args, " "))
				for _, arg := range c.args {
					if arg == "ssl" {
						item.TLS = true
					}
				}
			case "ssl":
				if len(c.args) > 0 && c.args[0] == "on" {
					item.TLS = true
				}
			}
		}
		var routes func([]confNode, string)
		routes = func(children []confNode, location string) {
			for _, c := range children {
				current := location
				if c.name == "location" {
					current = strings.Join(c.args, " ")
				}
				if c.name == "proxy_pass" && len(c.args) > 0 && (strings.HasPrefix(c.args[0], "http://") || strings.HasPrefix(c.args[0], "https://")) {
					destination := c.args[0]
					// Summaries never expose credentials embedded in a URL.
					if schemeEnd := strings.Index(destination, "://"); schemeEnd >= 0 {
						tail := destination[schemeEnd+3:]
						end := strings.IndexAny(tail, "/?#")
						if end < 0 {
							end = len(tail)
						}
						if at := strings.LastIndex(tail[:end], "@"); at >= 0 {
							destination = destination[:schemeEnd+3] + "[redatto]@" + tail[at+1:]
						}
					}
					name := strings.SplitN(strings.SplitN(c.args[0], "://", 2)[1], "/", 2)[0]
					backends := append([]string{}, upstreams[name]...)
					item.Routes = append(item.Routes, ExistingRoute{Location: current, Destination: destination, Backends: backends})
				}
				routes(c.children, current)
			}
		}
		routes(n.children, "/")
		if len(item.Routes) == 0 {
			return
		}
		if len(item.Domains) == 0 {
			item.Domains = []string{"(server predefinito)"}
		}
		result.Proxies = append(result.Proxies, item)
	})
	return result, nil
}

var _ io.Writer = (*dumpBuffer)(nil)
