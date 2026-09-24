"""Interactive local setup; the key is never echoed or sent to the browser."""
import getpass
import json
import os
from pathlib import Path

root=Path(__file__).resolve().parents[1]
key=getpass.getpass('Chiave API DeepSeek (input nascosto): ').strip()
if not key:
    raise SystemExit('Nessuna modifica: chiave vuota.')
folder=root/'.secrets'
folder.mkdir(mode=0o700,exist_ok=True)
folder.chmod(0o700)
path=folder/'deepseek.json'
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
os.fchmod(fd,0o600)
with os.fdopen(fd,'w') as handle:
    json.dump({'api_key':key,'model':'deepseek-flash'},handle)
print('DeepSeek configurato nel backend. La chiave non viene inclusa in Git.')
