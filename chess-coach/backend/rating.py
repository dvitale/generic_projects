"""Exploratory Maia skill-profile fit, not a calibrated Elo rating."""
import json
import chess

RATING_LEVELS = list(range(600, 2601, 200))


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
    # Bound browser work; sample deterministically across the whole game.
    if total > 40:
        positions = [positions[round(i * (total - 1) / 39)] for i in range(40)]
    return {'version': len(moves), 'revision': row['revision'], 'positions': positions,
            'totalPositions': total, 'levels': RATING_LEVELS,
            'opponentElo': row['elo'] if row['source'] in {'maia', 'drill', 'snapshot'} else 1500,
            'opponentAssumed': row['source'] not in {'maia', 'drill', 'snapshot'}}


def summarize_rating(scores):
    best = max(scores)
    # A log-likelihood support band, deliberately NOT called a confidence interval.
    supported = [level for level, score in zip(RATING_LEVELS, scores) if score >= best - 2]
    informative = max(scores) - min(scores) >= 2
    estimate = RATING_LEVELS[scores.index(best)] if informative else None
    return {'estimate': estimate, 'low': min(supported), 'high': max(supported),
            'boundary': 'lower' if estimate == RATING_LEVELS[0] else 'upper' if estimate == RATING_LEVELS[-1] else None,
            'status': 'estimated' if informative else 'inconclusive'}
