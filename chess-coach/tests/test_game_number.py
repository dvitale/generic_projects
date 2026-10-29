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
