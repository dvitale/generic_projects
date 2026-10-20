"""Fetch a pinned official reference into the ignored laboratory directory only."""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

CODE_COMMIT = "1e13597c42d4858b7cfd7cfdae01e297263364b2"
REVISION = "b6559de2398d7140b985f28fd2c19fb5e47ddabe"
SHA256 = "ba14208b2992d85502f5fb501934abf6aaaeb355e9f3fdf90e326911f562524f"
REPOSITORY = "https://github.com/CSSLab/maia3"


def fetch(folder=Path("baselines")):
    folder.mkdir(parents=True, exist_ok=True)
    code = folder / "maia3"
    if not code.exists():
        subprocess.run(["git", "init", str(code)], check=True)
        subprocess.run(["git", "-C", str(code), "fetch", "--depth", "1", REPOSITORY, CODE_COMMIT], check=True)
        subprocess.run(["git", "-C", str(code), "checkout", "--detach", "FETCH_HEAD"], check=True)
    commit = subprocess.check_output(["git", "-C", str(code), "rev-parse", "HEAD"], text=True).strip()
    if commit != CODE_COMMIT:
        raise ValueError("Versione del riferimento diversa: nessuna modifica automatica")
    url = f"https://huggingface.co/UofTCSSLab/Maia3-5M/resolve/{REVISION}/maia3-5m.pt"
    target = folder / "maia3-5m.pt"
    if not target.exists():
        part = target.with_suffix(".part")
        count, digest = 0, hashlib.sha256()
        with urllib.request.urlopen(url, timeout=60) as response, part.open("wb") as out:
            while chunk := response.read(1024**2):
                count += len(chunk)
                if count > 64 * 1024**2:
                    raise ValueError("Download oltre il limite previsto di 64 MiB")
                out.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != SHA256:
            raise ValueError("SHA256 del riferimento inatteso; pesi non utilizzabili")
        part.replace(target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Pesi esistenti diversi dal riferimento fissato")
    meta = dict(source=url, revision=REVISION, sha256=SHA256, bytes=target.stat().st_size,
                repository=REPOSITORY, code_commit=commit,
                purpose="Riferimento esterno nel solo laboratorio; nessuna integrazione nell'app")
    target.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    print(json.dumps(fetch(), indent=2))
