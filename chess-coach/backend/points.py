"""Where an engine score comes from: material now, material at the end of Stockfish's line, and the rest."""
import chess

from .engine import expected
from .insights import material


def breakdown(fen, evaluation):
    """From the side to move, the player: conventional material (1/3/3/5/9) now and after the reference line, the
    expected score of the engine score, and the part of the score that the material at the end of the line leaves out."""
    board = chess.Board(fen)
    me, now, plies = board.turn, material(board, board.turn), 0
    for uci in evaluation.get('pv') or []:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        board.push(move)
        plies += 1
    end, mate = material(board, me), evaluation.get('mate')
    return {'now': now, 'end': end, 'plies': plies, 'cp': None if mate is not None else evaluation['cp'], 'mate': mate,
            'expected': round(expected(evaluation) * 100),
            'rest': None if mate is not None else round(evaluation['cp'] / 100 - end, 2)}
