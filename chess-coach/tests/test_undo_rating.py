import json
import sqlite3
import chess
import pytest
from backend import main
from backend.rating import rating_plan, summarize_rating
from test_coach import client, wait_analysis


def move(client, g, uci):
    result = client.post(f"/api/games/{g['id']}/moves", json={
        'move': uci, 'version': g['version'], 'revision': g['revision'],
        'actor': 'human' if g['turn'] == g['playerColor'] else 'maia'})
    assert result.status_code == 200, result.text
    return result.json()


def undo(client, g):
    return client.post(f"/api/games/{g['id']}/undo", json={'version': g['version'], 'revision': g['revision']})


def test_undo_cancels_reply_and_rejects_replayed_old_requests(client):
    g = client.post('/api/games', json={}).json()
    assert not g['canUndo'] and undo(client, g).status_code == 409
    g = move(client, g, 'e2e4')
    old = dict(g)
    g = undo(client, g).json()
    assert g['moves'] == [] and g['fen'] == chess.STARTING_FEN and g['revision'] == 1
    assert undo(client, old).status_code == 409  # duplicate click
    g = move(client, g, 'd2d4')
    assert client.post(f"/api/games/{g['id']}/moves", json={'move': 'e7e5', 'version': 1, 'revision': 0, 'actor': 'maia'}).status_code == 409
    pending = dict(g)
    g = move(client, g, 'd7d5')
    # Reply committed during undo request: remove both plies atomically.
    g = undo(client, pending).json()
    assert g['moves'] == [] and g['revision'] == 2
    assert client.get('/api/games/' + g['id']).json() == g


def test_black_undo_preserves_first_bot_move_and_drill_seed(client):
    g = client.post('/api/games', json={'color': 'b'}).json()
    g = move(client, g, 'e2e4')
    assert not g['canUndo']
    g = move(client, g, 'e7e5')
    g = move(client, g, 'g1f3')
    g = undo(client, g).json()
    assert g['moves'] == ['e2e4'] and g['turn'] == 'b' and not g['canUndo']
    g = client.post('/api/drills/italiana/start', json={'target': 3}).json()
    seed = dict(g)
    assert not g['canUndo']
    while not g['drill']['complete']:
        g = move(client, g, g['legalMoves'][0])
    g = undo(client, g).json()
    assert not g['drill']['complete'] and g['drill']['decisions'] == 2
    while g['canUndo']:
        g = undo(client, g).json()
    assert g['moves'] == seed['moves'] and g['fen'] == seed['fen']
    assert g['drill']['decisions'] == 0 and undo(client, g).status_code == 409


@pytest.mark.parametrize('fen,uci', [
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1'),
    ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6'),
    ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7a8n'),
    ('7k/8/5KQ1/8/8/8/8/8 w - - 0 1', 'g6g7'),
])
def test_undo_restores_special_moves_and_finished_games(client, fen, uci):
    g = client.post('/api/games', json={'fen': fen}).json()
    initial = g['fen']
    g = move(client, g, uci)
    g = undo(client, g).json()
    assert g['fen'] == initial and g['result'] is None and uci in g['legalMoves']


def test_undo_preserves_reviewed_evidence_and_stale_analysis_cannot_write(client, monkeypatch):
    g = client.post('/api/games', json={'fen': '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}).json()
    g = move(client, g, 'g6g8')
    wait_analysis(client, g['id'])
    ex = client.get('/api/exercises').json()[0]
    session = client.post(f"/api/exercises/{ex['id']}/sessions").json()
    client.post(f"/api/exercises/{ex['id']}/reveal", json={'session_id': session['id']})
    with main.database() as con:
        stale = dict(main.find_game(con, g['id']))
    g = undo(client, g).json()
    assert g['analysis'] is None
    saved_ex = client.get('/api/exercises').json()[0]
    assert saved_ex['id'] == ex['id'] and saved_ex['gameId'] != g['id']
    archive = client.get('/api/games/' + saved_ex['gameId']).json()
    assert archive['moves'] == ['g6g8'] and archive['analysis'] and not archive['canUndo']
    assert client.get('/api/profile').json()['attempts'] == 1
    assert client.get('/api/profile').json()['games'] == 1
    g = move(client, g, 'g6h7')
    main.jobs['stale-test'] = {'gameId': g['id'], 'status': 'running', 'progress': 0}
    main.analyze_game('stale-test', stale)
    assert main.jobs['stale-test']['status'] == 'failed'
    assert client.get('/api/games/' + g['id']).json()['analysis'] is None
    wait_analysis(client, g['id'])  # New branch can create exercises without colliding with saved evidence.
    assert any(e['gameId'] == g['id'] for e in client.get('/api/exercises').json())


PGN = '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. Nbd2 Bb7 12. Bc2 Re8 *'


def test_rating_saved_for_exact_position_and_short_games_rejected(client):
    imported = client.post('/api/import', json={'pgn': PGN}).json()
    assert undo(client, imported).status_code == 409
    g = client.post('/api/games', json={}).json()
    for uci in imported['moves']:
        g = move(client, g, uci)
    plan = client.get(f"/api/games/{g['id']}/rating-positions").json()
    assert len(plan['positions']) == 12 and not plan['opponentAssumed']
    path = f"/api/games/{g['id']}/rating"
    body = {'version': g['version'], 'revision': g['revision'], 'log_scores': [-100,-90,-80,-70,-60,-50,-40,-41,-45,-60,-70]}
    result = client.post(path, json=body)
    assert result.status_code == 200, result.text
    assert result.json()['estimate'] == 1800 and result.json()['low'] == 1800 and result.json()['high'] == 2000
    assert client.get('/api/games/' + g['id']).json()['rating'] == result.json()
    g = undo(client, g).json()
    assert g['rating'] is None and client.post(path, json=body).status_code == 409
    with main.database() as con:
        assert con.execute('SELECT count(*) FROM game_ratings WHERE game_id=?', (g['id'],)).fetchone()[0] == 0
    g = client.post('/api/games', json={}).json()
    body.update(version=0, revision=0)
    assert client.post(f"/api/games/{g['id']}/rating", json=body).status_code == 422


def test_rating_uncertainty_boundaries_forced_moves_and_sample():
    assert summarize_rating([-10] * 11)['estimate'] is None
    assert summarize_rating([-10 - i for i in range(11)])['boundary'] == 'lower'
    assert summarize_rating([-30 + i for i in range(11)])['boundary'] == 'upper'
    board = chess.Board()
    moves = ['g1f3','g8f6','f3g1','f6g8'] * 30
    row = {'initial_fen': board.fen(), 'moves': json.dumps(moves), 'player_color':'w', 'revision': 0, 'source':'pgn', 'elo':1500}
    plan = rating_plan(row)
    assert plan['totalPositions'] == 60 and len(plan['positions']) == 40
    assert plan['positions'][0]['ply'] == 0 and plan['positions'][-1]['ply'] == 118
    assert plan['opponentAssumed']
    assert rating_plan(row, {'start_ply': 118})['totalPositions'] == 1
    row.update(initial_fen='k7/8/2KQ4/8/8/8/8/8 b - - 0 1', moves='["a8a7"]', player_color='b')
    assert chess.Board(row['initial_fen']).legal_moves.count() == 1
    assert rating_plan(row)['positions'] == []


def test_existing_database_migrates_without_losing_games(tmp_path, monkeypatch):
    db = tmp_path / 'old.sqlite3'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE games(id TEXT PRIMARY KEY, initial_fen TEXT,moves TEXT,player_color TEXT,elo INTEGER,title TEXT,created_at TEXT,analysis TEXT,analysis_version INTEGER,source TEXT)')
        con.execute('INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?,?)', ('old',chess.STARTING_FEN,'[]','w',1500,'Old',main.now(),None,None,'maia'))
    monkeypatch.setattr(main, 'DB_PATH', db)
    main.init_db()
    main.init_db()
    assert main.get_game('old')['revision'] == 0
