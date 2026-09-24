#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8033 --reload &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM
cd web
npm run dev
