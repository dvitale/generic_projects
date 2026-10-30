import json
import threading
import time
from pathlib import Path

import chess
import pytest

from backend.maia import Maia, maia

REFERENCE = json.loads((Path(__file__).parent / 'fixtures' / 'maia_reference.json').read_text())['positions']
needs_model = pytest.mark.skipif(not maia.available(), reason='modello Maia o onnxruntime assenti')


@pytest.mark.parametrize('case', REFERENCE, ids=lambda c: c['fen'])
def test_encoding_matches_browser(case):
    tokens, legal, _ = maia.encode(case['fen'])
    assert [int(i) for i in tokens.flatten().nonzero()[0]] == case['tokens']
    assert sorted([uci, index] for uci, index in legal) == case['legal']


@needs_model
def test_probabilities_match_browser_in_one_batch():
    cases = [c for c in REFERENCE if 'browserTop3' in c]
    for case, prediction in zip(cases, maia.predict_many([(c['fen'], 1500, 1500) for c in cases])):
        assert [m['uci'] for m in prediction['moves'][:3]] == [uci for uci, _ in case['browserTop3']]
        for move, (_, expected) in zip(prediction['moves'], case['browserTop3']):
            assert move['probability'] == pytest.approx(expected, abs=0.005)
        assert sum(m['probability'] for m in prediction['moves']) == pytest.approx(1, abs=1e-4)


@needs_model
def test_value_head_is_from_white_and_terminal_positions_need_no_model():
    mated = chess.Board('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3')
    black, white = maia.predict_many([('6k1/8/8/8/8/8/1q6/K7 b - - 0 1', 1500, 1500), ('k7/1Q6/8/8/8/8/8/6K1 w - - 0 1', 1500, 1500)])
    assert black['whiteExpectedScore'] < 0.2 and black['whiteOutcome']['loss'] > black['whiteOutcome']['win']
    # The mirrored position is the same decision for the other colour.
    assert black['whiteExpectedScore'] == pytest.approx(1 - white['whiteExpectedScore'], abs=1e-4)
    assert maia.predict(mated.fen(), 1500, 1500) == {'moves': [], 'whiteExpectedScore': 0.5, 'whiteOutcome': {'win': 0, 'draw': 1, 'loss': 0}}


@needs_model
def test_elo_changes_the_human_choice_and_batches_keep_order():
    fen = REFERENCE[3]['fen']
    weak, strong, again = maia.predict_many([(fen, 800, 800), (fen, 2200, 2200), (fen, 800, 800)])
    assert weak == again and weak['moves'] != strong['moves']


def test_missing_model_is_reported_not_raised(tmp_path):
    assert not Maia(tmp_path / 'missing.onnx').available()


@needs_model
def test_predict_endpoint_answers_in_order_with_san_and_caches(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)
    start = chess.STARTING_FEN
    after = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
    body = {'positions': [{'fen': start, 'selfElo': 1500, 'opponentElo': 1500}, {'fen': after, 'selfElo': 900, 'opponentElo': 900},
                          {'fen': start, 'selfElo': 1500, 'opponentElo': 1500}]}
    first, black, again = client.post('/api/maia/predict', json=body).json()['predictions']
    single = maia.predict(start, 1500, 1500)
    assert first == again and [m['uci'] for m in first['moves'][:3]] == [m['uci'] for m in single['moves'][:3]]
    assert first['whiteExpectedScore'] == pytest.approx(single['whiteExpectedScore'], abs=0.005)
    assert {m['san'] for m in first['moves'][:3]} <= {'e4', 'd4', 'Nf3', 'c4', 'g3', 'e3'}
    board = chess.Board(after)
    assert all(board.san(chess.Move.from_uci(m['uci'])) == m['san'] for m in black['moves'])
    # A repeated request is answered from the cache, without running the model again.
    monkeypatch.setattr(maia, 'predict_many', lambda *a, **k: pytest.fail('cache not used'))
    assert client.post('/api/maia/predict', json=body).json()['predictions'][0] == first


def test_predict_endpoint_rejects_bad_input_and_reports_a_missing_model(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)
    one = lambda fen: {'positions': [{'fen': fen, 'selfElo': 1500, 'opponentElo': 1500}]}
    assert client.post('/api/maia/predict', json=one('not a fen')).status_code == 422
    assert client.post('/api/maia/predict', json={'positions': []}).status_code == 422
    assert client.post('/api/maia/predict', json={'positions': [one(chess.STARTING_FEN)['positions'][0]] * 65}).status_code == 422
    monkeypatch.setattr(maia, 'available', lambda: False)
    assert client.post('/api/maia/predict', json=one(chess.STARTING_FEN)).status_code == 503


@needs_model
def test_interactive_requests_get_ahead_of_background_batches():
    order, started = [], threading.Event()
    maia.load()
    run = maia.session.run

    class Slow:
        def run(self, *args):
            started.set(); time.sleep(0.05); return run(*args)
    session, maia.session = maia.session, Slow()
    try:
        fens = [chess.STARTING_FEN] * (3 * 32)
        background = threading.Thread(target=lambda: (maia.predict_many([(f, 1500 + i, 1500) for i, f in enumerate(fens)]), order.append('background')))
        background.start(); started.wait(5)
        maia.predict_many([(chess.STARTING_FEN, 1234, 1234)], interactive=True); order.append('interactive')
        background.join()
    finally:
        maia.session = session
    assert order == ['interactive', 'background']


POLICY = [{'uci': 'e2e4', 'probability': .5}, {'uci': 'd2d4', 'probability': .3}, {'uci': 'c2c4', 'probability': .15}, {'uci': 'g2g4', 'probability': .05}]


def draw_with(monkeypatch, value):
    """choose() with the seeded draw fixed at `value`, as Math.random was fixed in the former browser tests."""
    monkeypatch.setattr('backend.maia.random.Random', lambda seed: type('R', (), {'random': lambda self: value})())


def test_full_distribution_can_choose_a_rare_move(monkeypatch):
    from backend.maia import choose
    policy = [{'uci': 'e2e4', 'probability': .8}, {'uci': 'd2d4', 'probability': .19}, {'uci': 'g2g4', 'probability': .01}]
    for value, expected in ((.4, 'e2e4'), (.9, 'd2d4'), (.999, 'g2g4')):
        draw_with(monkeypatch, value)
        assert choose(policy, 'sample-full-distribution', 30, 1)[0] == expected


def test_temperature_and_top_p_cut_rare_moves_and_top_move_plays_the_first(monkeypatch):
    from backend.maia import choose
    draw_with(monkeypatch, .9999)
    for selection in ('temperature-0.7-top-p-0.95', 'temperature-0.4-top-p-0.8'):
        assert choose(POLICY, selection, 30, 1)[0] != 'g2g4'
    assert choose(POLICY, 'sample-full-distribution', 30, 1)[0] == 'g2g4'
    # At temperature 0.4 e4 and d4 weigh 1 and 0.28: c4 (0.05) is outside top-p 0.8.
    assert choose(POLICY, 'temperature-0.4-top-p-0.8', 30, 1)[0] == 'd2d4'
    draw_with(monkeypatch, .5)
    assert choose(POLICY, 'temperature-0.4-top-p-0.8', 30, 1)[0] == 'e2e4'
    for value in (0, .5, .9999):
        draw_with(monkeypatch, value)
        assert choose(POLICY, 'top-move', 1, 1) == ('e2e4', .5)


def test_sharpened_selections_keep_variety_in_the_opening(monkeypatch):
    from backend.maia import choose
    # Up to move 8: temperature 1 and top-p 0.9, so c4 is possible but g4 (the last 5%) is not.
    for selection in ('temperature-0.4-top-p-0.8', 'temperature-0.7-top-p-0.95'):
        draw_with(monkeypatch, .9999)
        assert choose(POLICY, selection, 8, 1)[0] == 'c2c4'
        draw_with(monkeypatch, .6)
        assert choose(POLICY, selection, 1, 1)[0] == 'd2d4'
    draw_with(monkeypatch, .9999)
    assert choose(POLICY, 'temperature-0.4-top-p-0.8', 9, 1)[0] == 'd2d4'


def test_the_same_seed_gives_the_same_move():
    from backend.maia import choose
    assert len({choose(POLICY, 'sample-full-distribution', 30, 42) for _ in range(5)}) == 1
    assert choose([], 'top-move', 1, 1) is None


@needs_model
def test_maia_moves_on_the_server_with_the_game_selection_and_a_recorded_seed(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    from backend.maia import MODEL_VERSION
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'coach.sqlite3')
    with TestClient(main.app) as client:
        game = client.post('/api/games', json={'color': 'b', 'elo': 1500, 'move_selection': 'top-move', 'engine_version': 'scelta dalla pagina'}).json()
        assert game['engineVersion'] == MODEL_VERSION
        path = f"/api/games/{game['id']}/maia-move"
        moved = client.post(path, json={'version': 0, 'revision': 0, 'elapsed_seconds': 2.5}).json()
        top = maia.predict_cached([(chess.STARTING_FEN, 1500, 1500)])[0]['moves'][0]['uci']
        assert moved['moves'] == [top]
        with main.database() as con:
            row = con.execute('SELECT move_choices,move_times FROM games WHERE id=?', (game['id'],)).fetchone()
        choice = json.loads(row['move_choices'])[0]
        assert choice['engine'] == 'maia' and choice['selection'] == 'top-move' and choice['version'] == MODEL_VERSION and isinstance(choice['seed'], int)
        assert json.loads(row['move_times'])[0] == {'emt': 2.5}
        # Now it is the player's turn; a stale version is refused too.
        assert client.post(path, json={'version': 1, 'revision': 0}).status_code == 409
        assert client.post(path, json={'version': 0, 'revision': 0}).status_code == 409
        # A drill answers with Maia too; an imported game does not.
        drill = client.post('/api/drills/italiana/start', json={'color': 'b', 'elo': 1100, 'target': 3}).json()
        assert drill['turn'] != drill['playerColor']
        assert len(client.post(f"/api/games/{drill['id']}/maia-move", json={'version': drill['version'], 'revision': drill['revision']}).json()['moves']) == drill['version'] + 1
        imported = client.post('/api/import', json={'pgn': '1. e4 e5 *'}).json()
        assert client.post(f"/api/games/{imported['id']}/maia-move", json={'version': 2, 'revision': 0}).status_code == 409
