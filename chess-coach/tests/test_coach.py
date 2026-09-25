import json
import time
import chess
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.engine import evaluator


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'coach.sqlite3')
    with TestClient(main.app) as c:
        yield c


def test_game_legality_versions_and_persistence(client):
    g = client.post('/api/games', json={}).json()
    path = '/api/games/' + g['id'] + '/moves'
    assert client.post(path, json={'move':'e2e5','version':0,'actor':'human'}).status_code == 422
    assert client.post(path, json={'move':'e2e4','version':0,'actor':'maia'}).status_code == 409
    assert client.post(path, json={'move':'e2e4','version':0,'actor':'human'}).json()['version'] == 1
    assert client.post(path, json={'move':'e2e4','version':0,'actor':'human'}).status_code == 409
    assert client.get('/api/games/' + g['id']).json()['moves'] == ['e2e4']
    assert client.post('/api/games', json={}, headers={'origin':'https://example.com'}).status_code == 403


def test_special_moves_and_black_scores(client):
    positions = [
        ('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7a8n'),
        ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'e1g1'),
        ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'e5d6'),
    ]
    for fen, move in positions:
        g = client.post('/api/games', json={'fen':fen}).json()
        assert client.post(f"/api/games/{g['id']}/moves", json={'move':move,'version':0,'actor':'human'}).status_code == 200
    board = chess.Board('4k3/8/8/8/8/3q4/8/4K3 b - - 0 1')
    assert board.is_valid()
    evaluation = evaluator.evaluate(board, nodes=10000)
    assert evaluation['perspective'] == 'b' and evaluation['cp'] > 500


def seed_exercise():
    # White can mate with Qg7; Qg8+ lets the king capture the queen.
    fen = '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'
    with main.database() as con:
        con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)', ('seed',fen,'[]','w',1500,'Test',main.now(),None,None,'pgn'))
        con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    ('ex','seed',0,fen,'[]','Riconoscere il matto','g6g7',1000,main.now()))
    return 'ex'


def test_puzzle_first_attempt_retry_hint_and_early_practice(client):
    ex = seed_exercise()
    path = '/api/exercises/' + ex
    assert 'best_move' not in client.get('/api/exercises').json()[0]
    s = client.post(path + '/sessions').json()
    assert client.post(path + '/sessions').json()['id'] == s['id']
    bad = client.post(path + '/attempts', json={'move':'g6g8','session_id':s['id'],'version':0})
    assert bad.status_code == 200, bad.text
    assert not bad.json()['success'] and bad.json()['best'] is None
    assert client.post(path + '/attempts', json={'move':'g6g7','session_id':s['id'],'version':0}).status_code == 409
    good = client.post(path + '/attempts', json={'move':'g6g7','session_id':s['id'],'version':1}).json()
    assert good['success'] and good['closed']
    p = client.get('/api/profile').json()
    assert p['independentAttempts'] == 1 and p['unaidedSuccesses'] == 0
    practice = client.post(path + '/sessions').json()
    assert practice['exposure'] == 'practice'
    assert client.post(path+'/hint',json={'session_id':practice['id']}).status_code == 200
    assisted = client.post(path+'/attempts',json={'move':'g6g7','session_id':practice['id'],'version':0}).json()
    assert assisted['success'] and assisted['assisted']
    assert client.get('/api/profile').json()['unaidedSuccesses'] == 0
    assert client.get('/api/exercises').json()[0]['streak'] == 0


def test_reveal_and_review_schedule(client):
    seed_exercise()
    s = client.post('/api/exercises/ex/sessions').json()
    result = client.post('/api/exercises/ex/reveal',json={'session_id':s['id']}).json()
    assert result['closed'] and result['assisted'] and result['best']['pv']
    assert client.post('/api/exercises/ex/reveal',json={'session_id':s['id']}).status_code == 409
    with main.database() as con:
        con.execute("UPDATE exercises SET due_at='2000-01-01' WHERE id='ex'")
    s = client.post('/api/exercises/ex/sessions').json()
    assert s['exposure'] == 'review'
    result = client.post('/api/exercises/ex/attempts',json={'session_id':s['id'],'version':0,'move':'g6g7'}).json()
    assert result['success']
    assert client.get('/api/profile').json()['unaidedSuccesses'] == 1
    assert client.get('/api/exercises').json()[0]['streak'] == 1


def wait_analysis(client, game_id):
    job_id = client.post(f'/api/games/{game_id}/analysis').json()['jobId']
    for _ in range(300):
        job = client.get('/api/jobs/' + job_id).json()
        if job['status'] != 'running':
            assert job['status'] == 'complete', job
            return job['result']
        time.sleep(.05)
    pytest.fail('analysis timed out')


def test_drill_budget_and_only_new_decisions_analyzed(client):
    assert len(client.get('/api/drills').json()) == 5
    g = client.post('/api/drills/italiana/start',json={'target':3}).json()
    assert g['drill']['startPly'] == 6 and not g['drill']['complete']
    while not g['drill']['complete']:
        g = client.post(f"/api/games/{g['id']}/moves",json={'move':g['legalMoves'][0],'version':g['version'],'actor':'human' if g['turn']==g['playerColor'] else 'maia'}).json()
    assert g['drill']['decisions'] == 3
    assert client.post(f"/api/games/{g['id']}/moves",json={'move':g['legalMoves'][0],'version':g['version'],'actor':'maia'}).status_code == 409
    result = wait_analysis(client,g['id'])
    assert len(result['decisions']) == 3
    assert all(d['ply']>=6 for d in result['decisions'])


def test_import_analysis_and_personal_drill(client):
    body={'pgn':'[White "Test"]\n[Black "Other"]\n\n1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *','color':'w'}
    response=client.post('/api/import',json=body)
    assert response.status_code==200,response.text
    g=response.json()
    assert client.post('/api/import',json=body).json()['id']==g['id']
    analysis=wait_analysis(client,g['id'])
    assert analysis['reviewVersion'] == 3 and len(analysis['moves']) == 6
    board=chess.Board()
    for entry,move in zip(analysis['moves'],g['moves']):
        assert entry['fen'] == board.fen() and entry['played'] == move
        assert entry['actual']['perspective'] == ('w' if board.turn else 'b')
        assert entry['isPlayer'] == (board.turn == chess.WHITE)
        choices = entry['stockfishCandidates']
        assert len(choices) == min(3, board.legal_moves.count())
        assert choices[0] == entry['best']
        assert len({choice['pv'][0] for choice in choices}) == len(choices)
        assert [choice['cp'] for choice in choices] == sorted([choice['cp'] for choice in choices], reverse=True)
        for choice in choices:
            assert choice['perspective'] == ('w' if board.turn else 'b')
            assert chess.Move.from_uci(choice['pv'][0]) in board.legal_moves
            line = board.copy()
            for uci, san in zip(choice['pv'], choice['san']):
                assert line.san(chess.Move.from_uci(uci)) == san
                line.push_uci(uci)
        board.push_uci(move)
    assert any(d['played']=='h5e5' and d['loss']>180 for d in analysis['critical'])
    exs=client.get('/api/exercises').json()
    assert exs
    drill=client.post('/api/drills/personal:'+exs[0]['id']+'/start',json={}).json()
    assert drill['fen']==exs[0]['fen']
    assert drill['playerColor']==exs[0]['turn']
    assert client.post('/api/import',json={'pgn':'1. e5 *'}).status_code==422


def test_forced_moves_are_in_step_review_but_not_personal_weaknesses(client):
    g=client.post('/api/games',json={'color':'b','fen':'k7/8/2KQ4/8/8/8/8/8 b - - 0 1'}).json()
    assert g['legalMoves'] == ['a8a7']
    assert client.post(f"/api/games/{g['id']}/moves",json={'move':'a8a7','version':0,'actor':'human'}).status_code == 200
    analysis=wait_analysis(client,g['id'])
    assert len(analysis['moves']) == 1 and analysis['moves'][0]['forced']
    assert analysis['moves'][0]['label'] == 'Mossa obbligata'
    assert len(analysis['moves'][0]['stockfishCandidates']) == 1
    assert analysis['decisions'] == [] and analysis['critical'] == []
