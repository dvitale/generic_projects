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
    assert 'stessa mossa della partita' in wrong['message']
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


def test_due_positions_rotate_so_the_same_ones_do_not_always_come_first(client):
    _, p = seed(client)
    session(client, p)  # Verifies the position and marks it as shown.
    with main.database() as con:
        for ply, ident in enumerate(('a', 'b'), start=1):
            con.execute('''INSERT INTO prevention_positions(id,game_id,ply,initial_fen,history,original_move,due_at,verification)
                SELECT ?,game_id,?,initial_fen,history,original_move,'2000-01-01T00:00:00+00:00',verification
                FROM prevention_positions WHERE id=?''', (ident, ply, p['id']))
    order = lambda: [x['id'] for x in client.get('/api/prevention').json()['positions']]
    assert order() == ['a', 'b', p['id']]
    session(client, {'id': 'a'})
    assert order() == ['b', p['id'], 'a']


def test_practice_after_closing_checks_moves_without_recording(client):
    _,p=seed(client)
    s=session(client,p)
    body=lambda move:{'session_id':s['id'],'move':move}
    assert client.post(f"/api/prevention/{p['id']}/practice",json=body('g6f5')).status_code==409
    assert attempt(client,p,s,'g6f5').json()['closed']
    before=client.get('/api/prevention').json()['stats']
    bad=client.post(f"/api/prevention/{p['id']}/practice",json=body('g6g8')).json()
    good=client.post(f"/api/prevention/{p['id']}/practice",json=body('g6f5')).json()
    assert (bad['success'],bad['san'],good['success'])==(False,'Qg8+',True)
    assert client.get('/api/prevention').json()['stats']==before
    with main.database() as con:
        assert con.execute('SELECT count(*) FROM prevention_attempts WHERE session_id=?',(s['id'],)).fetchone()[0]==1


def test_any_move_that_avoids_the_game_blunder_is_accepted():
    from backend.prevention import accepted
    e = lambda cp=None, mate=None: {'cp': cp if mate is None else (100000 - mate if mate > 0 else -100000 - mate), 'mate': mate}
    # Avoiding the blunder is enough: from -0.80, a move to -1.20 or -1.90 is not a blunder; to -2.80 it is.
    assert accepted(e(-80), e(-120))
    assert accepted(e(0), e(-110)) and accepted(e(-80), e(-270))
    assert not accepted(e(-80), e(-280))
    assert accepted(e(300), e(-90))
    # The game move itself is never accepted, whatever a deeper search now says.
    assert not accepted(e(-80), e(-90), original=True)
    # A mate against is never accepted; missing a mate is judged by the safety line only.
    assert not accepted(e(-50), e(mate=-5))
    assert not accepted(e(mate=3), e(-150))
    assert accepted(e(mate=3), e(-20))


def line(*moves):
    return {'cp': -900, 'mate': None, 'pv': list(moves)}


def test_elementary_refutations_lose_material_or_mate_within_four_plies():
    hanging = chess.Board(FEN)
    assert prevention.elementary(hanging, line('g6g8', 'a8g8'))
    assert prevention.elementary(hanging, {'cp': -100000, 'mate': -1, 'pv': []})
    # An even exchange is not a loss: the recapture inside the window restores the balance.
    trade = chess.Board('4k3/8/4p3/3q4/8/8/3Q4/4K3 w - - 0 1')
    assert not prevention.elementary(trade, line('d2d5', 'e6d5'))
    # The loss must be concrete inside the window: a queen lost on the sixth ply is calculation, not a glance.
    slow = chess.Board('4k3/8/8/8/8/8/1q6/Q3K3 w - - 0 1')
    assert not prevention.elementary(slow, line('e1f1', 'e8e7', 'f1g1', 'e7e6', 'g1h1', 'b2a1'))


def test_reach_separates_lapses_from_typical_and_complex_errors(monkeypatch):
    board = chess.Board(FEN)
    def fake(blunder, reply):
        return lambda requests: [{'moves': [{'uci': 'g6g8', 'probability': blunder}]}, {'moves': [{'uci': 'a8g8', 'probability': reply}]}]
    cases = [((0.30, 0.9), line('g6g8', 'a8g8'), 'typical'), ((0.01, 0.9), line('g6g8', 'a8g8'), 'lapse'),
             ((0.01, 0.05), line('g6g8', 'a8g8'), 'lapse')]
    for (blunder, reply), actual, status in cases:
        monkeypatch.setattr(prevention.maia, 'predict_many', fake(blunder, reply))
        assert prevention.assess_reach([(board, 'g6g8', actual, 1500)])[0]['status'] == status
    # A refutation that is neither short nor likely for the opponent asks for calculation: it belongs to Puzzle.
    monkeypatch.setattr(prevention, 'elementary', lambda *a: False)
    monkeypatch.setattr(prevention.maia, 'predict_many', fake(0.01, 0.05))
    verdict = prevention.assess_reach([(board, 'g6g8', line('g6g8', 'a8g8'), 1500)])[0]
    assert verdict['status'] == 'complex' and verdict['reply'] == 'a8g8' and verdict['level'] == 1500
    monkeypatch.setattr(prevention.maia, 'predict_many', fake(0.01, 0.20))
    assert prevention.assess_reach([(board, 'g6g8', line('g6g8', 'a8g8'), 1500)])[0]['status'] == 'lapse'
    # Without the engine line there is no evidence, and without Maia no verdict: the position stays as before.
    assert prevention.assess_reach([(board, 'g6g8', {'cp': -900, 'mate': None, 'pv': []}, 1500)]) == [None]
    monkeypatch.setattr(prevention.maia, 'available', lambda: False)
    assert prevention.assess_reach([(board, 'g6g8', line('g6g8', 'a8g8'), 1500)]) == [None]


@pytest.mark.skipif(not prevention.maia.available(), reason='modello Maia o onnxruntime assenti')
def test_real_maia_marks_the_hanging_queen_as_a_lapse_and_the_catalog_hides_other_verdicts(client):
    _, p = seed(client)
    with main.database() as con:
        reach = json.loads(con.execute('SELECT reach FROM prevention_positions WHERE id=?', (p['id'],)).fetchone()[0])
    assert reach['status'] == 'lapse' and reach['elementary'] and reach['blunderProbability'] < 0.25 and reach['level'] == 1500
    catalog = client.get('/api/prevention').json()
    assert catalog['reach'] | {'description': ''} == {'lapse': 1, 'typical': 0, 'complex': 0, 'pending': 0, 'available': True, 'description': ''}
    with main.database() as con:
        con.execute("UPDATE prevention_positions SET reach_status='typical' WHERE id=?", (p['id'],))
    catalog = client.get('/api/prevention').json()
    assert catalog['positions'] == [] and catalog['reach']['typical'] == 1
    # Positions indexed before the rule (or by an older version) are judged again by the backfill.
    with main.database() as con:
        con.execute('UPDATE prevention_positions SET reach=NULL,reach_status=NULL WHERE id=?', (p['id'],))
    assert client.get('/api/prevention').json()['reach']['pending'] == 1
    prevention.backfill_reach(main.database, main.load_analysis)
    assert [x['id'] for x in client.get('/api/prevention').json()['positions']] == [p['id']]


def test_positions_left_to_puzzle_leave_the_training_plan_and_the_game_pack(client):
    game, p = seed(client)
    plan = lambda: json.dumps(client.get('/api/training-plan').json())
    assert p['id'] in plan()
    with main.database() as con:
        con.execute("UPDATE prevention_positions SET reach_status='complex' WHERE id=?", (p['id'],))
        listed = con.execute('SELECT count(*) FROM prevention_positions WHERE ' + prevention.training_schedule.PREVENTION_LISTED.format(''))
        assert listed.fetchone()[0] == 0
    assert p['id'] not in plan()
    pack = client.get(f"/api/study/games/{game['id']}/pack")
    assert pack.status_code != 200 or p['id'] not in pack.text
