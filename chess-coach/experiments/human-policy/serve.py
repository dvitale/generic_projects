"""Local HTTP service for SparringMate: the full move distribution of one checkpoint, loaded once.

GET /health  -> engine, model version, rating bounds.
POST /predict {"fen", "elo", "context"} -> every legal move with its probability (never truncated).
Binds to 127.0.0.1 only; the app verifies legality, probabilities and version before using a move.
"""
import argparse
import hashlib
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import chess
import torch

from policy import Config, Policy, collate, encode, inputs, move_id

ENGINE = "sparringmate-human-policy"
MAX_BODY = 4096


def resolve_checkpoint(value="latest", root=None):
    """Use training order and verified acceptance, never the month name's date order."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    if value != "latest":
        path = Path(value)
        return path if path.is_absolute() else root/path
    ledger_path = root/"data/cycles/ledger.json"
    try:
        ledger = json.loads(ledger_path.read_text())
        month = ledger["active_month"]
        record = ledger["months"][month]
        path = (root/record["checkpoint"]).resolve()
        if (record["state"] != "complete" or not path.is_relative_to((root/"runs/monthly").resolve())
            or path.name != "best.pt"):
            raise ValueError("Checkpoint attivo non valido")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        proof_path = path.parent/"verification.json"
        proof = json.loads(proof_path.read_text())
        if (digest != record["checkpoint_sha256"] or not proof.get("accepted")
            or proof.get("checkpoint_sha256") != digest
            or hashlib.sha256(proof_path.read_bytes()).hexdigest() != record["verification_sha256"]):
            raise ValueError("Verifica del modello attivo non corrispondente")
        return path
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Nessun modello attivo verificato: controlla il ciclo o indica CHECKPOINT esplicitamente") from exc


class Model:
    def __init__(self, checkpoint, device="cpu"):
        path = Path(checkpoint)
        ckpt = torch.load(path, map_location="cpu", weights_only=True)
        self.device = device
        self.bounds = list(ckpt["rating_bounds"])
        self.step = ckpt["step"]
        self.speed = ckpt["dataset"]["speed"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        # Run folder, step and weights hash: a different checkpoint is always a different version.
        self.version = f"{path.parent.name}-step{self.step}-{digest[:12]}"
        self.net = Policy(Config(**ckpt["config"])).to(device)
        self.net.load_state_dict(ckpt["model"])
        self.net.eval()
        self.lock = threading.Lock()

    def health(self):
        return {"engine": ENGINE, "version": self.version, "step": self.step, "ratingBounds": self.bounds,
                "ratingSystem": f"Lichess {self.speed}", "calibrated": False}

    @torch.inference_mode()
    def predict(self, fen, elo):
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise ValueError("FEN non valida") from exc
        if not board.is_valid():
            raise ValueError("FEN non valida")
        if not self.bounds[0] <= elo <= self.bounds[1]:
            raise ValueError(f"Rating fuori dal campione addestrato: {self.bounds}")
        legal = list(board.legal_moves)
        moves = []
        if legal:
            pieces, ep, context = encode(board, elo)
            batch = collate([dict(pieces=pieces, ep=ep, context=context, elo=elo,
                                  legal=[move_id(m) for m in legal], target=0)])
            with self.lock:
                probs = self.net(*inputs(batch, self.device)).float().softmax(-1)[0].cpu().tolist()
            moves = [{"uci": m.uci(), "probability": p} for m, p in zip(legal, probs)]
        return {"engine": ENGINE, "version": self.version, "elo": elo, "moves": moves}


def handler(model):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self.reply(200, model.health())
            if self.path == "/":
                # Opened by hand in a browser: say what this is and where to play.
                return self.reply(200, {**model.health(), "info": "Servizio di mosse per SparringMate, non una pagina da usare: "
                                        "imposta SPARRINGMATE_EXPERIMENTAL_ENGINE in .env e gioca in Gioca su http://localhost:8033"})
            self.reply(404, {"error": "Percorso sconosciuto"})

        def do_POST(self):
            if self.path != "/predict":
                return self.reply(404, {"error": "Percorso sconosciuto"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                return self.reply(413, {"error": "Richiesta troppo grande"})
            try:
                body = json.loads(self.rfile.read(length))
                elo = body["elo"]
                if not isinstance(elo, (int, float)) or not math.isfinite(elo):
                    raise ValueError("Elo non valido")
                self.reply(200, model.predict(str(body["fen"]), elo))
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(422, {"error": str(exc)})

        def log_message(self, format, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="latest", help="latest: ultimo ciclo accettato; oppure percorso esplicito")
    parser.add_argument("--port", type=int, default=8044)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    model = Model(resolve_checkpoint(args.checkpoint), args.device)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(model))
    print(f"{ENGINE} {model.version} su http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
