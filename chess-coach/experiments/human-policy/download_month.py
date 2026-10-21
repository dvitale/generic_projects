"""Resumable, checksummed monthly Lichess download, confined to the research lab."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import time
import urllib.error
import urllib.request

BASE = "https://database.lichess.org/standard/"
GIB = 1024**3
CHUNK = 1024**2


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp.replace(path)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_metadata(month):
    if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
        raise ValueError("Mese non valido: usare YYYY-MM")
    name = f"lichess_db_standard_rated_{month}.pgn.zst"
    with urllib.request.urlopen(BASE + "sha256sums.txt", timeout=45) as response:
        lines = response.read(1024**2).decode().splitlines()
    matches = [line.split()[0] for line in lines
               if len(line.split()) == 2 and line.split()[1].lstrip("*") == name]
    if len(matches) != 1 or not re.fullmatch(r"[a-f0-9]{64}", matches[0]):
        raise ValueError("Checksum ufficiale assente o ambiguo")
    url = BASE + name
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=45) as response:
        size = int(response.headers["Content-Length"])
        etag = response.headers.get("ETag")
    if not 0 < size <= 60 * GIB:
        raise ValueError("Dimensione mensile fuori dal limite previsto di 60 GiB")
    return dict(month=month, name=name, url=url, bytes=size, sha256=matches[0], etag=etag,
                checksum_source=BASE + "sha256sums.txt", license="CC0")


def check_space(folder, host_disk, remaining=0, reserve=10 * GIB):
    # WSL's virtual free capacity can exceed actual host free space.
    for path in (folder, host_disk):
        if shutil.disk_usage(path).free < remaining + reserve:
            raise RuntimeError(f"Spazio insufficiente su {path}: conservati almeno {reserve/GIB:.0f} GiB liberi")


def download(month, folder, host_disk, reserve=10 * GIB):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    lock_path = folder / f"{month}.lock"
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        meta = remote_metadata(month)
        target = folder / meta["name"]
        part = target.with_suffix(target.suffix + ".part")
        meta_path = folder / f"{month}.manifest.json"
        status_path = folder / f"{month}.status.json"
        if meta_path.exists() and json.loads(meta_path.read_text()) != meta:
            raise ValueError("Archivio remoto cambiato: ripresa interrotta, file conservati")
        if part.exists() and not meta_path.exists():
            raise ValueError("File parziale senza manifest: non posso verificarne la provenienza")
        write_json(meta_path, meta)
        started = time.monotonic()
        initial = part.stat().st_size if part.exists() else 0
        last_report = 0.

        def status(state, error=None):
            current = target.stat().st_size if target.exists() else part.stat().st_size if part.exists() else 0
            elapsed = time.monotonic() - started
            rate = max(0, current - initial) / max(elapsed, .001)
            value = dict(state=state, month=month, pid=os.getpid(), bytes=current,
                         total_bytes=meta["bytes"], percent=100 * current / meta["bytes"],
                         session_mib_per_second=rate/CHUNK,
                         updated_utc=datetime.now(timezone.utc).isoformat(),
                         destination=str(target.resolve()), error=error)
            write_json(status_path, value)
            print(json.dumps(value), flush=True)

        try:
            if target.exists():
                status("verifying")
                if target.stat().st_size != meta["bytes"] or checksum(target) != meta["sha256"]:
                    raise ValueError("Archivio finale esistente non valido: non sovrascritto")
                status("complete")
                return
            if initial > meta["bytes"]:
                raise ValueError("File parziale più grande dell'archivio remoto")
            check_space(folder, host_disk, meta["bytes"] - initial, reserve)
            status("downloading")
            for attempt in range(6):
                offset = part.stat().st_size if part.exists() else 0
                if offset == meta["bytes"]:
                    break
                headers = {"User-Agent": "SparringMateResearch/0.2", "Accept-Encoding": "identity"}
                if offset:
                    headers["Range"] = f"bytes={offset}-"
                    if meta["etag"]:
                        headers["If-Range"] = meta["etag"]
                request = urllib.request.Request(meta["url"], headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=45) as response:
                        if offset and (response.status != 206 or
                            response.headers.get("Content-Range") != f"bytes {offset}-{meta['bytes']-1}/{meta['bytes']}"):
                            raise ValueError("Il server non conferma la ripresa esatta: file parziale conservato")
                        if not offset and response.status != 200:
                            raise ValueError("Risposta inattesa al download completo")
                        if int(response.headers["Content-Length"]) != meta["bytes"] - offset:
                            raise ValueError("Dimensione della risposta inattesa")
                        with part.open("ab") as out:
                            while chunk := response.read(CHUNK):
                                if offset + len(chunk) > meta["bytes"]:
                                    raise ValueError("Risposta oltre la dimensione prevista")
                                if time.monotonic() - last_report >= 5:
                                    check_space(folder, host_disk, reserve=reserve)
                                    status("downloading")
                                    last_report = time.monotonic()
                                out.write(chunk)
                                offset += len(chunk)
                    if offset != meta["bytes"]:
                        raise http.client.IncompleteRead(b"", meta["bytes"] - offset)
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as exc:
                    if attempt == 5:
                        raise
                    status("retrying", str(exc))
                    time.sleep(min(30, 2 ** attempt))
            status("verifying")
            if part.stat().st_size != meta["bytes"] or checksum(part) != meta["sha256"]:
                raise ValueError("Checksum non corrispondente: archivio non utilizzabile, file conservato")
            part.replace(target)
            status("complete")
        except BaseException as exc:
            status("interrupted" if isinstance(exc, KeyboardInterrupt) else "failed", str(exc))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="2026-09")
    parser.add_argument("--host-disk", default="/mnt/c")
    parser.add_argument("--reserve-gib", type=int, default=10)
    args = parser.parse_args()
    if args.reserve_gib < 1:
        parser.error("Mantenere almeno 1 GiB di riserva")
    def stop(signum, frame):
        raise KeyboardInterrupt("Arresto richiesto; ripresa disponibile")
    signal.signal(signal.SIGTERM, stop)
    download(args.month, Path(__file__).resolve().parent / "data/monthly", args.host_disk,
             args.reserve_gib * GIB)
