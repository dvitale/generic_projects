"""Maia3 on the server: the browser's ONNX model, encoding and move mapping, for batch work."""
import json
import os
import threading
from pathlib import Path

import chess
import numpy as np

from .engine import ROOT

MODEL = Path(os.environ.get('MAIA_MODEL_PATH', ROOT / 'web' / 'public' / 'maia3' / 'maia3_simplified.onnx'))
MAPPING = ROOT / 'web' / 'src' / 'engine' / 'data' / 'all_moves_maia3.json'
BATCH = 32  # Beyond 32 positions a run gains no speed and the memory arena keeps growing.
MOVES = 4352


def mirror(uci):
    return uci[0] + str(9 - int(uci[1])) + uci[2] + str(9 - int(uci[3])) + uci[4:]


class Maia:
    def __init__(self, model=MODEL):
        self.model, self.lock, self.session, self.indices = Path(model), threading.Lock(), None, None

    def available(self):
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return False
        return self.model.is_file() and MAPPING.is_file()

    def encode(self, fen):
        """Same layout as encode() in web/src/engine/maia.ts: the side to move always plays up the board."""
        if self.indices is None:
            self.indices = json.loads(MAPPING.read_text())
        board = chess.Board(fen)
        black = board.turn == chess.BLACK
        tokens = np.zeros((64, 12), np.float32)
        for square, piece in board.piece_map().items():
            channel = 'PNBRQKpnbrqk'.index(piece.symbol())
            if black:
                channel, square = (channel + 6) % 12, chess.square_mirror(square)
            tokens[square, channel] = 1
        legal = [(m.uci(), self.indices[mirror(m.uci()) if black else m.uci()]) for m in board.legal_moves]
        return tokens, legal, black

    def load(self):
        with self.lock:
            if self.session is None:
                import onnxruntime as ort
                options = ort.SessionOptions()
                # onnxruntime 1.23+ crashes building this model with ORT_ENABLE_ALL (NchwcTransformer together
                # with MatmulTransposeFusion); EXTENDED is as fast here and gives the same probabilities.
                options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
                options.intra_op_num_threads = int(os.environ.get('MAIA_THREADS', '0'))
                self.session = ort.InferenceSession(str(self.model), options, providers=['CPUExecutionProvider'])
        return self.session

    def predict_many(self, requests):
        """requests: (fen, self_elo, opponent_elo) triples. Returns one prediction per request, in order."""
        encoded = [self.encode(fen) for fen, _, _ in requests]
        results: list = [None] * len(requests)
        live = [i for i, e in enumerate(encoded) if e[1]]
        for i in set(range(len(requests))) - set(live):
            results[i] = {'moves': [], 'whiteExpectedScore': 0.5, 'whiteOutcome': {'win': 0, 'draw': 1, 'loss': 0}}
        session = self.load()
        for start in range(0, len(live), BATCH):
            chunk = live[start:start + BATCH]
            feeds = {'tokens': np.stack([encoded[i][0] for i in chunk]),
                     'elo_self': np.array([requests[i][1] for i in chunk], np.float32),
                     'elo_oppo': np.array([requests[i][2] for i in chunk], np.float32)}
            with self.lock:
                moves, values = session.run(['logits_move', 'logits_value'], feeds)
            if moves.shape[1] != MOVES or values.shape[1] != 3 or not (np.isfinite(moves).all() and np.isfinite(values).all()):
                raise RuntimeError('Output Maia non valido')
            for row, i in enumerate(chunk):
                _, legal, black = encoded[i]
                logits = moves[row, [index for _, index in legal]]
                p = np.exp(logits - logits.max()); p /= p.sum()
                v = np.exp(values[row] - values[row].max()); v /= v.sum()
                # Value logits are loss, draw, win for the side to move.
                own = {'win': float(v[2]), 'draw': float(v[1]), 'loss': float(v[0])}
                expected = own['win'] + own['draw'] / 2
                results[i] = {'moves': sorted(({'uci': uci, 'probability': float(q)} for (uci, _), q in zip(legal, p)), key=lambda m: -m['probability']),
                              'whiteExpectedScore': 1 - expected if black else expected,
                              'whiteOutcome': {'win': own['loss'], 'draw': own['draw'], 'loss': own['win']} if black else own}
        return results

    def predict(self, fen, self_elo, opponent_elo):
        return self.predict_many([(fen, self_elo, opponent_elo)])[0]


maia = Maia()
