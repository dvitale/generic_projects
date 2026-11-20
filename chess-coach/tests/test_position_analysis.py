import chess

from test_problems import client  # noqa: F401

URL = '/api/analysis/position'


def test_any_position_gets_an_evaluation_and_stockfishs_best_moves(client):
    # After 1. e4 e5 2. Qh5 Nc6 3. Qxe5+: Black takes the queen.
    fen = 'r1bqkbnr/pppp1ppp/2n5/4Q3/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 3'
    r = client.post(URL, json={'fen': fen})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['terminal'] is None and data['evaluation']['perspective'] == 'b'
    assert data['candidates'][0]['uci'] == 'c6e5' and data['candidates'][0]['san'] == 'Nxe5'
    assert 1 <= len(data['candidates']) <= 3 and data['evaluation']['cp'] > 500
    assert all(chess.Move.from_uci(c['uci']) in chess.Board(fen).legal_moves for c in data['candidates'])


def test_a_free_move_is_judged_with_the_review_rule(client):
    fen = 'r1bqkbnr/pppp1ppp/2n5/4Q3/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 3'
    good = client.post(URL, json={'fen': fen, 'move': 'c6e5'}).json()['move']
    assert good['best'] and good['san'] == 'Nxe5' and good['label'] == 'Buona scelta'
    bad = client.post(URL, json={'fen': fen, 'move': 'g8e7'}).json()['move']
    assert not bad['best'] and bad['loss'] >= 180 and bad['label'] == 'Errore'


def test_mate_on_the_board_is_terminal_and_bad_input_is_refused(client):
    mate = 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3'
    data = client.post(URL, json={'fen': mate}).json()
    assert data['terminal'] == 'checkmate' and data['evaluation']['mate'] == 0 and data['candidates'] == []
    assert client.post(URL, json={'fen': 'not a fen'}).status_code == 422
    assert client.post(URL, json={'fen': chess.STARTING_FEN, 'move': 'e2e5'}).status_code == 422
