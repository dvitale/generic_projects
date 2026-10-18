#!/usr/bin/env bash
# Update the public instance (see deploy/SERVER.md): build the interface, sync the code,
# refresh dependencies, apply changed systemd/nginx files, restart and check health.
# SSH uses your key; if SSHPASS is set in the environment, sshpass supplies the password instead.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

HOST="${DEPLOY_HOST:-root@sparringmate.u-s.it}"
DIR="${DEPLOY_DIR:-/opt/sparringmate}"
URL="${DEPLOY_URL:-https://sparringmate.u-s.it}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
WRAP=()
if [ -n "${SSHPASS:-}" ]; then WRAP=(sshpass -e); fi
remote() { "${WRAP[@]}" ssh "${SSH_OPTS[@]}" "$HOST" "$@"; }

if [ -n "$(git status --porcelain -- .)" ]; then
  echo "Attenzione: modifiche non committate, vengono pubblicate così come sono." >&2
fi

if [ "${SKIP_BUILD:-0}" != 1 ]; then
  echo "== Compilo l'interfaccia"
  (cd web && npm run build >/dev/null)
fi

echo "== Sincronizzo $DIR su $HOST"
# Server-only state is excluded, so --delete never touches it: credentials, data, venv and the locally built Stockfish.
# Code is owned by the remote user (root) and never group/world-writable, whatever the local checkout's modes are.
"${WRAP[@]}" rsync -a --delete --no-owner --no-group --chmod=Dgo-w,Fgo-w -e "ssh ${SSH_OPTS[*]}" \
  --exclude='/.env' --exclude='/.env.*' --exclude='/.secrets/' --exclude='/data/' --exclude='/.venv/' \
  --exclude='/engine/' --exclude='/.run/' --exclude='/.pytest_cache/' --exclude='__pycache__/' \
  --exclude='/web/node_modules/' --exclude='/web/test-results/' --exclude='/web/playwright-report/' \
  --exclude='/vendor/*.tar.gz' --exclude='.git' \
  ./ "$HOST:$DIR/"

# data/ is server-only, except the read-only problem database: it is built locally (make puzzles) and copied as is.
if [ -f data/lichess_puzzles.sqlite3 ]; then
  echo "== Copio il database dei problemi"
  "${WRAP[@]}" rsync -a --no-owner --no-group --chmod=F644 -e "ssh ${SSH_OPTS[*]}" data/lichess_puzzles.sqlite3 "$HOST:$DIR/data/lichess_puzzles.sqlite3"
fi

echo "== Dipendenze, servizio e nginx"
remote "DIR='$DIR' bash -s" <<'EOF'
set -euo pipefail
cd "$DIR"
chown -R sparringmate:sparringmate data .env
uv pip install --quiet --python .venv/bin/python -r requirements.lock

if ! cmp -s deploy/sparringmate.service /etc/systemd/system/sparringmate.service; then
  cp deploy/sparringmate.service /etc/systemd/system/sparringmate.service
  systemctl daemon-reload
  echo "unit systemd aggiornata"
fi
systemctl restart sparringmate
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8033/api/health >/dev/null && break; sleep 1; done
curl -sf http://127.0.0.1:8033/api/health >/dev/null || { journalctl -u sparringmate -n 30 --no-pager; exit 1; }

conf=/etc/nginx/sites-enabled/sparringmate.conf
if ! cmp -s deploy/sparringmate.conf "$conf"; then
  backup="/root/sparringmate.conf.bak-$(date +%Y%m%d-%H%M%S)"
  cp -p "$conf" "$backup"
  cp deploy/sparringmate.conf "$conf"
  if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "nginx aggiornato (copia precedente: $backup)"
  else
    cp -p "$backup" "$conf"
    nginx -t
    echo "nginx: configurazione nuova non valida, ripristinata la precedente" >&2
    exit 1
  fi
fi
EOF

echo "== Verifica pubblica"
curl -sf "$URL/api/health" >/dev/null || { echo "$URL/api/health non risponde" >&2; exit 1; }
status=$(curl -s -o /dev/null -w '%{http_code}' "$URL/api/games")
[ "$status" = 401 ] || { echo "Attesa 401 senza login su /api/games, ricevuto $status" >&2; exit 1; }
echo "Pubblicato: $URL"
