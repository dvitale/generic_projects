import sqlite3
import chess
from backend import main
from test_coach import client  # noqa: F401


def test_games_get_a_stable_number_in_creation_order(client):
    first, second = client.post('/api/games', json={}).json(), client.post('/api/import', json={'pgn': '1. e4 e5 *', 'color': 'w'}).json()
    assert second['number'] == first['number'] + 1
    listed = {g['id']: g['number'] for g in client.get('/api/games').json()}
    assert listed[first['id']] == first['number'] and listed[second['id']] == second['number']
    assert client.get(f"/api/games/{first['id']}").json()['number'] == first['number']


def test_existing_games_are_numbered_by_date_once(tmp_path, monkeypatch):
    db = tmp_path / 'old.sqlite3'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE games(id TEXT PRIMARY KEY, initial_fen TEXT,moves TEXT,player_color TEXT,elo INTEGER,title TEXT,created_at TEXT,analysis TEXT,analysis_version INTEGER,source TEXT)')
        for game_id, created in (('later', '2026-10-02T10:00:00'), ('earlier', '2026-10-01T10:00:00')):
            con.execute('INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?,?)', (game_id, chess.STARTING_FEN, '[]', 'w', 1500, 'Old', created, None, None, 'maia'))
    monkeypatch.setattr(main, 'DB_PATH', db)
    main.init_db()
    main.init_db()
    assert [main.get_game(i)['number'] for i in ('earlier', 'later')] == [1, 2]


def test_training_screens_name_the_source_game_by_number(client):
    from test_coach import seed_exercise
    seed_exercise()
    with main.database() as con:
        number = con.execute("SELECT number FROM games WHERE id='seed'").fetchone()[0]
        con.execute('INSERT INTO prevention_positions(id,game_id,ply,initial_fen,history,original_move,due_at) VALUES(?,?,?,?,?,?,?)',
                    ('bp', 'seed', 1, '7k/8/5KQ1/8/8/8/8/8 w - - 0 1', '[]', 'g6g8', main.now()))
    assert client.get('/api/exercises').json()[0]['gameNumber'] == number
    assert client.get('/api/exercises/ex').json()['gameNumber'] == number
    assert client.get('/api/prevention').json()['positions'][0]['gameNumber'] == number
    queue = client.get('/api/training-plan').json()['queue']
    assert queue and all(item['title'] == f'#{number} · Test' for item in queue)
    personal = next(t for t in client.get('/api/drills').json() if t['kind'] == 'personal')
    assert personal['source'].startswith(f'#{number} · Test · mossa')
