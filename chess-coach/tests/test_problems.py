import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests' / 'fixtures' / 'lichess-puzzles.csv'
spec = importlib.util.spec_from_file_location('import_lichess_puzzles', ROOT / 'scripts' / 'import_lichess_puzzles.py')
assert spec and spec.loader
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'coach.sqlite3')
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def stocked(client, tmp_path):
    importer.build(str(FIXTURE), tmp_path / 'lichess_puzzles.sqlite3', 5, 80, 200, 90)
    return client


def start(client, **body):
    r = client.post('/api/problems/next', json=body)
    assert r.status_code == 200, r.text
    return r.json()


def play(client, problem, move, step):
    return client.post(f"/api/problems/sessions/{problem['sessionId']}/moves", json={'move': move, 'step': step})


def test_without_database_the_section_explains_how_to_install_it(client):
    overview = client.get('/api/problems').json()
    assert overview['available'] is False and overview['bands'] == [] and overview['rating'] == 1200
    assert client.post('/api/problems/next', json={}).status_code == 404


def test_import_keeps_bands_themes_and_filters(stocked, tmp_path):
    overview = stocked.get('/api/problems').json()
    assert overview['available'] and overview['total'] == 11
    assert [b['count'] for b in overview['bands']] == [1, 1, 2, 1, 1, 1, 1, 1, 1, 1]
    assert overview['bands'][0]['label'] == 'Fino a 800' and overview['bands'][-1]['min'] == 2500
    assert {'id': 'mateIn1', 'count': 1} in overview['themes']
    # Low popularity or few plays are filtered out at import time.
    importer.build(str(FIXTURE), tmp_path / 'strict.sqlite3', 5, 98, 200, 90)
    import sqlite3
    with sqlite3.connect(tmp_path / 'strict.sqlite3') as con:
        assert con.execute('SELECT COUNT(*) FROM puzzles').fetchone()[0] == 1


def test_clean_solution_raises_the_rating_and_hides_the_solution_until_the_end(stocked):
    problem = start(stocked, band=0)
    assert problem['puzzle']['id'] == '007mr' and problem['puzzle']['opponentMove'] == 'd4e4'
    assert problem['puzzle']['turn'] == 'b' and problem['puzzle']['length'] == 2
    assert 'solution' not in problem['puzzle'] and 'rating' not in problem['puzzle']
    first = play(stocked, problem, 'd5d1', 1).json()
    assert first['correct'] and first['reply'] == 'e1d1' and first['step'] == 3 and not first['done']
    assert 'd7d1' in first['legalMoves']
    last = play(stocked, problem, 'd7d1', 3).json()
    assert last['done'] and last['result']['success'] and last['result']['solution'] == ['d5d1', 'e1d1', 'd7d1']
    assert last['result']['ratingBefore'] == 1200 and last['result']['ratingAfter'] > 1200
    assert play(stocked, problem, 'd7d1', 3).status_code == 409
    overview = stocked.get('/api/problems').json()
    assert overview['solved'] == 1 and overview['bands'][0]['solved'] == 1


def test_first_mistake_is_rated_once_and_the_problem_can_still_be_finished(stocked):
    problem = start(stocked, band=1)
    wrong = play(stocked, problem, 'a8b8', 1).json()
    assert not wrong['correct'] and wrong['result']['success'] is False
    assert 'solution' not in wrong['result']
    lowered = wrong['result']['ratingAfter']
    assert lowered < 1200
    again = play(stocked, problem, 'a8b8', 1).json()
    assert not again['correct'] and again['result'] is None
    assert play(stocked, problem, 'd6c5', 2).status_code == 409
    assert play(stocked, problem, 'a1a2', 1).status_code == 422
    first = play(stocked, problem, 'd6c5', 1).json()
    assert first['correct'] and first['reply'] == 'g1h1'
    done = play(stocked, problem, 'c5c4', 3).json()
    assert done['done'] and done['result']['success'] is False and done['result']['ratingAfter'] == lowered
    assert stocked.get('/api/problems').json()['attempts'] == 1


def test_reveal_closes_the_problem_and_skip_before_moving_leaves_no_trace(stocked):
    problem = start(stocked, band=3)
    revealed = stocked.post(f"/api/problems/sessions/{problem['sessionId']}/reveal", json={'step': 1}).json()
    assert revealed['remaining'] == ['f5e5', 'e2f1', 'e5e6'] and revealed['result']['success'] is False
    assert play(stocked, problem, 'f5e5', 1).status_code == 409
    skipped = start(stocked, band=4)
    assert stocked.post(f"/api/problems/sessions/{skipped['sessionId']}/skip").json() == {'skipped': True}
    overview = stocked.get('/api/problems').json()
    assert overview['attempts'] == 1 and overview['bands'][4]['attempts'] == 0


def test_theme_filter_adaptive_mode_and_repetition(stocked):
    mate = start(stocked, band=2, theme='mateIn1')
    assert mate['puzzle']['id'] == '001wb'
    finished = play(stocked, mate, 'g6h5', 1).json()
    assert finished['done'] and finished['reply'] is None and finished['result']['success']
    # Adaptive mode: within 100 points of the personal rating (now slightly above 1200).
    adaptive = start(stocked)
    assert adaptive['puzzle']['id'] == '001wb' and adaptive['repeated'] is True
    assert stocked.post('/api/problems/next', json={'band': 2, 'theme': 'zugzwang'}).status_code == 404
    assert stocked.post('/api/problems/next', json={'theme': 'bad theme'}).status_code == 422
