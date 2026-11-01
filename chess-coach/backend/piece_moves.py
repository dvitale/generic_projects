"""Review: every legal move of one piece, judged by Stockfish against the best move of the whole position.

The interface pairs each move with Maia's probability at the review level, so a tempting mistake shows at a glance."""
from functools import lru_cache

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import evaluator, expected

NODES = 20000  # per move of the piece; the whole position gets four times as many
# Expected-score drop against the best move: the Queen paper's thresholds (arXiv 2610.03695).
INACCURACY, MISTAKE = 0.05, 0.10


class PieceBody(BaseModel):
    fen: str = Field(max_length=100)
    square: str = Field(pattern=r'^[a-h][1-8]$')


def quality(drop):
    return 'mistake' if drop >= MISTAKE else 'inaccuracy' if drop >= INACCURACY else 'good'


@lru_cache(maxsize=256)
def judge(fen, square):
    board = chess.Board(fen)
    origin = chess.parse_square(square)
    moves = [m for m in board.legal_moves if m.from_square == origin]
    if not moves:
        return []
    best = evaluator.evaluate(board, nodes=NODES * 4)
    found = {e['pv'][0]: e for e in evaluator.rank(board, moves, NODES)}
    # A node-limited MultiPV search can stop before every line is reported: the rest are searched one by one.
    for move in moves:
        found.setdefault(move.uci(), evaluator.evaluate(board, move, NODES))
    top = max([expected(best)] + [expected(e) for e in found.values()])
    result = []
    for move in moves:
        e = found[move.uci()]
        drop = max(0.0, top - expected(e))
        result.append({'uci': move.uci(), 'san': board.san(move), 'cp': e['cp'], 'mate': e['mate'], 'drop': round(drop, 3),
                       'quality': 'best' if best['pv'] and move.uci() == best['pv'][0] else quality(drop)})
    return result


def install(app):
    @app.post('/api/review/piece-moves')
    def piece_moves(body: PieceBody):
        try:
            board = chess.Board(body.fen)
        except ValueError:
            raise HTTPException(422, 'Posizione non valida') from None
        if not board.is_valid():
            raise HTTPException(422, 'Posizione non valida')
        piece = board.piece_at(chess.parse_square(body.square))
        if piece is None or piece.color != board.turn:
            raise HTTPException(422, 'Seleziona un pezzo del giocatore che muove')
        return {'moves': judge(board.fen(), body.square), 'thresholds': {'inaccuracy': INACCURACY, 'mistake': MISTAKE}}
