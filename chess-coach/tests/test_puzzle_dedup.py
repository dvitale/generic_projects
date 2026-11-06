import json
import sqlite3
from datetime import datetime, timedelta, timezone
from test_coach import client, seed_exercise
from backend import main

START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'


def game(con, ident, moves):
    con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (ident, START, json.dumps(moves), 'w', 1500, 'Test', main.now(), None, None, 'pgn'))
    return {'id': ident, 'revision': 0, 'initial_fen': START}


def item(ply):
    return {'ply': ply, 'theme': 'Conseguenze tattiche', 'loss': 250, 'best': {'pv': ['f1c4']}}


def test_the_same_position_in_another_game_brings_the_puzzle_back_instead_of_a_copy(client):
    # 1.e4 e5 2.Nf3 Nc6 and 1.Nf3 Nc6 2.e4 e5 reach the same position by transposition.
    first, second = ['e2e4', 'e7e5', 'g1f3', 'b8c6'], ['g1f3', 'b8c6', 'e2e4', 'e7e5']
    with main.database() as con:
        a, b = game(con, 'a', first), game(con, 'b', second)
        ex = main.store_exercise(con, a, first, item(4), main.now())
        later = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        con.execute("UPDATE exercises SET streak=2,due_at=? WHERE id=?", (later, ex))
        # Analysing the same game again is not a repetition.
        assert main.store_exercise(con, a, first, item(4), main.now()) == ex
        assert con.execute('SELECT streak FROM exercises').fetchone()[0] == 2
        assert main.store_exercise(con, b, second, item(4), main.now()) == ex
        assert main.store_exercise(con, b, second, item(4), main.now()) == ex
        row = con.execute('SELECT * FROM exercises').fetchall()
        assert len(row) == 1 and row[0]['streak'] == 0 and row[0]['due_at'] <= main.now()
    listed = client.get('/api/exercises').json()
    assert [e['id'] for e in listed] == [ex] and listed[0]['repeats'] == 1
    assert client.get(f'/api/exercises/{ex}').json()['repeats'] == 1
    # The game pack of the second game still finds its puzzle.
    with main.database() as con:
        assert con.execute("SELECT exercise_id FROM exercise_sources WHERE game_id='b'").fetchone()[0] == ex


def test_three_independent_successes_retire_a_puzzle_until_the_mistake_comes_back(client):
    seed_exercise()
    with main.database() as con:
        con.execute("UPDATE exercises SET streak=2,position_key=? WHERE id='ex'", ('7k/8/5KQ1/8/8/8/8/8 w - -',))
        con.execute("INSERT INTO exercise_sources VALUES('ex','seed',0,?)", (main.now(),))
    s = client.post('/api/exercises/ex/sessions').json()
    result = client.post('/api/exercises/ex/attempts', json={'session_id': s['id'], 'move': 'g6g7', 'version': 0}).json()
    assert result['scheduled']
    assert client.get('/api/exercises').json() == [] and client.get('/api/profile').json()['due'] == 0
    assert client.get('/api/training-plan').json()['total'] == 0
    # Still reachable by id, for history and links.
    assert client.get('/api/exercises/ex').json()['retired'] == 'mastered'
    fen = '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'
    with main.database() as con:
        con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('again', fen, '[]', 'w', 1500, 'Test', main.now(), None, None, 'pgn'))
        main.store_exercise(con, {'id': 'again', 'revision': 0, 'initial_fen': fen}, [], {**item(0), 'best': {'pv': ['g6g7']}}, main.now())
    listed = client.get('/api/exercises').json()
    assert [e['id'] for e in listed] == ['ex'] and listed[0]['streak'] == 0 and listed[0]['repeats'] == 1


def test_migration_keeps_the_first_copy_and_retires_learnt_puzzles():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.execute('''CREATE TABLE exercises(id TEXT PRIMARY KEY, game_id TEXT, ply INTEGER, initial_fen TEXT, history TEXT,
                   theme TEXT, best_move TEXT, loss INTEGER, due_at TEXT, streak INTEGER DEFAULT 0, UNIQUE(game_id, ply))''')
    rows = [('x', 'a', 4, '["e2e4","e7e5","g1f3","b8c6"]', 0), ('y', 'b', 4, '["g1f3","b8c6","e2e4","e7e5"]', 1), ('z', 'c', 1, '["d2d4"]', 3)]
    for ident, g, ply, history, streak in rows:
        con.execute('INSERT INTO exercises VALUES(?,?,?,?,?,?,?,?,?,?)', (ident, g, ply, START, history, 'T', 'f1c4', 200, '2026-01-01', streak))
    main.migrate_exercise_positions(con)
    main.migrate_exercise_positions(con)
    assert {r['id']: r['retired'] for r in con.execute('SELECT * FROM exercises')} == {'x': None, 'y': 'duplicate', 'z': 'mastered'}
    assert {(r['game_id'], r['exercise_id']) for r in con.execute('SELECT * FROM exercise_sources')} == {('a', 'x'), ('b', 'x'), ('c', 'z')}
