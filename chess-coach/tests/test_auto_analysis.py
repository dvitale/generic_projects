import time
import pytest
from backend import main
from test_coach import client, seed_exercise
from test_prevention import seed

@pytest.mark.parametrize('fen,move,color,actor,result',[
    ('7k/8/5KQ1/8/8/8/8/8 w - - 0 1','g6g7','w','human','1-0'),
    ('8/8/8/8/8/5kq1/8/7K b - - 0 1','g3g2','w','maia','0-1'),
    ('7k/8/5KQ1/8/8/8/8/8 w - - 0 1','g6f7','w','human','1/2-1/2'),
])
def test_final_move_starts_analysis_and_survives_reloading(client,fen,move,color,actor,result):
    game=client.post('/api/games',json={'fen':fen,'color':color}).json()
    ended=client.post(f"/api/games/{game['id']}/moves",json={'move':move,'version':0,'actor':actor}).json()
    assert ended['result']==result
    ids=[key for key,job in main.jobs.items() if job['gameId']==game['id']]
    assert len(ids)==1 and main.jobs[ids[0]]['automatic']
    for _ in range(200):
        job=client.get('/api/jobs/'+ids[0]).json()
        if job['status']!='running':break
        time.sleep(.02)
    assert job['status']=='complete',job
    assert client.get('/api/games/'+game['id']).json()['analysis']['version']==1
    assert len([j for j in main.jobs.values() if j['gameId']==game['id']])==1

def test_normal_move_does_not_start_analysis(client):
    game=client.post('/api/games',json={}).json()
    moved=client.post(f"/api/games/{game['id']}/moves",json={'move':'e2e4','version':0,'actor':'human'}).json()
    assert moved['analysisJobId'] is None
    assert not any(j['gameId']==game['id'] for j in main.jobs.values())

def test_pending_analysis_is_reused_but_undo_creates_a_new_revision(client,monkeypatch):
    submitted=[]
    monkeypatch.setattr(main.executor,'submit',lambda *args:submitted.append(args))
    game=client.post('/api/games',json={'fen':'7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}).json()
    path='/api/games/'+game['id']
    try:
        ended=client.post(path+'/moves',json={'move':'g6g7','version':0,'actor':'human'}).json()
        job=ended['analysisJobId']
        assert job and client.get(path).json()['analysisJobId']==job
        assert client.post(path+'/analysis').json()['jobId']==job
        assert len(submitted)==1
        undone=client.post(path+'/undo',json={'version':1,'revision':0}).json()
        assert undone['analysisJobId'] is None
        replay=client.post(path+'/moves',json={'move':'g6g7','version':0,'revision':1,'actor':'human'}).json()
        assert replay['analysisJobId']!=job and len(submitted)==2
    finally:
        with main.jobs_lock:
            for key in [k for k,j in main.jobs.items() if j['gameId']==game['id']]:del main.jobs[key]

def test_puzzle_and_prevention_include_source_metadata(client):
    seed_exercise()
    ex=client.get('/api/exercises').json()[0]
    assert ex['gameId']=='seed' and ex['gameTitle']=='Test' and ex['gameCreatedAt']
    game,p=seed(client)
    assert p['gameId']==game['id'] and p['title']==game['title'] and p['gameCreatedAt']
    generated=next(e for e in client.get('/api/exercises').json() if e['gameId']==game['id'])
    assert generated['gameTitle']==game['title'] and generated['ply']==p['ply']
