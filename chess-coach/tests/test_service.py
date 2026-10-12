import os
import signal
import socket
from pathlib import Path

import pytest
from scripts.service import Service


def test_stale_pid_never_signals_an_unrelated_process(tmp_path, monkeypatch):
    service=Service(tmp_path)
    service.run.mkdir()
    service.pid_file.write_text(str(os.getpid()))
    assert not service.matches(os.getpid())
    def forbidden(*args):
        pytest.fail('Must not signal the unrelated PID from the stale file')
    monkeypatch.setattr(os,'kill',forbidden)
    service.stop()
    assert not service.pid_file.exists()


def test_busy_port_refuses_start_without_signaling(tmp_path, monkeypatch):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen()
        service=Service(tmp_path,port=listener.getsockname()[1])
        monkeypatch.setattr(service,'processes',lambda:[])
        with pytest.raises(RuntimeError,match='occupata'):
            service.start()


def test_stop_timeout_does_not_force_kill_or_delete_pid(tmp_path,monkeypatch):
    service=Service(tmp_path,stop_timeout=1)
    service.run.mkdir();service.pid_file.write_text('123')
    monkeypatch.setattr(service,'processes',lambda:[123])
    monkeypatch.setattr(service,'matches',lambda pid:True)
    signals=[];monkeypatch.setattr(os,'kill',lambda pid,sig:signals.append((pid,sig)))
    ticks=iter([0,2]);monkeypatch.setattr('scripts.service.time.monotonic',lambda:next(ticks))
    with pytest.raises(RuntimeError,match='nessuna terminazione forzata'):
        service.stop()
    assert signals==[(123,signal.SIGTERM)] and service.pid_file.exists()
