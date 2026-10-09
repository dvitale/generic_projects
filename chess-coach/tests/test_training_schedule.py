import json
from datetime import datetime,timedelta,timezone
from test_coach import client,seed_exercise
from backend import main,training_schedule as schedule


def test_review_ladder_failure_and_early_practice(client,monkeypatch):
    seed_exercise();clock=datetime.now(timezone.utc);monkeypatch.setattr(main,'now',lambda:clock.isoformat())
    path='/api/exercises/ex'
    def start():return client.post(path+'/sessions').json()
    def attempt(s,move='g6g7',version=0):return client.post(path+'/attempts',json={'session_id':s['id'],'version':version,'move':move}).json()
    first=start();good=attempt(first)
    assert good['scheduled']
    assert datetime.fromisoformat(good['dueAt'])==clock+timedelta(hours=4)
    assert client.get('/api/training-plan').json()['completed']==1
    early=start();assert early['exposure']=='practice'
    assert not attempt(early)['scheduled']
    assert client.get('/api/training-plan').json()['completed']==1
    clock+=timedelta(hours=5)
    second=start();assert second['exposure']=='review'
    good=attempt(second)
    assert datetime.fromisoformat(good['dueAt'])==clock+timedelta(days=1)
    clock+=timedelta(days=1,seconds=1)
    s=start();bad=attempt(s,'g6g8');assert not bad['success']
    assert client.get('/api/profile').json()['due']==1
    assert client.get('/api/training-plan').json()['waiting']==1
    assert attempt(s,version=1)['success']
    retry=start();assert retry['exposure']=='practice'
    assert not attempt(retry)['scheduled']
    clock+=timedelta(hours=4,seconds=1)
    fresh=attempt(start());assert fresh['scheduled']
    assert datetime.fromisoformat(fresh['dueAt'])==clock+timedelta(hours=4)


def test_plan_settings_limits_timezone_and_duplicate_positions(client):
    seed_exercise()
    with main.database() as con:
        row=con.execute("SELECT * FROM exercises WHERE id='ex'").fetchone()
        con.execute('INSERT INTO prevention_positions(id,game_id,ply,initial_fen,history,original_move,due_at) VALUES(?,?,?,?,?,?,?)',
          ('bp','seed',0,row['initial_fen'],'[]','g6g8',row['due_at']))
        for i in range(6):
            con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at) VALUES(?,?,?,?,?,?,?,?,?)',
                        (f'ex{i}','seed',i+1,row['initial_fen'],'[]','Test','g6g7',1000,row['due_at']))
        p=schedule.plan(con,'2030-03-30T23:30:00+00:00')
        assert p['today']=='2030-03-31'
        assert len(p['queue'])==3
        assert len({(x['gameId'],x['ply']) for x in p['queue']})==len(p['queue'])
    settings={'minutes':5,'newLimit':1,'weekdays':[0,1,2,3,4,5,6],'timezone':'Europe/Rome'}
    p=client.post('/api/training-plan/settings',json=settings).json()
    assert p['target']==2 and len(p['queue'])==1
    assert client.get('/api/training-plan').json()['settings']==settings
    assert client.post('/api/training-plan/settings',json={**settings,'weekdays':[]}).status_code==422
    assert client.post('/api/training-plan/settings',json={**settings,'weekdays':[7]}).status_code==422
    assert client.post('/api/training-plan/settings',json={**settings,'timezone':'bad/zone'}).status_code==422
    with main.database() as con:
        con.execute("UPDATE training_settings SET weekdays='[0]'")
        p=schedule.plan(con,'2030-03-31T12:00:00+00:00')
        assert not p['activeDay'] and not p['queue']


def test_prevention_schedule_shares_rules(client):
    from test_prevention import seed
    game,position=seed(client)
    path='/api/prevention/'+position['id']
    s=client.post(path+'/sessions').json()
    r=client.post(path+'/attempts',json={'session_id':s['id'],'version':0,'move':'g6g7'}).json()
    assert r['scheduled']
    p=client.get('/api/training-plan').json()
    assert p['completed']==1
    assert all(x['gameId']!=game['id'] for x in p['queue'])


def test_scheduled_exercise_opens_beyond_catalog_limit(client):
    seed_exercise()
    with main.database() as con:
        row=con.execute("SELECT * FROM exercises WHERE id='ex'").fetchone()
        for i in range(101):
            con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at) VALUES(?,?,?,?,?,?,?,?,?)',
                        (f'old{i}','seed',i+1,row['initial_fen'],'[]','Test','g6g7',1000,'2000-01-01T00:00:00+00:00'))
    assert 'ex' not in {e['id'] for e in client.get('/api/exercises').json()}
    detail=client.get('/api/exercises/ex')
    assert detail.status_code==200 and detail.json()['gameId']=='seed'
    assert 'g6g7' in detail.json()['legalMoves']
    assert client.get('/api/exercises/missing').status_code==404
