import pytest
from backend import main
from test_coach import client

def move(client,game,uci,actor):
    r=client.post(f"/api/games/{game['id']}/moves",json={'move':uci,'actor':actor,'version':game['version'],'revision':game['revision']})
    assert r.status_code==200,r.text
    return r.json()

@pytest.mark.parametrize('color,result,resigner',[('w','0-1','White'),('b','1-0','Black')])
def test_resign_persists_result_exports_pgn_and_starts_analysis(client,color,result,resigner):
    g=client.post('/api/games',json={'color':color}).json()
    g=move(client,g,'e2e4','human' if color=='w' else 'maia')
    path='/api/games/'+g['id']
    r=client.post(path+'/resign',json={'version':g['version'],'revision':g['revision']})
    assert r.status_code==200,r.text
    ended=r.json()
    assert ended['result']==result and ended['termination']=='resign'
    assert not ended['canUndo'] and ended['moves']==g['moves']
    assert client.get(path).json()['result']==result
    pgn=client.get(path+'/pgn').text
    assert f'[Result "{result}"]' in pgn and f'[Resignation "{resigner}"]' in pgn
    assert len([j for j in main.jobs.values() if j['gameId']==g['id'] and j['automatic']])==1
    assert client.post(path+'/moves',json={'move':'e7e5','version':1,'revision':ended['revision'],'actor':'maia' if color=='w' else 'human'}).status_code==409
    assert client.post(path+'/undo',json={'version':1,'revision':ended['revision']}).status_code==409
    assert client.post(path+'/resign',json={'version':1,'revision':ended['revision']}).status_code==409

def test_resign_before_any_move_saves_defeat_without_empty_analysis(client):
    g=client.post('/api/games',json={'color':'b'}).json()
    r=client.post(f"/api/games/{g['id']}/resign",json={'version':0,'revision':0}).json()
    assert r['result']=='1-0' and r['analysisJobId'] is None
    assert not any(j['gameId']==g['id'] for j in main.jobs.values())

def test_resign_tolerates_only_one_late_bot_reply(client):
    g=client.post('/api/games',json={}).json()
    g=move(client,g,'e2e4','human')
    g=move(client,g,'e7e5','maia')
    path='/api/games/'+g['id']
    assert client.post(path+'/resign',json={'version':1,'revision':0}).status_code==200
    other=client.post('/api/games',json={}).json()
    other=move(client,other,'e2e4','human')
    assert client.post(f"/api/games/{other['id']}/resign",json={'version':0,'revision':0}).status_code==409
    assert client.post(f"/api/games/{other['id']}/resign",json={'version':1,'revision':2}).status_code==409

def test_cannot_resign_imported_or_board_finished_games(client):
    imported=client.post('/api/import',json={'pgn':'1. e4 e5 *','color':'w'}).json()
    assert client.post(f"/api/games/{imported['id']}/resign",json={'version':2,'revision':0}).status_code==409
    finished=client.post('/api/games',json={'fen':'7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'}).json()
    assert client.post(f"/api/games/{finished['id']}/resign",json={'version':0,'revision':0}).status_code==409
