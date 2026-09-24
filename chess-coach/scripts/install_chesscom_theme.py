"""Optional local installation of the user's requested Chess.com Green/Neo theme."""
import hashlib
import json
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'model-manifests/chesscom-theme.json').read_text())
for item in manifest['files']:
    path=root/'web/public'/item['path']
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']:
        continue
    path.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(item['url'],timeout=20) as response:
        content=response.read()
    if hashlib.sha256(content).hexdigest()!=item['sha256']:
        raise RuntimeError('Asset del tema modificato: verifica prima di aggiornare il manifest.')
    path.write_bytes(content)
print('Tema Green/Neo pronto localmente. Ricompila il frontend con npm run build.')
