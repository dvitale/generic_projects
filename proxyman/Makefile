GO ?= $(shell command -v go 2>/dev/null || echo /usr/local/go/bin/go)
BINARY := bin/proxyman
.PHONY: build test start stop restart status logs clean
build:
	CGO_ENABLED=0 $(GO) build -trimpath -ldflags="-s -w" -o $(BINARY) .
test:
	$(GO) test ./...
start: build
	@./scripts/service.sh start
stop:
	@./scripts/service.sh stop
restart: build
	@./scripts/service.sh stop
	@./scripts/service.sh start
status:
	@./scripts/service.sh status
logs:
	@tail -n 100 -f var/proxyman.log
clean:
	@./scripts/service.sh assert-stopped
	rm -f $(BINARY)
