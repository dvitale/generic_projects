"""Fetch pinned runtime assets without training or model conversion."""
import hashlib
import json
import os
import platform
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def download(url, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        return
    temporary = target.with_suffix(target.suffix + '.download')
    urllib.request.urlretrieve(url, temporary)
    if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
        temporary.unlink()
        raise RuntimeError('Checksum non corrispondente: ' + url)
    temporary.replace(target)
    print('Verificato:', target.relative_to(ROOT))


manifest = json.loads((ROOT / 'model-manifests/maia-browser.json').read_text())
for asset in manifest['files']:
    if asset['path'].startswith('public/'):
        download(asset['url'], ROOT / 'web' / asset['path'], asset['sha256'])

if not os.environ.get('STOCKFISH_PATH'):
    if platform.machine() not in ('x86_64', 'AMD64'):
        raise RuntimeError('Fornisci STOCKFISH_PATH per questa architettura.')
    archive = ROOT / 'vendor/stockfish-19.tar.gz'
    download('https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-linux-x86-64-universal.tar.gz', archive,
             '9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f')
    vendor = (ROOT / 'vendor').resolve()
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            target = (vendor / member.name).resolve()
            if not target.is_relative_to(vendor) or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise RuntimeError('Percorso non consentito nell’archivio Stockfish')
        tar.extractall(vendor)
