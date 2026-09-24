"""Stop only this project's background server, checking against PID reuse."""
import os
import signal
from pathlib import Path

root = Path(__file__).resolve().parents[1]
pid_file = root / '.run/app.pid'
if not pid_file.exists():
    raise SystemExit('Nessun avvio in background registrato. Per un server in primo piano usa Ctrl+C.')
pid = int(pid_file.read_text())
try:
    args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
except FileNotFoundError:
    raise SystemExit('Server già fermo.')
if str(root / '.venv/bin/python').encode() not in args or b'backend.main:app' not in args:
    raise SystemExit('Il PID appartiene a un altro processo: nessun segnale inviato.')
os.kill(pid, signal.SIGTERM)
print('Arresto di Chess Coach richiesto. Le analisi in corso vengono completate.')
