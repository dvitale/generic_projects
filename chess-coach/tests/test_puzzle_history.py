from test_coach import client, seed_exercise
from backend import main

KEY = '7k/8/5KQ1/8/8/8/8/8 w - -'


def seed():
    seed_exercise()
    with main.database() as con:
        con.execute("UPDATE exercises SET position_key=? WHERE id='ex'", (KEY,))


def guess(client, session, move, version):
    return client.post('/api/exercises/ex/attempts', json={'session_id': session, 'move': move, 'version': version}).json()


def test_each_guess_keeps_the_hint_seen_before_it_and_progress_says_which_hint_did_not_suffice(client):
    seed()
    s = client.post('/api/exercises/ex/sessions').json()['id']
    assert not guess(client, s, 'g6g8', 0)['success']
    first = client.post('/api/exercises/ex/hint', json={'session_id': s}).json()
    assert not guess(client, s, 'g6g8', 1)['success']
    second = client.post('/api/exercises/ex/hint', json={'session_id': s}).json()
    assert guess(client, s, 'g6g7', 2)['success']
    keys = [main.puzzle_history.hint_key(h['title']) for h in second['hints']]
    assert keys[0] == 'kind' and len(keys) == 2 and len(first['hints']) == 1
    with main.database() as con:
        rows = [tuple(r) for r in con.execute("SELECT move, hint_level, hint FROM attempts WHERE session_id=? ORDER BY id", (s,))]
    assert rows == [('g6g8', 0, None), ('g6g8', 1, 'kind'), ('g6g7', 2, keys[1])]
    hints = {h['key']: h for h in client.get('/api/gaps').json()['hints']}
    assert (hints['kind']['wrong'], hints['kind']['solved']) == (1, 0)
    assert (hints[keys[1]]['solved'], hints[keys[1]]['wrong']) == (1, 0)


def test_a_wrong_move_played_again_in_a_later_session_is_named_and_listed(client):
    seed()
    s1 = client.post('/api/exercises/ex/sessions').json()['id']
    first = guess(client, s1, 'g6g8', 0)
    assert first['repeated'] is None
    # The same wrong move twice in one session is not a repetition across sessions.
    assert guess(client, s1, 'g6g8', 1)['repeated'] is None
    client.post('/api/exercises/ex/reveal', json={'session_id': s1})
    assert client.get('/api/gaps').json()['repeats'] == []
    s2 = client.post('/api/exercises/ex/sessions').json()['id']
    again = guess(client, s2, 'g6g8', 0)
    assert again['repeated']['sessions'] == 1 and again['repeated']['san'] == 'Qg8+'
    [listed] = client.get('/api/gaps').json()['repeats']
    assert (listed['exercise'], listed['san'], listed['sessions'], listed['persistent']) == ('ex', 'Qg8+', 2, True)


def test_a_puzzle_stays_persistent_until_three_sessions_without_the_repeated_move(client):
    seed_exercise()
    with main.database() as con:
        con.execute("UPDATE exercises SET position_key=? WHERE id='ex'", (KEY,))
        for i in (1, 2):
            con.execute("INSERT INTO puzzle_sessions(id,exercise_id,created_at,status,guesses,exposure) VALUES(?,?,?,?,?,?)",
                        (f's{i}', 'ex', main.now(), 'revealed', 1, 'review'))
            con.execute("INSERT INTO attempts(exercise_id,move,success,assisted,created_at,session_id,is_first,exposure) VALUES(?,?,?,?,?,?,?,?)",
                        ('ex', 'g6g8', 0, 0, main.now(), f's{i}', 1, 'review'))
        assert main.puzzle_history.persistent(con, 'ex')
        # Three later sessions without the repeated move end the persistence.
        for i in (3, 4, 5):
            con.execute("INSERT INTO puzzle_sessions(id,exercise_id,created_at,status,guesses,exposure) VALUES(?,?,?,?,?,?)",
                        (f's{i}', 'ex', main.now() + str(i), 'complete', 1, 'review'))
        assert not main.puzzle_history.persistent(con, 'ex')


def test_the_cap_holds_the_review_stage_of_a_persistent_puzzle(client):
    seed()
    with main.database() as con:
        con.execute("UPDATE exercises SET streak=2 WHERE id='ex'")
        for i in (1, 2):
            con.execute("INSERT INTO puzzle_sessions(id,exercise_id,created_at,status,guesses,exposure) VALUES(?,?,?,?,?,?)",
                        (f'old{i}', 'ex', main.now(), 'revealed', 1, 'review'))
            con.execute("INSERT INTO attempts(exercise_id,move,success,assisted,created_at,session_id,is_first,exposure) VALUES(?,?,?,?,?,?,?,?)",
                        ('ex', 'g6g8', 0, 0, main.now(), f'old{i}', 1, 'review'))
    s = client.post('/api/exercises/ex/sessions').json()['id']
    result = guess(client, s, 'g6g7', 0)
    assert result['success'] and result['scheduled']
    # Without the repeated mistake a third success would retire it, and the next review would be three days away.
    row = client.get('/api/exercises/ex').json()
    assert row['retired'] is None and row['streak'] == 2
