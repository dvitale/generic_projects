.DEFAULT_GOAL := help
PORT ?= 8033
STOP_TIMEOUT ?= 60
PYTHON ?= python3

.PHONY: help start status restart stop build logs deploy puzzles

help:
	@printf '%s\n' 'SparringMate — comandi WSL Debian' '  make start    Avvia in background' '  make status   Mostra stato, indirizzo e log' '  make restart  Arresta con attesa e riavvia' '  make stop     Arresta senza cancellare dati' '  make build    Ricompila l’interfaccia' '  make logs     Mostra le ultime righe del log' '  make deploy   Pubblica su sparringmate.u-s.it (vedi deploy/SERVER.md)' '  make puzzles  Scarica i problemi Lichess per fasce di rating (PER_BAND=3000)' 'Opzioni: PORT=8033 STOP_TIMEOUT=60'

start status restart stop logs:
	@$(PYTHON) "$(CURDIR)/scripts/service.py" $@ --port "$(PORT)" --stop-timeout "$(STOP_TIMEOUT)"

build:
	@cd "$(CURDIR)/web" && npm run build

deploy:
	@"$(CURDIR)/scripts/deploy.sh"

PER_BAND ?= 3000
puzzles:
	@"$(CURDIR)/.venv/bin/python" "$(CURDIR)/scripts/import_lichess_puzzles.py" --per-band "$(PER_BAND)"
