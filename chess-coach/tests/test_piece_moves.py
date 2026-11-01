import chess

from test_problems import client  # noqa: F401


def test_every_move_of_the_selected_piece_is_judged_against_the_best_move(client):
    # Black to move: the queen can take a defended pawn on e4 (a mistake) or retreat.
    fen = 'rnb1kbnr/pppp1ppp/8/4p1q1/4P3/3P4/PPP2PPP/RNBQKBNR b KQkq - 0 3'
    moves = {m['san']: m for m in client.post('/api/review/piece-moves', json={'fen': fen, 'square': 'g5'}).json()['moves']}
    assert len(moves) == len([m for m in chess.Board(fen).legal_moves if m.from_square == chess.G5])
    assert moves['Qxg2']['quality'] == 'mistake' and moves['Qxg2']['drop'] >= 0.10
    assert {m['quality'] for m in moves.values()} <= {'best', 'good', 'inaccuracy', 'mistake'}
    assert client.post('/api/review/piece-moves', json={'fen': fen, 'square': 'e4'}).status_code == 422
