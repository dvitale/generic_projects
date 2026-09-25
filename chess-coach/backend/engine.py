"""Stockfish boundary: keep every comparison in the decision maker's perspective."""
import os
import threading
from pathlib import Path

import chess
import chess.engine

ROOT = Path(__file__).resolve().parents[1]


def stockfish_path():
    configured = os.environ.get("STOCKFISH_PATH")
    if configured:
        return configured
    candidates = list((ROOT / "vendor").glob("**/stockfish-ubuntu*"))
    candidates += list((ROOT / "vendor").glob("**/stockfish-linux*"))
    candidates += list((ROOT / "vendor").glob("**/stockfish"))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK) and not candidate.name.endswith(".tar.gz"):
            return str(candidate)
    if Path("/usr/games/stockfish").exists():
        return "/usr/games/stockfish"
    raise RuntimeError("Stockfish non trovato. Imposta STOCKFISH_PATH.")


class Evaluator:
    def __init__(self):
        self.lock = threading.RLock()
        self.engine = None
        self.name = "Non avviato"

    def start(self):
        with self.lock:
            if self.engine is None:
                self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path(), timeout=30)
                self.engine.configure({"Threads": 2, "Hash": 64})
                self.name = self.engine.id.get("name", "Stockfish")

    def close(self):
        with self.lock:
            if self.engine:
                self.engine.quit()
                self.engine = None

    def _analyse(self, board, nodes, **kwargs):
        # Callers hold the reentrant lock throughout analysis and comparison.
        self.start()
        try:
            return self.engine.analyse(board, chess.engine.Limit(nodes=nodes), **kwargs)
        except chess.engine.EngineTerminatedError:
            self.engine = None
            self.start()
            return self.engine.analyse(board, chess.engine.Limit(nodes=nodes), **kwargs)

    @staticmethod
    def _format(board, info):
        score = info["score"].pov(board.turn)
        cursor = board.copy()
        san, uci = [], []
        for step in info.get("pv", [])[:8]:
            if step not in cursor.legal_moves:
                break
            san.append(cursor.san(step))
            uci.append(step.uci())
            cursor.push(step)
        return {"cp": score.score(mate_score=100000), "mate": score.mate(),
                "pv": uci, "san": san, "depth": info.get("depth", 0),
                "nodes": info.get("nodes", 0), "perspective": "w" if board.turn else "b"}

    def evaluate(self, board, move=None, nodes=12000):
        with self.lock:
            kwargs = {"root_moves": [move]} if move else {}
            return self._format(board, self._analyse(board, nodes, **kwargs))

    def candidates(self, board, nodes=12000, count=3):
        with self.lock:
            count = min(count, board.legal_moves.count())
            if count < 1:
                return []
            # MultiPV ranks distinct root moves, not subsequent moves in one variation.
            infos = self._analyse(board, nodes * count, multipv=count)
            return [self._format(board, info) for info in infos]

    def compare_candidates(self, board, played, nodes=24000):
        with self.lock:
            choices = self.candidates(board, nodes=nodes)
            actual = next((c for c in choices if c["pv"] and c["pv"][0] == played.uci()), None)
            if actual is None:
                actual = self.evaluate(board, played, nodes)
            if actual["cp"] > choices[0]["cp"] + 30:
                choices = self.candidates(board, nodes=nodes * 2)
                actual = next((c for c in choices if c["pv"] and c["pv"][0] == played.uci()), actual)
            best = choices[0]
            return best, actual, max(0, best["cp"] - actual["cp"]), choices

    def compare(self, board, played, nodes=24000):
        # One lock prevents interleaved jobs from changing the engine's state mid-comparison.
        with self.lock:
            best = self.evaluate(board, nodes=nodes)
            actual = best if best["pv"] and best["pv"][0] == played.uci() else self.evaluate(board, played, nodes)
            if actual["cp"] > best["cp"] + 30:
                best = self.evaluate(board, nodes=nodes * 2)
            return best, actual, max(0, best["cp"] - actual["cp"])


evaluator = Evaluator()
