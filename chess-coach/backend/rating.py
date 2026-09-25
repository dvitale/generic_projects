"""Maia platform drill-style maximum likelihood score, not calibrated Elo.

Reference: CSSLab/maia-platform-frontend a6e52f5,
useOpeningDrillController.ts (ratingDistribution and ensureMaiaForNode).
"""
import json
import math
import chess

RATING_LEVELS = list(range(600, 2601, 100))
RATING_METHOD = 'maia3-drill-match-v2'


def rating_plan(row, session=None):
    board = chess.Board(row['initial_fen'])
    start = session['start_ply'] if session else 0
    positions = []
    moves = json.loads(row['moves'])
    for ply, move in enumerate(moves):
        if ply >= start and board.turn == (row['player_color'] == 'w') and board.legal_moves.count() > 1:
            positions.append({'fen': board.fen(), 'move': move, 'ply': ply})
        board.push_uci(move)
    total = len(positions)
    return {'version': len(moves), 'revision': row['revision'], 'positions': positions,
            'totalPositions': total, 'levels': RATING_LEVELS,
            'method': RATING_METHOD, 'opponentMode': 'matched-level', 'probabilityFloor': 0.001}


def summarize_rating(scores, sample_size):
    best = max(scores)
    # Preserve a genuine numerical tie instead of claiming the lowest level wins.
    tied = [level for level, score in zip(RATING_LEVELS, scores) if math.isclose(score, best, rel_tol=0, abs_tol=1e-8)]
    estimate = tied[0] if len(tied) == 1 else None
    comparisons = [{'level': level, 'meanLogLikelihood': score / sample_size,
                    'geometricMoveProbability': math.exp(score / sample_size)}
                   for level, score in zip(RATING_LEVELS, scores)]
    return {'estimate': estimate, 'tiedLevels': tied if len(tied) > 1 else [], 'comparisons': comparisons,
            'boundary': 'lower' if estimate == RATING_LEVELS[0] else 'upper' if estimate == RATING_LEVELS[-1] else None,
            'status': 'estimated' if estimate is not None else 'tied'}
