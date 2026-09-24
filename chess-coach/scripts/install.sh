#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
python3 scripts/download_assets.py
(cd web && npm ci && npm run build)
echo 'Installazione completata. Avvia con ./start.sh'
