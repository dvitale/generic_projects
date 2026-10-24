#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p var
chmod 700 var
exec 9>var/service.lock
flock -x 9
pidfile=var/proxyman.pid
running() {
 [ -f "$pidfile" ] || return 1
 pid=$(cat "$pidfile")
 case "$pid" in ''|*[!0-9]*) return 1;; esac
 kill -0 "$pid" 2>/dev/null || return 1
 actual=$(readlink "/proc/$pid/exe" 2>/dev/null || true)
 expected="$(pwd -P)/bin/proxyman"
 [ "$actual" = "$expected" ] || [ "$actual" = "$expected (deleted)" ]
}
case "${1:-status}" in
 start)
  if running; then echo "Proxyman già attivo (PID $pid)"; exit 0; fi
  if [ -f .env ]; then set -a; . ./.env; set +a; fi
  : "${PROXYMAN_PASSWORD:?Crea .env da .env.example e imposta PROXYMAN_PASSWORD}"
  set -- -listen "${PROXYMAN_LISTEN:-127.0.0.1:8080}" -data "$(pwd -P)/var/hosts.json" -config "${PROXYMAN_CONFIG:-/etc/nginx/conf.d/proxyman.conf}" -nginx "${PROXYMAN_NGINX:-/usr/sbin/nginx}"
  if [ "${PROXYMAN_APPLY:-0}" = 1 ]; then set -- "$@" -apply; fi
  nohup ./bin/proxyman "$@" >>var/proxyman.log 2>&1 9>&- &
  echo "$!" >"$pidfile"
  sleep 1
  if running; then echo "Proxyman avviato: http://${PROXYMAN_LISTEN:-127.0.0.1:8080} (PID $pid)"
  else cat var/proxyman.log; exit 1; fi
  ;;
 stop)
  if ! running; then echo "Proxyman non attivo"; rm -f "$pidfile"; exit 0; fi
  kill -TERM "$pid"
  count=0
  while running; do
   if [ "$count" -ge 50 ]; then echo "Arresto non completato: controllare il processo $pid"; exit 1; fi
   sleep 1; count=$((count+1))
  done
  rm -f "$pidfile"
  echo "Proxyman arrestato"
  ;;
 status)
  if running; then echo "Proxyman attivo (PID $pid)"
  else echo "Proxyman non attivo"; exit 3; fi
  ;;
 assert-stopped)
  if running; then echo "Arresta Proxyman prima di clean"; exit 1; fi
  ;;
 *) echo "Uso: $0 start|stop|status"; exit 2;;
esac
