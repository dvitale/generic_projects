import chess

from backend import diagnosis, gaps, main
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


def describe(fen):
    import chess
    from backend import diagnosis
    from backend.engine import evaluator
    board = chess.Board(fen)
    best = evaluator.evaluate(board, nodes=diagnosis.NODES)
    passed = diagnosis.threat_board(board)
    threat = diagnosis.player_view(evaluator.evaluate(passed, nodes=diagnosis.NODES))
    return diagnosis.solution(board, best, {'move': threat['pv'][0], 'san': threat['san'][0], 'evaluation': threat})


def test_solution_kind_tells_forcing_moves_from_quiet_ones(client):
    mate = describe('6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1')
    assert (mate['kind'], mate['san'], mate['forcing']) == ('forcing', 'Rd8#', ['check'])
    # Qd4 and Qg4 neither check nor capture, but threaten Qxg7#. Both win by about +10 and Stockfish's pick between
    # them changes with threads and hash contents, so either is accepted: the kind of move is what is tested.
    quiet = describe('r4rk1/5pp1/8/8/8/2B5/5PPP/3QR1K1 w - - 0 1')
    assert quiet['kind'] == 'quiet_threat' and quiet['san'] in ('Qd4', 'Qg4') and quiet['threat']['san'] == 'Qxg7#'
    # With a free tempo Black would mate with ...Ra1+: the luft takes that resource away.
    luft = describe('r5k1/5ppp/8/8/8/1Q6/5PPP/6K1 w - - 0 1')
    assert luft['kind'] == 'prophylaxis' and luft['stopped']['san'] == 'Ra1+'
    # A quiet opening position: no forcing move, no threat to make or stop.
    calm = describe('r1b1k2r/ppppqppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 1')
    assert calm['kind'] == 'improvement' and calm['facts']['piece'] in 'KQRBNP'


def test_hints_for_a_quiet_solution_never_point_to_checks_and_captures(client):
    board = chess.Board('r5k1/5ppp/8/8/8/1Q6/5PPP/6K1 w - - 0 1')
    found = diagnosis.solution_of(board)
    first, second = diagnosis.hints(board, found)
    assert found['kind'] == 'prophylaxis' and first['title'] == 'Profilassi' and first['text'].startswith('Non è uno scacco né una cattura')
    # The opponent's idea is named in the first hint, with Stockfish's line from the passed move.
    assert 'idea migliore del Nero. Se toccasse al Nero, Stockfish giocherebbe 1… Ra1+' in first['text']
    assert second['squares'] == [chess.square_name(chess.Move.from_uci(found['move']).from_square)] and second['text'].endswith('è il pezzo che muove.')


def test_a_prophylactic_move_names_the_line_it_closes():
    # Puzzle 16-25B: 25. c5 cuts the a7 bishop off d4, e3 and f2, next to White's king, and leaves it no active square.
    board = chess.Board('3q1rk1/b4pp1/3Np1np/1R2P3/2P1Q3/7P/P2B1PP1/6K1 w - - 5 25')
    assert diagnosis.blocked(board, chess.Move.from_uci('c4c5')) == {
        'piece': 'B', 'square': 'a7', 'lost': ['d4', 'e3', 'f2'], 'near': ['f2'], 'king': True}
    found = {'move': 'c4c5', 'kind': 'prophylaxis', 'stopped': {'san': 'f5', 'before': {'pv': ['f7f5', 'e4d3', 'g8h7', 'd3c3', 'd8h4']}}}
    first, last = diagnosis.hints(board, found)
    assert 'Stockfish giocherebbe 25… f5 26. Qd3 Kh7 27. Qc3 Qh4.' in first['text']
    assert last['text'] == 'Guarda il tuo pedone in c4: è il pezzo che muove. Il pezzo avversario da frenare è l’alfiere in a7.'


def test_obstacle_is_stored_and_missed_solutions_are_counted_by_kind(stocked):
    problem = start(stocked, band=0)
    pid, sid = problem['puzzle']['id'], problem['sessionId']
    saved = diagnose(stocked, 'problem', pid, sid, assessment='much_better', obstacle='inconclusive', candidate='a7a6', candidate_reason='inconclusive').json()
    assert saved['answer']['obstacle'] == 'inconclusive' and saved['ruleVersion'] == 2
    assert saved['search'] == 'missed_solution' and saved['evidence']['solution']['kind'] == 'forcing'
    assert stocked.get('/api/diagnoses/summary').json()['recent']['solutions']['forcing'] == 1


def fake_maia(monkeypatch, moves):
    asked = []
    monkeypatch.setattr(diagnosis.maia, 'available', lambda: True)
    monkeypatch.setattr(diagnosis.maia, 'predict', lambda fen, own, other: asked.append(own) or {'moves': [{'uci': u, 'probability': p} for u, p in moves]})
    return asked


def test_the_tempting_move_is_maias_likeliest_mistake_refuted_without_naming_the_solution(monkeypatch):
    board = chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    found = diagnosis.solution_of(board)
    assert found['move'] == 'g6g7'
    asked = fake_maia(monkeypatch, [('g6g7', 0.5), ('g6g8', 0.3), ('f6f7', 0.2)])
    tempt = diagnosis.tempting(board, found, 3000)
    assert asked == [2600] and tempt['san'] == 'Qg8+' and tempt['line'][:2] == ['g6g8', 'h8g8']
    # A missed mate would name the solution: the outcomes are compared in words instead.
    assert tempt['text'] == ('La mossa che viene più naturale è Qg8+: al tuo livello la sceglierebbe circa un giocatore su 3. '
                             'Non funziona: con la mossa giusta sei in forte vantaggio, dopo Qg8+ la posizione è in equilibrio. '
                             'La risposta più forte è 1… Kxg8.')
    titles = [h['title'] for h in diagnosis.hints(board, found, tempt)]
    assert titles == ['Mossa forzante', 'La mossa che tenta', 'Dove guardare']
    # The king move stalemates: there is no reply to name.
    fake_maia(monkeypatch, [('f6f7', 0.6), ('g6g7', 0.3)])
    stalemate = diagnosis.tempting(board, found, 1500)
    assert stalemate['text'].endswith('Non funziona: con la mossa giusta sei in forte vantaggio, dopo Kf7 la posizione è in equilibrio.')
    # A rare move, or no Maia at all, gives no hint.
    fake_maia(monkeypatch, [('g6g7', 0.95), ('g6g8', 0.05)])
    assert diagnosis.tempting(board, found, 1500) is None
    monkeypatch.setattr(diagnosis.maia, 'available', lambda: False)
    assert diagnosis.tempting(board, found, 1500) is None


def test_candidate_moves_hide_the_solution_among_wrong_moves_worth_considering(monkeypatch):
    board = chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    found = diagnosis.solution_of(board)
    fake_maia(monkeypatch, [('g6g7', 0.5), ('g6g8', 0.3), ('f6f7', 0.2)])
    tempt = diagnosis.tempting(board, found, 1500)
    choices = diagnosis.candidates(board, found, 1500, tempt)
    # The tempting move comes first, then a wrong move from the engine or Maia; alphabetical, so the order tells nothing.
    assert 'g6g8' in choices['moves'] and 'g6g7' in choices['moves'] and len(choices['moves']) == 3
    assert choices['sans'] == sorted(choices['sans'])
    assert choices['text'].startswith(f"La soluzione è una di queste mosse: {choices['sans'][0]}, {choices['sans'][1]} o {choices['sans'][2]}.")
    assert choices['text'].endswith('le altre 2 non reggono.')
    titles = [h['title'] for h in diagnosis.hints(board, found, tempt, choices)]
    assert titles == ['Mossa forzante', 'La mossa che tenta', 'Mosse candidate', 'Dove guardare']
    # Without Maia only Stockfish's best moves are left, and here they all win too: no wrong move to offer.
    monkeypatch.setattr(diagnosis.maia, 'available', lambda: False)
    assert diagnosis.candidates(board, found, 1500) is None
    assert [h['title'] for h in diagnosis.hints(board, found)] == ['Mossa forzante', 'Dove guardare']


FORK = '4k2r/8/8/8/3n4/8/7P/R3K3 w Q - 0 1'  # After 1. h3 the black knight forks king and rook with Nc2+.


def test_the_motif_of_an_own_puzzle_is_read_from_the_opponents_last_move():
    board = chess.Board(FORK)
    board.push_uci('h2h3')
    assert diagnosis.motif(board, {'line': ['Nc2+', 'Kd2', 'Nxa1']}) == 'fork'
    # A line that wins nothing, or a puzzle with no previous move, has no motif.
    assert diagnosis.motif(board, {'line': ['Nc2+', 'Kd2', 'Nd4']}) is None
    assert diagnosis.motif(chess.Board(FORK), {'line': ['h3']}) is None


def test_own_puzzle_hints_name_the_motif_and_gaps_count_it(client, monkeypatch):
    monkeypatch.setattr(diagnosis, 'tempting', lambda *a: None)
    monkeypatch.setattr(diagnosis, 'candidates', lambda *a: None)
    with main.database() as con:
        con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    ('forked', FORK, '["h2h3"]', 'b', 1500, 'Forchetta', main.now(), None, None, 'pgn'))
        con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at) VALUES(?,?,?,?,?,?,?,?,?)',
                    ('fork-ex', 'forked', 1, FORK, '["h2h3"]', 'Calcolo e mosse candidate', 'd4c2', 500, main.now()))
    path = '/api/exercises/fork-ex'
    s = client.post(path + '/sessions').json()
    client.post(path + '/hint', json={'session_id': s['id']})
    hints = client.post(path + '/hint', json={'session_id': s['id']}).json()['hints']
    assert hints[1] == {'level': 2, 'title': 'Motivo', 'text': '', 'themes': ['fork']}
    client.post(path + '/reveal', json={'session_id': s['id']})
    with main.database() as con:
        records, missing = gaps.own_records(con)
    assert records[0]['keys'][0] == 'kind:forcing' and 'theme:fork' in records[0]['keys'] and not missing
