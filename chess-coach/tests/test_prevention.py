import json
import chess
import pytest
from backend import main, prevention
from test_coach import client, wait_analysis

FEN='r6k/8/5KQ1/8/8/8/8/8 w - - 0 1'


def seed(client, black=False):
    board=chess.Board(FEN)
    if black:board=board.mirror()
    game=client.post('/api/games',json={'fen':board.fen(),'color':'b' if black else 'w'}).json()
    move='g3g1' if black else 'g6g8'
    r=client.post(f"/api/games/{game['id']}/moves",json={'move':move,'version':0,'revision':0,'actor':'human'})
    assert r.status_code==200
    wait_analysis(client,game['id'])
    catalog=client.get('/api/prevention').json()
    assert len(catalog['positions'])==1,catalog
    p=catalog['positions'][0]
    return game,p


def session(client,p):
    r=client.post(f"/api/prevention/{p['id']}/sessions")
    assert r.status_code==200,r.text
    assert not r.json().get('excluded'),r.text
    return r.json()


def attempt(client,p,s,move):
    return client.post(f"/api/prevention/{p['id']}/attempts",json={'session_id':s['id'],'version':s['version'],'move':move})


@pytest.mark.parametrize('black',[False,True])
def test_accepts_non_best_non_losing_move_for_both_colors_and_does_not_change_game(client,black):
    game,p=seed(client,black)
    assert p['turn']==('b' if black else 'w')
    assert not {'original_move','best','verification'} & p.keys()
    s=session(client,p)
    assert session(client,p)['id']==s['id']
    move='g3f4' if black else 'g6f5'
    result=attempt(client,p,s,move)
    assert result.status_code==200,result.text
    result=result.json()
    assert result['success'] and result['closed'] and result['firstTry']
    assert result['example']['pv'][0]!=move # A mate in one exists; this move is still accepted.
    assert result['original']['san'] in {'Qg8+','Qg1+'}
    assert attempt(client,p,s,move).status_code==409
    assert client.get('/api/prevention').json()['stats']=={'firstAttempts':1,'firstSuccesses':1}
    assert client.get('/api/games/'+game['id']).json()['moves']==['g3g1' if black else 'g6g8']


def test_retry_illegal_reveal_and_practice_do_not_inflate_independent_success(client):
    _,p=seed(client);s=session(client,p)
    assert attempt(client,p,s,'g6f5').json()['success']
    s=session(client,p)
    # Make a valid-looking but illegal king move; no attempt should be recorded.
    before=client.get('/api/prevention').json()['stats']
    assert attempt(client,p,s,'f6f8').status_code==422
    assert client.get('/api/prevention').json()['stats']==before
    wrong=attempt(client,p,s,'g6g8').json()
    assert not wrong['success'] and not wrong['closed'] and wrong['original'] is None and wrong['example'] is None
    assert attempt(client,p,s,'g6g7').status_code==409
    s['version']=wrong['version']
    good=attempt(client,p,s,'g6g7').json()
    assert good['success'] and not good['firstTry']
    prior=client.get('/api/prevention').json()['stats']
    s=session(client,p)
    assert s['exposure']=='practice'
    result=client.post(f"/api/prevention/{p['id']}/reveal",json={'session_id':s['id'],'version':s['version']}).json()
    assert result['closed'] and result['assisted'] and not result['success']
    assert client.get('/api/prevention').json()['stats']==prior


def test_first_failure_then_success_remains_failed_first_attempt(client):
    _,p=seed(client);s=session(client,p)
    wrong=attempt(client,p,s,'g6g8').json();s['version']=wrong['version']
    assert attempt(client,p,s,'g6g7').json()['success']
    assert client.get('/api/prevention').json()['stats']=={'firstAttempts':1,'firstSuccesses':0}
    assert client.get('/api/prevention').json()['positions'][0]['streak']==0


def test_selection_filters_lost_positions_mates_and_non_losing_original_moves():
    v=lambda cp,mate=None:{'cp':cp,'mate':mate}
    assert prevention.eligible(v(20),v(-300))
    assert not prevention.eligible(v(-400),v(-900))
    assert not prevention.eligible(v(800),v(0)) # Drawing is accepted; not an avoidance exercise.
    assert not prevention.eligible(v(100000,1),v(700))
    assert prevention.eligible(v(0),v(-100000,-2))
    assert prevention.safe(v(-100)) and not prevention.safe(v(-101))
    assert prevention.safe(v(100000,5)) and not prevention.safe(v(-100000,-10))


def test_backfill_is_idempotent_and_undo_keeps_original_position(client):
    game,p=seed(client)
    main.init_db();main.init_db()
    assert len(client.get('/api/prevention').json()['positions'])==1
    r=client.post(f"/api/games/{game['id']}/undo",json={'version':1,'revision':0})
    assert r.status_code==200,r.text
    current=client.get('/api/prevention').json()['positions'][0]
    assert current['id']==p['id'] and current['fen']==p['fen'] and current['gameId']!=game['id']
    assert session(client,current)['version']==0


def test_deep_verification_can_exclude_false_candidates(client,monkeypatch):
    _,p=seed(client)
    monkeypatch.setattr(prevention.evaluator,'compare',lambda *a,**k:({'cp':0,'mate':None},{'cp':0,'mate':None},0))
    response=client.post(f"/api/prevention/{p['id']}/sessions").json()
    assert response['excluded']
    assert client.get('/api/prevention').json()['positions']==[]
    assert client.post(f"/api/prevention/{p['id']}/sessions").status_code==409


def test_catalog_uses_all_personal_decisions_not_just_three_critical_moments(client):
    g=client.post('/api/games',json={}).json()
    moves=['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4','g8f6','d2d3']
    board=chess.Board();decisions=[]
    for ply,uci in enumerate(moves):
        decisions.append({'ply':ply,'fen':board.fen(),'played':uci,'best':{'cp':0,'mate':None},'actual':{'cp':-400,'mate':None}})
        board.push_uci(uci)
    with main.database() as con:
        row=dict(main.find_game(con,g['id']));row['moves']=json.dumps(moves)
        prevention.seed_game(con,row,{'decisions':decisions,'critical':decisions[:3]},main.now())
    positions=client.get('/api/prevention').json()['positions']
    assert sorted(p['ply'] for p in positions)==[0,2,4,6,8]
    assert all(p['turn']=='w' for p in positions)
