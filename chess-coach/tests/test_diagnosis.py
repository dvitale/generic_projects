from test_problems import client, stocked, start  # noqa: F401
from test_coach import wait_analysis
from test_prevention import attempt, seed, session
from test_problems import play


def context(client, kind, target, session_id):
    r = client.post('/api/diagnoses/context', json={'kind': kind, 'target_id': target, 'session_id': session_id})
    assert r.status_code == 200, r.text
    return r.json()


def diagnose(client, kind, target, session_id, **answer):
    body = {'kind': kind, 'target_id': target, 'session_id': session_id, 'confidence': 'moderate', **answer}
    return client.post('/api/diagnoses', json=body)


def test_problem_diagnosis_separates_a_rejected_solution_and_is_saved_once(stocked):
    problem = start(stocked, band=0)
    pid, sid = problem['puzzle']['id'], problem['sessionId']
    ctx = context(stocked, 'problem', pid, sid)
    assert ctx['color'] == 'b' and {'uci': 'd5d1', 'san': 'Rd1+'} in ctx['playerMoves']
    # The threat board gives the move to White, the opponent of the solver.
    assert ctx['threatFen'].split()[1] == 'w' and ctx['threatMoves']
    r = diagnose(stocked, 'problem', pid, sid, assessment='much_better', candidate='d5d1', candidate_reason='calculation')
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved['search'] == 'rejected_solution' and saved['evidence']['candidate']['sound']
    assert saved['evidence']['engineBand'] == 'much_better' and saved['evidence']['bandGap'] == 0
    assert 'pessimistic' not in saved['reading'] and 'optimistic' not in saved['reading']
    again = diagnose(stocked, 'problem', pid, sid, assessment='much_worse')
    assert again.json()['id'] == saved['id'] and again.json()['search'] == 'rejected_solution'
    assert context(stocked, 'problem', pid, sid)['existing']['id'] == saved['id']
    # The diagnosis does not close or rate the problem: the solution can still be revealed.
    assert stocked.get('/api/problems').json()['attempts'] == 0
    assert stocked.post(f'/api/problems/sessions/{sid}/reveal', json={'step': 1}).status_code == 200
    summary = stocked.get('/api/diagnoses/summary').json()
    assert summary['total'] == 1 and summary['byKind']['problem'] == 1
    assert summary['recent']['counts']['rejected_solution'] == 1 and summary['calibration']['moderate'] == {'total': 1, 'matched': 1}


def test_problem_diagnosis_flags_pessimism_and_needs_an_open_session(stocked):
    problem = start(stocked, band=0)
    pid, sid = problem['puzzle']['id'], problem['sessionId']
    assert diagnose(stocked, 'problem', pid, sid, assessment='equal', threat='d5d1').status_code == 422
    saved = diagnose(stocked, 'problem', pid, sid, assessment='much_worse', feared_lost=True, threat='c3c4', candidate='a7a6').json()
    assert saved['search'] == 'missed_solution' and not saved['evidence']['candidate']['sound']
    # c4 leaves the back-rank mate intact (a3 would not: it opens a2). A phantom threat.
    assert {'pessimistic', 'phantom_threat'} <= set(saved['reading'])
    closed = start(stocked, band=1)
    stocked.post(f"/api/problems/sessions/{closed['sessionId']}/reveal", json={'step': 1})
    assert diagnose(stocked, 'problem', closed['puzzle']['id'], closed['sessionId'], assessment='equal').status_code == 409
    assert diagnose(stocked, 'puzzle', 'missing', 'missing', assessment='equal').status_code == 404


def test_prevention_diagnosis_recognises_a_concrete_threat(client):
    _, p = seed(client)
    s = session(client, p)
    ctx = context(client, 'prevention', p['id'], s['id'])
    assert ctx['color'] == 'w' and any(m['uci'] == 'a8a6' for m in ctx['threatMoves'])
    r = diagnose(client, 'prevention', p['id'], s['id'], assessment='worse', threat='a8a6', candidate='g6g7')
    assert r.status_code == 200, r.text
    saved = r.json()
    # White mates in one, but if White passed, ...Ra6+ would skewer king and queen: a concrete threat.
    assert saved['search'] == 'rejected_solution' and saved['reading'] == ['pessimistic']
    assert saved['evidence']['statedThreat']['san'] == 'Ra6+' and saved['evidence']['statedThreat']['concrete']
    assert saved['evidence']['threat']['real'] is True


def test_puzzle_diagnosis_counts_failed_attempts_as_candidates(client):
    game = client.post('/api/games', json={'fen': '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}).json()
    client.post(f"/api/games/{game['id']}/moves", json={'move': 'g6g8', 'version': 0, 'revision': 0, 'actor': 'human'})
    wait_analysis(client, game['id'])
    ex = client.get('/api/exercises').json()[0]
    s = client.post(f"/api/exercises/{ex['id']}/sessions").json()
    for version, move in enumerate(['g6g8', 'g6g8', 'f6g5']):
        r = client.post(f"/api/exercises/{ex['id']}/attempts", json={'session_id': s['id'], 'version': version, 'move': move})
        assert r.status_code == 200 and not r.json()['success'], r.text
    # Each failed move once, in the order it was tried.
    assert context(client, 'puzzle', ex['id'], s['id'])['tried'] == [{'uci': 'g6g8', 'san': 'Qg8+'}, {'uci': 'f6g5', 'san': 'Kg5'}]
    saved = diagnose(client, 'puzzle', ex['id'], s['id'], assessment='much_better').json()
    assert saved['search'] == 'missed_solution' and saved['evidence']['tried'] == ['Qg8+', 'Kg5']


def test_prevention_and_problem_diagnoses_list_the_moves_already_tried(client, stocked):
    _, p = seed(client)
    s = session(client, p)
    assert context(client, 'prevention', p['id'], s['id'])['tried'] == []
    assert not attempt(client, p, s, 'g6g8').json()['success']
    assert [m['san'] for m in context(client, 'prevention', p['id'], s['id'])['tried']] == ['Qg8+']
    problem = start(stocked, band=0)
    pid, sid = problem['puzzle']['id'], problem['sessionId']
    assert play(stocked, problem, 'a7a6', 1).json()['correct'] is False
    assert context(stocked, 'problem', pid, sid)['tried'] == [{'uci': 'a7a6', 'san': 'a6'}]
    assert diagnose(stocked, 'problem', pid, sid, assessment='much_better').json()['evidence']['tried'] == ['a6']


def test_puzzle_practice_opens_only_after_closing_and_records_nothing(client):
    game = client.post('/api/games', json={'fen': '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}).json()
    client.post(f"/api/games/{game['id']}/moves", json={'move': 'g6g8', 'version': 0, 'revision': 0, 'actor': 'human'})
    wait_analysis(client, game['id'])
    ex = client.get('/api/exercises').json()[0]
    s = client.post(f"/api/exercises/{ex['id']}/sessions").json()
    url = f"/api/exercises/{ex['id']}/practice"
    assert client.post(url, json={'session_id': s['id'], 'move': 'g6g7'}).status_code == 409
    client.post(f"/api/exercises/{ex['id']}/reveal", json={'session_id': s['id']})
    attempts = client.get('/api/profile').json()['attempts']
    good = client.post(url, json={'session_id': s['id'], 'move': 'g6g7'}).json()
    bad = client.post(url, json={'session_id': s['id'], 'move': 'g6g8'}).json()
    assert (good['success'], good['san'], bad['success']) == (True, 'Qg7#', False)
    assert client.get('/api/profile').json()['attempts'] == attempts
