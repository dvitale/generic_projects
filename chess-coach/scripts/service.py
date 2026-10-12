"""WSL/Linux lifecycle commands. Only signal this checkout's verified Uvicorn process."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class Service:
    def __init__(self, root=ROOT, port=8033, stop_timeout=60):
        self.root = Path(root).resolve()
        self.port = port
        self.stop_timeout = stop_timeout
        self.run = self.root / '.run'
        suffix = '' if port == 8033 else f'-{port}'
        self.pid_file = self.run / f'app{suffix}.pid'
        self.log_file = self.run / f'app{suffix}.log'
        self.url = f'http://127.0.0.1:{port}'

    def matches(self, pid):
        try:
            proc = Path(f'/proc/{pid}')
            args = proc.joinpath('cmdline').read_bytes().decode().strip('\0').split('\0')
            if proc.joinpath('cwd').resolve() != self.root:
                return False
            if args[1:4] != ['-m', 'uvicorn', 'backend.main:app'] or '--reload' in args:
                return False
            executable = Path(args[0])
            if not executable.is_absolute():
                executable = self.root / executable
            return (executable.resolve() == (self.root / '.venv/bin/python').resolve()
                    and args[args.index('--port')+1] == str(self.port)
                    and args[args.index('--host')+1] == '127.0.0.1')
        except (OSError, RuntimeError, UnicodeError, ValueError, IndexError):
            return False

    def processes(self):
        # Discover older launches as well; a stale/reused PID file is never authority to kill.
        return [int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit() and self.matches(int(p.name))]

    def healthy(self):
        try:
            with urllib.request.urlopen(self.url + '/api/health', timeout=1) as response:
                return response.status == 200 and json.load(response).get('status') == 'ok'
        except (OSError, ValueError):
            return False

    def port_busy(self):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', self.port))
                return False
            except OSError:
                return True

    def remember(self, pid):
        temporary = self.pid_file.with_suffix('.tmp')
        temporary.write_text(str(pid) + '\n')
        temporary.replace(self.pid_file)

    def status(self):
        pids = self.processes()
        if pids:
            state = 'attivo e pronto' if self.healthy() else 'processo presente, servizio non pronto'
            print(f'SparringMate: {state} (PID {", ".join(map(str,pids))}).')
        elif self.port_busy():
            print(f'SparringMate non gestito da questi comandi: porta {self.port} occupata da un altro processo.')
        else:
            print('SparringMate: fermo.')
        print(f'Indirizzo: http://localhost:{self.port}\nLog: {self.log_file}')

    def start(self):
        pids = self.processes()
        if pids:
            self.status()
            if len(pids) != 1 or not self.healthy():
                raise RuntimeError('Nessun secondo server avviato. Controlla il log o usa make restart.')
            self.remember(pids[0])
            return
        if self.port_busy():
            raise RuntimeError(f'Porta {self.port} occupata: nessun processo arrestato. Scegli PORT oppure ferma il servizio che la usa.')
        python = self.root / '.venv/bin/python'
        if not python.is_file():
            raise RuntimeError('Ambiente Python mancante: esegui scripts/install.sh come indicato nel README.')
        if not (self.root / 'web/dist/index.html').is_file():
            print('Preparazione dell’interfaccia…', flush=True)
            subprocess.run(['npm','run','build'], cwd=self.root/'web', check=True)
        with self.log_file.open('a') as log:
            process = subprocess.Popen([str(python), '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(self.port)],
                cwd=self.root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        self.remember(process.pid)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.pid_file.unlink(missing_ok=True)
                raise RuntimeError(f'Avvio fallito. Leggi {self.log_file}')
            if self.healthy():
                self.status()
                return
            time.sleep(.2)
        raise RuntimeError(f'Avvio ancora non pronto (PID {process.pid}). Controlla make status e {self.log_file}; nessun secondo server avviato.')

    def stop(self):
        pids = self.processes()
        if not pids:
            self.pid_file.unlink(missing_ok=True)
            print('SparringMate: già fermo. Nessun segnale inviato ad altri processi.')
            return
        if len(pids) > 1:
            raise RuntimeError('Più processi corrispondenti: arresto non eseguito; controlla make status.')
        pid = pids[0]
        # Verify again immediately before signaling; never trust app.pid alone.
        if not self.matches(pid):
            raise RuntimeError('Il processo è cambiato: arresto non eseguito.')
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            raise RuntimeError('Il server appartiene a un altro utente: esegui make stop con l’utente che lo ha avviato.') from None
        print('Arresto richiesto. Attendo il completamento delle analisi in corso…', flush=True)
        deadline = time.monotonic() + self.stop_timeout
        while self.matches(pid):
            if time.monotonic() >= deadline:
                raise RuntimeError('Server ancora in arresto: nessuna terminazione forzata e nessun riavvio. Riprova make status, poi make restart quando sarà fermo.')
            time.sleep(.2)
        self.pid_file.unlink(missing_ok=True)
        print('SparringMate: fermo. Partite e allenamenti conservati.')

    def logs(self):
        if not self.log_file.exists():
            print('Nessun log disponibile.')
            return
        subprocess.run(['tail','-n','60',str(self.log_file)],check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['start','status','restart','stop','logs'])
    parser.add_argument('--port', type=int, default=8033)
    parser.add_argument('--stop-timeout', type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.stop_timeout < 1:
        parser.error('Porta o tempo di attesa non valido')
    service = Service(port=args.port, stop_timeout=args.stop_timeout)
    try:
        service.run.mkdir(exist_ok=True)
        with (service.run / f'service-{args.port}.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.command == 'restart':
                service.stop()
                service.start()
            else:
                getattr(service,args.command)()
        return 0
    except BlockingIOError:
        print('Un altro comando è già in corso per questa porta. Attendi e riprova.',file=sys.stderr)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'SparringMate: {exc}',file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
