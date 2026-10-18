from test_coach import client, seed_exercise
from backend import main
from datetime import datetime,timedelta,timezone


def test_only_unassisted_first_success_removes_due_puzzle(client,monkeypatch):
    seed_exercise()
    path = '/api/exercises/ex'
    def session():
        return client.post(path+'/sessions').json()
    def attempt(s, move, version=0):
        r = client.post(path+'/attempts', json={'session_id':s['id'],'move':move,'version':version})
        assert r.status_code == 200, r.text
        return r.json()
    def due():
        return client.get('/api/profile').json()['due']
    assert due() == 1
    s = session()
    bad = attempt(s, 'g6g8')
    assert not bad['scheduled'] and bad['firstTry'] and due() == 1
    # Returning to the puzzle must not reset the failed first attempt.
    resumed = session()
    assert resumed['id'] == s['id'] and resumed['version'] == 1
    good = attempt(resumed, 'g6g7', 1)
    assert good['success'] and not good['firstTry'] and not good['scheduled'] and due() == 1
    s = session()
    client.post(path+'/hint',json={'session_id':s['id']})
    good = attempt(s, 'g6g7')
    assert good['assisted'] and not good['scheduled'] and due() == 1
    s = session()
    client.post(path+'/reveal',json={'session_id':s['id']})
    assert due() == 1
    later=(datetime.now(timezone.utc)+timedelta(hours=5)).isoformat()
    monkeypatch.setattr(main,'now',lambda:later)
    s = session()
    good = attempt(s, 'g6g7')
    assert good['scheduled'] and good['firstTry'] and due() == 0
    # Scheduled exercises are retained for history and return at their due date.
    assert len(client.get('/api/exercises').json()) == 1
    s = session()
    assert s['exposure'] == 'practice'
    practice = attempt(s, 'g6g7')
    assert not practice['scheduled'] and practice['dueAt'] == good['dueAt']
    with main.database() as con:
        con.execute("UPDATE exercises SET due_at='2000-01-01' WHERE id='ex'")
    assert due() == 1


def test_due_puzzles_rotate_so_the_same_ones_do_not_always_come_first(client):
    seed_exercise()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    with main.database() as con:
        # 'ex' is due now; a and b are older, c is not due yet.
        for ply, (ident, due) in enumerate((('a', past), ('b', past), ('c', future)), start=1):
            con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at) SELECT ?,game_id,?,initial_fen,history,theme,best_move,loss,? FROM exercises WHERE id=?', (ident, ply, due, 'ex'))
    order = lambda: [e['id'] for e in client.get('/api/exercises').json()]
    assert order() == ['a', 'b', 'ex', 'c']
    # Opening a puzzle, even without answering, sends it behind the due puzzles never shown.
    client.post('/api/exercises/a/sessions')
    assert order() == ['b', 'ex', 'a', 'c']
    client.post('/api/exercises/b/sessions')
    client.post('/api/exercises/ex/sessions')
    assert order() == ['a', 'b', 'ex', 'c']
    # Reopening the active session also counts as shown.
    client.post('/api/exercises/a/sessions')
    assert order()[:3] == ['b', 'ex', 'a']
