"""Free analysis of any position, for the line replays: evaluation, Stockfish's best moves and a verdict on a move.

Opened by «Guarda la variante sulla scacchiera» when the player leaves the line and tries moves of their own,
in the manner of the Lichess analysis board. The verdict uses the one review rule (`review_loss`, `missed_mate`)."""
from functools import lru_cache

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import evaluator, missed_mate, review_label, review_loss

NODES = 15000  # per line of the MultiPV search
COUNT = 3


class PositionBody(BaseModel):
    fen: str = Field(max_length=100)
    move: str | None = Field(default=None, pattern=r'^[a-h][1-8][a-h][1-8][qrbn]?$')


@lru_cache(maxsize=512)
def analyse(fen):
    board = chess.Board(fen)
    side = 'w' if board.turn else 'b'
    if board.is_checkmate():
        return {'evaluation': {'cp': -100000, 'mate': 0, 'perspective': side}, 'terminal': 'checkmate', 'candidates': []}
    if board.is_game_over(claim_draw=True):
        return {'evaluation': {'cp': 0, 'mate': None, 'perspective': side}, 'terminal': 'draw', 'candidates': []}
    lines = evaluator.candidates(board, nodes=NODES, count=COUNT)
    candidates = [{'uci': e['pv'][0], 'san': e['san'][0], 'cp': e['cp'], 'mate': e['mate'], 'pv': e['pv'], 'sanLine': e['san']}
                  for e in lines if e['pv']]
    best = lines[0]
    return {'evaluation': {'cp': best['cp'], 'mate': best['mate'], 'perspective': side}, 'terminal': None, 'candidates': candidates}


@lru_cache(maxsize=512)
def verdict(fen, uci):
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    result = analyse(fen)
    best = result['candidates'][0]
    actual = next((c for c in result['candidates'] if c['uci'] == uci), None) or evaluator.evaluate(board, move, NODES)
    loss, mate = review_loss(best, actual), missed_mate(best, actual)
    forced = board.legal_moves.count() == 1
    return {'uci': uci, 'san': board.san(move), 'cp': actual['cp'], 'mate': actual['mate'], 'loss': loss, 'missedMate': mate,
            'best': uci == best['uci'], 'label': review_label({'loss': loss, 'missedMate': mate, 'forced': forced})}


def install(app):
    @app.post('/api/analysis/position')
    def position_analysis(body: PositionBody):
        try:
            board = chess.Board(body.fen)
        except ValueError:
            raise HTTPException(422, 'Posizione non valida') from None
        if not board.is_valid():
            raise HTTPException(422, 'Posizione non valida')
        fen = board.fen()
        if body.move is None:
            return analyse(fen)
        if chess.Move.from_uci(body.move) not in board.legal_moves:
            raise HTTPException(422, 'Mossa non legale in questa posizione')
        return {**analyse(fen), 'move': verdict(fen, body.move)}
