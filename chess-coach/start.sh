#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
if [ ! -x .venv/bin/python ]; then
  echo 'Ambiente Python mancante: leggi README.md.' >&2
  exit 1
fi
if [ ! -f web/dist/index.html ]; then
  (cd web && npm run build)
fi
echo "Chess Coach: http://localhost:${PORT:-8033}"
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8033}"
