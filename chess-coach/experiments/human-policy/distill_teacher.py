"""Local Maia teacher worker; JSONL stdin/stdout, no HTTP or personal database."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
os.environ.setdefault('MAIA_THREADS','2')
from backend.maia import Maia

teacher = Maia(root/'models/maia3/maia3_simplified.onnx')
for line in sys.stdin:
    try:
        batch = json.loads(line)
        requests = [(item['fen'],item['elo'],item['elo']) for item in batch]
        output = teacher.predict_many(requests)
        print(json.dumps([item['moves'] for item in output]),flush=True)
    except Exception as error:
        print(json.dumps({'error':str(error)}),flush=True)
        break
