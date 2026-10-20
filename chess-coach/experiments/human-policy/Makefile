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

.PHONY: help setup download prepare test train resume status predict reference benchmark
help:
	@printf '%s\n' 'Modello sperimentale di mosse umane — GPU locale' 'make setup | download | prepare | test | train | resume | status | reference | benchmark' 'make predict FEN="..." ELO=800' 'Opzioni: STEPS=100 BATCH=16 PRESET=tiny|small RUN=runs/tiny GAMES=5000 DATA=data/positions.sqlite' 'Benchmark pilota: make benchmark DATA=data/pilot.sqlite' 'STEPS indica passi aggiuntivi. Ctrl+C salva e arresta dopo il batch.'
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
	$(PY) -m pytest -q test_policy.py test_benchmark.py
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
