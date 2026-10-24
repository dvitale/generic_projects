.DEFAULT_GOAL := help
PY := .venv/bin/python
STEPS ?= 100
BATCH ?= 16
RUN ?= runs/tiny
PRESET ?= tiny
GAMES ?= 5000
TOP_K ?= 5
DATA ?= data/positions.sqlite
OUTPUT ?= runs/comparison-pilot
MONTH ?= 2026-09
MONTHS ?= 2026-09
CYCLE_STEPS ?= 10000

.PHONY: help setup download prepare test train resume status predict reference benchmark download-month month-status cycle cycle-status
help:
	@printf '%s\n' 'Modello sperimentale di mosse umane — GPU locale' 'make setup | download | prepare | test | train | resume | status | reference | benchmark' 'make predict FEN="..." ELO=800' 'Opzioni: STEPS=100 BATCH=16 PRESET=tiny|small RUN=runs/tiny GAMES=5000 DATA=data/positions.sqlite' 'Benchmark pilota: make benchmark DATA=data/pilot.sqlite' 'STEPS indica passi aggiuntivi. Ctrl+C salva e arresta dopo il batch.'
	@printf '%s\n' 'Ciclo mensile: make cycle MONTHS=2026-09 CYCLE_STEPS=10000 | make cycle-status'
setup:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install torch==2.7.1+cu128 --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple
	$(PY) -m pip install -r requirements.txt
download:
	$(PY) dataset.py download --mib 32
prepare:
	$(PY) dataset.py prepare --max-games $(GAMES) --output "$(DATA)"
test:
	$(PY) -m pytest -q test_policy.py test_benchmark.py test_download_month.py test_monthly_cycle.py test_rating_focus.py test_serve.py test_tactical_lab.py test_tactical_matches.py test_tactical_report.py
train:
	$(PY) train.py train --data "$(DATA)" --steps $(STEPS) --batch-size $(BATCH) --preset $(PRESET) --run $(RUN)
resume:
	$(PY) train.py train --data "$(DATA)" --steps $(STEPS) --batch-size $(BATCH) --preset $(PRESET) --run $(RUN) --resume
status:
	@$(PY) -c "from pathlib import Path; p=Path('$(RUN)/report.json'); print(p.read_text() if p.exists() else 'Nessun rapporto completato')"
predict:
	$(PY) train.py predict --checkpoint "$(RUN)/last.pt" --fen "$(FEN)" --elo "$(ELO)" --top-k "$(TOP_K)"
reference:
	$(PY) fetch_reference.py
benchmark:
	$(PY) benchmark.py --data "$(DATA)" --output "$(OUTPUT)"
download-month:
	$(PY) download_month.py --month "$(MONTH)"
month-status:
	@$(PY) -c "from pathlib import Path; p=Path('data/monthly/$(MONTH).status.json'); print(p.read_text() if p.exists() else 'Download non avviato; controllare anche il log')"
cycle:
	$(PY) monthly_cycle.py run --months "$(MONTHS)" --max-steps "$(CYCLE_STEPS)"
cycle-status:
	$(PY) monthly_cycle.py status

.PHONY: tactical-pilot tactical-status
tactical-pilot:
	$(PY) tactical_lab.py --stockfish "$(abspath ../../vendor/stockfish/stockfish-linux-x86-64-universal)"
	$(PY) tactical_report.py --directory runs/tactical-pilot-v1
tactical-status:
	@$(PY) -c "from pathlib import Path; p=Path('runs/tactical-pilot-v1/RAPPORTO.md'); print(p.read_text() if p.exists() else 'Esperimento non completato: controllare manifest.json, stockfish-labels.json e i log dei bracci in runs/tactical-pilot-v1')"
