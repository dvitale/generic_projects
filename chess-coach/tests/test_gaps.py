import json
import sqlite3
import time
from pathlib import Path

import pytest

from backend import gaps, main
from test_problems import client, stocked, start, play  # noqa: F401


def store_moves(puzzle_id):
    with sqlite3.connect(Path(main.DB_PATH).parent / 'lichess_puzzles.sqlite3') as con:
        return con.execute('SELECT moves FROM puzzles WHERE id=?', (puzzle_id,)).fetchone()[0].split()


def solve(client, problem):
    moves = store_moves(problem['puzzle']['id'])
    for step in range(1, len(moves), 2):
        r = play(client, problem, moves[step], step).json()
        assert r['correct'], r
    assert r['done']
    return r


def seed_own(results):
    """Closed own puzzles: (kind, endgame, solved first try) per session, with the classification already stored."""
    with main.database() as con:
        con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('own', '7k/8/5KQ1/8/8/8/8/8 w - - 0 1', '[]', 'w', 1500, 'Test', main.now(), None, None, 'pgn'))
        for i, (kind, endgame, solved) in enumerate(results):
            solution = {'kind': kind, 'move': 'g6g7', 'san': 'Qg7#', 'line': [], 'gain': None, 'endgame': endgame}
            con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at,solution) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (f'ex{i}', 'own', i, '7k/8/5KQ1/8/8/8/8/8 w - - 0 1', '[]', 'Tema', 'g6g7', 900, main.now(), json.dumps(solution)))
            con.execute('INSERT INTO puzzle_sessions(id,exercise_id,created_at,status,guesses,hints,exposure) VALUES(?,?,?,?,?,?,?)',
                        (f's{i}', f'ex{i}', main.now(), 'complete' if solved else 'revealed', 1, 0 if solved else 1, 'new'))


def seed_problem_failures(puzzle_id, count, rating=1200, puzzle_rating=989):
    with main.database() as con:
        for i in range(count):
            con.execute('INSERT INTO problem_sessions(id,puzzle_id,created_at,status,failed) VALUES(?,?,?,?,1)', (f'p{puzzle_id}{i}', puzzle_id, main.now(), 'closed'))
            con.execute('INSERT INTO problem_attempts(session_id,puzzle_id,puzzle_rating,success,rating_before,rating_after,created_at) VALUES(?,?,?,?,?,?,?)',
                        (f'p{puzzle_id}{i}', puzzle_id, puzzle_rating, 0, rating, rating, main.now()))


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(gaps, 'THEMED_SIZE', 2)
    monkeypatch.setattr(gaps, 'MIXED_SIZE', 2)
    monkeypatch.setattr(gaps, 'MIXED_THEMED', 1)


def test_own_puzzles_reveal_kinds_solved_less_often_than_the_average(client):
    seed_own([('quiet_threat', False, False)] * 6 + [('forcing', False, True)] * 6 + [('forcing', True, False)] * 3)
    found = {g['key']: g for g in client.get('/api/gaps').json()['gaps']}
    quiet = found['kind:quiet_threat']
    assert (quiet['status'], quiet['family'], quiet['total'], quiet['solved'], quiet['theme']) == ('confirmed', 'method', 6, 0, 'quietMove')
    assert quiet['expected'] == pytest.approx(6 / 15, abs=1e-3) and len(quiet['examples']) == 3
    # Three endgame failures are a hypothesis to watch, not yet a confirmed gap.
    endgame = found['phase:endgame']
    assert (endgame['status'], endgame['family'], endgame['missing']) == ('watch', 'theory', 3)
    assert 'kind:forcing' not in found
    # A puzzle not classified yet is reported and classified in the background.
    with main.database() as con:
        con.execute("UPDATE exercises SET solution=NULL WHERE id='ex0'")
    assert client.get('/api/gaps').json()['unclassified'] == 1
    for _ in range(100):
        with main.database() as con:
            if con.execute("SELECT solution FROM exercises WHERE id='ex0'").fetchone()[0]:
                break
        time.sleep(0.1)
    assert client.get('/api/gaps').json()['unclassified'] == 0


def test_problem_themes_are_compared_with_the_rating_expectation(stocked):
    seed_problem_failures('001wr', 6)
    # A failed 1974 problem at 1200 is expected: no gap for its themes.
    seed_problem_failures('001kG', 6, puzzle_rating=1974)
    found = {g['key']: g for g in stocked.get('/api/gaps').json()['gaps']}
    assert found['theme:fork']['status'] == 'confirmed' and found['theme:fork']['family'] == 'tactic'
    assert 'theme:pin' not in found and 'theme:advantage' not in found and 'theme:short' not in found


def test_problem_hints_go_from_the_kind_of_move_to_the_motif_and_cost_the_rating_once(stocked):
    problem = start(stocked, band=6)
    assert problem['puzzle']['id'] == '001kG'
    path = f"/api/problems/sessions/{problem['sessionId']}/hint"
    first = stocked.post(path, json={'step': 1}).json()
    assert len(first['hints']) == 1 and first['result']['success'] is False and not first['last']
    second = stocked.post(path, json={'step': 1}).json()
    assert second['hints'][1] == {'level': 2, 'title': 'Motivo', 'text': '', 'themes': ['pin']} and second['result'] is None
    third = stocked.post(path, json={'step': 1}).json()
    assert third['last'] and third['hints'][2]['title'] == 'Dove guardare' and third['hints'][2]['squares']
    assert stocked.post(path, json={'step': 3}).status_code == 409
    assert stocked.get('/api/problems').json()['attempts'] == 1


def test_study_path_runs_lesson_themed_mixed_and_review_then_closes_the_gap(stocked, small):
    seed_problem_failures('001wr', 6)
    assert stocked.post('/api/study-paths', json={'gap': 'theme:pin'}).status_code == 409
    created = stocked.post('/api/study-paths', json={'gap': 'theme:fork'}).json()['path']
    assert created['stage'] == 'lesson' and created['lesson']['title'] == 'Attacco doppio' and created['fewPuzzles']
    assert created['example']['label'] == 'Problema 001wr' and created['example']['solution']
    assert stocked.post('/api/study-paths', json={'gap': 'theme:fork'}).status_code == 409
    ident = created['id']
    assert stocked.post('/api/problems/next', json={'path': ident}).status_code == 409
    assert stocked.post(f'/api/study-paths/{ident}/start').json()['path']['stage'] == 'themed'
    for _ in range(2):
        problem = start(stocked, path=ident)
        assert problem['puzzle']['id'] == '001wr' and problem['path'] == ident
        solve(stocked, problem)
    path = stocked.get('/api/study-paths/active').json()['path']
    assert path['stage'] == 'mixed' and path['progress'] == {'done': 0, 'size': 2, 'solved': None}
    themed = 0
    for _ in range(2):
        problem = start(stocked, path=ident)
        themed += problem['puzzle']['id'] == '001wr'
        solve(stocked, problem)
    assert themed == 1
    path = stocked.get('/api/study-paths/active').json()['path']
    assert path['stage'] == 'waiting' and path['reviewAt'] > main.now()
    assert stocked.post('/api/problems/next', json={'path': ident}).status_code == 409
    # Path problems never feed the gap statistics.
    assert stocked.get('/api/gaps').json()['gaps'][0]['total'] == 6
    with main.database() as con:
        con.execute('UPDATE study_paths SET review_at=? WHERE id=?', ('2000-01-01T00:00:00+00:00', ident))
    problem = start(stocked, path=ident)
    assert problem['puzzle']['id'] == '001wr'
    solve(stocked, problem)
    assert stocked.get('/api/study-paths/active').json()['path'] is None
    overview = stocked.get('/api/gaps').json()
    assert overview['passed'][0]['gap'] == 'theme:fork' and not any(g['key'] == 'theme:fork' for g in overview['gaps'])


def test_a_failed_mixed_series_repeats_the_themed_one(stocked, small):
    seed_problem_failures('001wr', 6)
    ident = stocked.post('/api/study-paths', json={'gap': 'theme:fork'}).json()['path']['id']
    stocked.post(f'/api/study-paths/{ident}/start')
    for _ in range(2):
        solve(stocked, start(stocked, path=ident))
    for _ in range(2):
        problem = start(stocked, path=ident)
        stocked.post(f"/api/problems/sessions/{problem['sessionId']}/reveal", json={'step': 1})
    path = stocked.get('/api/study-paths/active').json()['path']
    assert (path['stage'], path['round'], path['progress']['done']) == ('themed', 2, 0)
    assert stocked.post(f'/api/study-paths/{ident}/abandon').json() == {'path': None}
    assert stocked.get('/api/study-paths/active').json()['path'] is None


def test_a_path_for_own_puzzles_schedules_the_original_failures_for_review(stocked, small):
    seed_own([('quiet_threat', False, False)] * 6 + [('forcing', False, True)] * 6)
    r = stocked.post('/api/study-paths', json={'gap': 'kind:quiet_threat'})
    assert r.status_code == 200, r.text
    created = r.json()['path']
    assert created['theme'] == 'quietMove' and created['example']['label'] == 'Dalla tua partita #1'
    assert stocked.post('/api/study-paths', json={'gap': 'kind:improvement'}).status_code == 409
    ident = created['id']
    stocked.post(f'/api/study-paths/{ident}/start')
    for _ in range(2):
        solve(stocked, start(stocked, path=ident))
    for _ in range(2):
        problem = start(stocked, path=ident)
        solve(stocked, problem)
    assert stocked.get('/api/study-paths/active').json()['path'] is None
    with main.database() as con:
        path = con.execute('SELECT outcome, review_at, examples FROM study_paths WHERE id=?', (ident,)).fetchone()
        examples = json.loads(path['examples'])
        due = [r[0] for r in con.execute(f"SELECT due_at FROM exercises WHERE id IN ({','.join('?' * len(examples))})", examples)]
    assert path['outcome'] == 'passed' and len(examples) == 3 and due == [path['review_at']] * 3
