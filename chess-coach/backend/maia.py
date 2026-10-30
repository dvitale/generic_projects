"""Maia3 on the server, the only place it runs: the interface asks /api/maia/predict, batch work calls it directly."""
import json
import os
import random
import threading
import time
from collections import OrderedDict
from pathlib import Path

import chess
import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import ROOT

MODEL = Path(os.environ.get('MAIA_MODEL_PATH', ROOT / 'models' / 'maia3' / 'maia3_simplified.onnx'))
MAPPING = Path(__file__).parent / 'data' / 'all_moves_maia3.json'
# Recorded with each new Maia game: the model and the weights downloaded from maiachess.com.
MODEL_VERSION = 'maia3_simplified.onnx@official-browser-2026-09-23'
BATCH = 32  # Beyond 32 positions a run gains no speed and the memory arena keeps growing.
MOVES = 4352
CACHE = 4096  # Predictions kept for the interface: browsing a game asks the same positions again.
REQUEST_LIMIT = 64
# A low temperature replays the same opening every game: up to this move number, sharpened modes draw
# with OPENING (temperature 1, rare moves still cut) so games diverge before their own rule applies.
OPENING_MOVES = 8
OPENING = (1, 0.9)
# Move selection modes for Play, fixed per game: (temperature, top-p, sharpened only after the opening).
# Keys match MAIA_SELECTIONS in backend/opponents.py.
SELECTIONS = {'sample-full-distribution': (1, 1, False), 'temperature-0.7-top-p-0.95': (0.7, 0.95, True),
              'temperature-0.4-top-p-0.8': (0.4, 0.8, True), 'top-move': (0, 1, False)}


def choose(moves, selection, move_number, seed):
    """Sharpen the distribution with the temperature, keep the smallest set reaching top-p, then draw with the seed.

    moves: Maia's moves sorted by probability. Returns (uci, probability) of the chosen move, or None without moves."""
    if not moves:
        return None
    temperature, top_p, sharpened = SELECTIONS.get(selection, SELECTIONS['sample-full-distribution'])
    if sharpened and move_number <= OPENING_MOVES:
        temperature, top_p = OPENING
    if temperature == 0:
        return moves[0]['uci'], moves[0]['probability']
    top = moves[0]['probability']
    weights = [(m['probability'] / top) ** (1 / temperature) if top > 0 else 1 for m in moves]
    total, cumulative, kept = sum(weights), 0, 0
    while kept < len(moves) and (kept == 0 or cumulative < top_p * total - 1e-12):
        cumulative += weights[kept]
        kept += 1
    draw = random.Random(seed).random() * cumulative
    for move, weight in zip(moves[:kept], weights):
        draw -= weight
        if draw < 0:
            return move['uci'], move['probability']
    return moves[kept - 1]['uci'], moves[kept - 1]['probability']


def mirror(uci):
    return uci[0] + str(9 - int(uci[1])) + uci[2] + str(9 - int(uci[3])) + uci[4:]


class Maia:
    def __init__(self, model=MODEL):
        self.model, self.lock, self.session, self.indices = Path(model), threading.Lock(), None, None
        # Interactive requests waiting for the session: background batches step aside between chunks.
        self.waiting, self.cache, self.cache_lock = 0, OrderedDict(), threading.Lock()

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

    def predict_many(self, requests, interactive=False):
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
            if interactive:
                with self.cache_lock:
                    self.waiting += 1
            else:
                while self.waiting:
                    time.sleep(0.005)
            try:
                with self.lock:
                    moves, values = session.run(['logits_move', 'logits_value'], feeds)
            finally:
                if interactive:
                    with self.cache_lock:
                        self.waiting -= 1
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

    def predict_cached(self, requests):
        """The interface's requests, with SAN for each move; repeated positions come from the cache."""
        with self.cache_lock:
            found = {key: self.cache[key] for key in requests if key in self.cache}
            for key in found:
                self.cache.move_to_end(key)
        missing = list(dict.fromkeys(key for key in requests if key not in found))
        for key, prediction in zip(missing, self.predict_many(missing, interactive=True) if missing else []):
            board = chess.Board(key[0])
            prediction = {**prediction, 'moves': [{**m, 'san': board.san(chess.Move.from_uci(m['uci']))} for m in prediction['moves']]}
            found[key] = prediction
            with self.cache_lock:
                self.cache[key] = prediction
                while len(self.cache) > CACHE:
                    self.cache.popitem(last=False)
        return [found[key] for key in requests]


maia = Maia()


class Position(BaseModel):
    fen: str = Field(max_length=100)
    selfElo: int = Field(ge=100, le=4000)
    opponentElo: int = Field(ge=100, le=4000)


class PredictBody(BaseModel):
    positions: list[Position] = Field(min_length=1, max_length=REQUEST_LIMIT)


def install(app):
    @app.post('/api/maia/predict')
    def predict(body: PredictBody):
        """Maia's move probabilities and outcome for each position, in the order asked."""
        requests = []
        for p in body.positions:
            try:
                fen = chess.Board(p.fen).fen()
            except ValueError:
                raise HTTPException(422, 'Posizione non valida: ' + p.fen)
            requests.append((fen, p.selfElo, p.opponentElo))
        if not maia.available():
            raise HTTPException(503, 'Maia sul server non è disponibile.')
        return {'predictions': maia.predict_cached(requests)}
