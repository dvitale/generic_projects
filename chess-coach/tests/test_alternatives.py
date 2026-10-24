import json
import chess
import pytest
from fastapi.testclient import TestClient
from backend import alternatives, main
from backend.engine import evaluator
from test_coach import client

# Verification cases: each position is checked with Stockfish by the tests below.
QUEEN = 'r1bqkbnr/pppp1p1p/2n3p1/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 4'  # queen attacked, several safe squares
ROOK = '6k1/5pp1/7p/8/8/1n6/5PPP/R5K1 w - - 0 1'                             # rook attacked, many answers
COUNTER = 'r1bqk2r/ppp2ppp/2np1n2/2b1N3/2B1P3/8/PPPP1PPP/RNBQK2R w KQkq - 0 5'  # attacked knight, active answer
EXCHANGE = '2r3k1/5ppp/8/8/1b6/2N5/5PPP/2R3K1 w - - 0 1'                       # pinned knight, defence by exchange
SACRIFICE = 'rnbq1rk1/pppn1ppp/4p3/3pP3/1b1P4/2NB1N2/PPP2PPP/R1BQK2R w KQ - 0 7'  # correct Bxh7+
QUIET = '8/8/8/3k4/8/8/3PK3/8 w - - 0 1'                                      # only the quiet Kd3 wins
LOST = 'r3k3/8/8/8/8/8/4P3/4K3 w - - 0 1'                                     # every move keeps a lost game


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setenv('CHESS_COACH_DISABLE_LLM', '1')


def game(client, fen, color='w'):
    return client.post('/api/games', json={'fen': fen, 'color': color}).json()


def start(client, g, mode='guide', origin='live', ply=0):
    r = client.post('/api/alternatives/episodes', json={'game_id': g['id'], 'ply': ply, 'revision': g['revision'], 'mode': mode, 'origin': origin})
    assert r.status_code == 200, r.text
    return r.json()


def reason(client, e, **answer):
    body = {'threat_none': True, 'considered_none': True} | answer
    r = client.post(f"/api/alternatives/episodes/{e['id']}/reasoning", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def attempt(client, e, move, version=None):
    version = len(e['attempts']) if version is None else version
    return client.post(f"/api/alternatives/episodes/{e['id']}/attempts", json={'move': move, 'version': version})


def guided(client, fen, color='w', **answer):
    return reason(client, start(client, game(client, fen, color)), **answer)


def test_mark_and_continue_shows_no_help_and_leaves_the_game_alone(client):
    g = game(client, QUEEN)
    e = start(client, g, mode='mark')
    assert e['status'] == 'marked' and e['hints'] == [] and e['solution'] is None and e['helpLevel'] == 0
    after = client.get('/api/games/' + g['id']).json()
    assert after['moves'] == [] and after['assistedPlies'] == [] and after['pgn'] == g['pgn']
    # The same moment is not duplicated; opening it later starts the reasoning questions.
    assert start(client, g, mode='mark')['id'] == e['id']
    assert start(client, g, mode='guide')['status'] == 'reasoning'
    assert client.get('/api/alternatives/progress').json()['collection']['liveMarks'] == 1


def test_hints_open_one_at_a_time_and_the_level_is_stored(client):
    g = game(client, QUEEN)
    e = start(client, g)
    path = f"/api/alternatives/episodes/{e['id']}"
    # Nothing is judged or hinted before the two questions are answered.
    assert client.post(path + '/hint', json={'level': 1}).status_code == 409
    assert attempt(client, e, 'h5d1').status_code == 409
    assert client.post(path + '/reasoning', json={}).status_code == 422
    e = reason(client, e, threat='g6h5', threat_none=False, considered=['h5h3'], considered_none=False)
    assert e['reasoningOrigin'] == 'live' and e['reasoning']['threatSan'] == 'gxh5' and e['reasoning']['consideredSan'] == ['Qh3']
    assert e['hints'] == [] and e['solution'] is None and 'evidence' not in e
    assert client.post(path + '/hint', json={'level': 3}).status_code == 409
    e = client.post(path + '/hint', json={'level': 1}).json()
    assert [h['level'] for h in e['hints']] == [1] and e['helpLevel'] == 1
    assert 'gxh5' in e['hints'][0]['text'] and 'concreta' in e['hints'][0]['text']
    for level in (2, 3):
        e = client.post(path + '/hint', json={'level': level}).json()
    # Levels before the suggested move never name a valid alternative.
    shown = ' '.join(h['text'] for h in e['hints'])
    assert e['helpLevel'] == 3 and not any(san in shown for san in ('Qd1', 'Qf3', 'Qe2'))
    assert e['hints'][2]['squares'] == ['h5']
    # Repeating an already opened level changes nothing; hints during the live game mark the decision as assisted.
    assert client.post(path + '/hint', json={'level': 2}).json()['helpLevel'] == 3
    assert client.get('/api/games/' + g['id']).json()['assistedPlies'] == [0]
    assert client.get(path).json()['helpLevel'] == 3


def test_several_alternatives_illegal_moves_and_deeper_verdicts(client):
    e = guided(client, QUEEN)
    assert attempt(client, e, 'h5h8').status_code == 422
    bad = attempt(client, e, 'h5h3').json()
    assert bad['feedback']['verdict'] == 'insufficient' and bad['status'] == 'searching'
    assert 'evaluation' not in bad['attempts'][0]  # No numbers while the search is open.
    assert attempt(client, bad, 'h5h3', version=0).status_code == 409
    accepted = set()
    for move in ('h5d1', 'h5f3'):
        found = attempt(client, guided(client, QUEEN), move).json()
        assert found['feedback']['verdict'] == 'valid' and found['status'] == 'reflecting'
        accepted.add(found['found']['san'])
        # The explanation follows the move the player found, not the engine's favourite.
        assert found['found']['explanation']['detail'].startswith(found['found']['san'])
    assert accepted == {'Qd1', 'Qf3'}
    valid = [a['san'] for a in found['solution']['alternatives'] if a['verdict'] == 'valid']
    assert {'Qd1', 'Qf3'} <= set(valid) and found['solution']['engine']['thresholds']['validLossCp'] == 50


@pytest.mark.parametrize('fen,good,bad', [(COUNTER, 'c4f7', 'e5f3'), (EXCHANGE, 'c3e2', 'g2g3'), (ROOK, 'a1a4', None)])
def test_active_answers_exchanges_and_simple_rook_moves(client, fen, good, bad):
    e = guided(client, fen)
    if bad:
        e = attempt(client, e, bad).json()
        assert e['feedback']['verdict'] == 'insufficient' and e['feedback']['reply']
    assert attempt(client, e, good).json()['feedback']['verdict'] == 'valid'


def test_a_sound_sacrifice_and_a_quiet_move_are_not_penalised(client):
    sacrifice = attempt(client, guided(client, SACRIFICE), 'd3h7').json()
    assert sacrifice['feedback']['verdict'] == 'valid' and 'Offri materiale' in sacrifice['feedback']['message']
    assert sacrifice['solution']['direction'] == 'Sacrificio'
    quiet = guided(client, QUIET)
    quiet = attempt(client, quiet, 'e2e3').json()
    assert quiet['feedback']['verdict'] == 'insufficient'
    assert attempt(client, quiet, 'e2d3').json()['feedback']['verdict'] == 'valid'


def test_black_perspective_is_the_players(client):
    mirrored = chess.Board(QUEEN).mirror()
    e = guided(client, mirrored.fen(), color='b')
    assert e['color'] == 'b'
    assert attempt(client, e, 'h4h6').json()['feedback']['verdict'] == 'insufficient'
    found = attempt(client, client.get(f"/api/alternatives/episodes/{e['id']}").json(), 'h4d8').json()
    assert found['feedback']['verdict'] == 'valid'
    assert found['solution']['evaluation']['perspective'] == 'b'
    assert found['solution']['threat']['san'] == 'gxh4'


def test_a_lost_position_promises_nothing(client):
    e = guided(client, LOST)
    e = attempt(client, e, 'e2e4').json()
    assert e['feedback']['verdict'] == 'insufficient' and 'molto difficile' in e['feedback']['message']
    e = client.post(f"/api/alternatives/episodes/{e['id']}/hint", json={'level': 1}).json()
    e = client.post(f"/api/alternatives/episodes/{e['id']}/hint", json={'level': 2}).json()
    assert 'resiste più a lungo' in e['hints'][1]['text']
    for level in (3, 4, 5):
        e = client.post(f"/api/alternatives/episodes/{e['id']}/hint", json={'level': level}).json()
    assert e['status'] == 'reflecting' and e['solution']['status'] == 'much_worse'
    final = e['hints'][4]
    assert 'compromessa' in final['status'] and 'Non è una prova' in final['status']


def test_answers_survive_reload_and_engine_failures_are_recoverable(client, tmp_path, monkeypatch):
    g = game(client, QUEEN)
    e = start(client, g)
    original = evaluator.evaluate

    def broken(*args, **kwargs):
        raise RuntimeError('engine down')
    monkeypatch.setattr(evaluator, 'evaluate', broken)
    r = client.post(f"/api/alternatives/episodes/{e['id']}/reasoning", json={'threat': 'g6h5', 'considered': ['h5h3']})
    assert r.status_code == 503
    saved = client.get(f"/api/alternatives/episodes/{e['id']}").json()
    assert saved['status'] == 'searching' and not saved['analysisReady'] and saved['reasoning']['considered'] == ['h5h3']
    assert client.post(f"/api/alternatives/episodes/{e['id']}/hint", json={'level': 1}).status_code == 409
    monkeypatch.setattr(evaluator, 'evaluate', original)
    e = client.post(f"/api/alternatives/episodes/{e['id']}/analyze").json()
    assert e['analysisReady']
    assert attempt(client, e, 'h5h3').json()['feedback']['verdict'] == 'insufficient'
    with TestClient(main.app) as reopened:
        again = reopened.get(f"/api/alternatives/episodes/{e['id']}").json()
    assert again['reasoning']['threatSan'] == 'gxh5' and [a['san'] for a in again['attempts']] == ['Qh3']


def test_exercises_never_change_the_pgn_and_stale_proposals_are_refused(client):
    g = game(client, QUEEN)
    r = client.post(f"/api/games/{g['id']}/moves", json={'move': 'h5e2', 'version': 0, 'revision': 0, 'actor': 'human'})
    assert r.status_code == 200
    pgn = client.get(f"/api/games/{g['id']}/pgn").text
    e = start(client, g, origin='retrospective')
    e = reason(client, e)
    assert e['reasoningOrigin'] == 'retrospective' and e['playedMove']['san'] == 'Qe2'
    e = attempt(client, e, 'h5f3').json()
    assert client.post(f"/api/alternatives/episodes/{e['id']}/apply").status_code == 409
    assert client.get(f"/api/games/{g['id']}/pgn").text == pgn
    assert client.get('/api/games/' + g['id']).json()['assistedPlies'] == []
    # Live: the game moves on while the exercise is open, so the proposal stays in the exercise.
    live = game(client, QUEEN)
    e = reason(client, start(client, live))
    e = attempt(client, e, 'h5f3').json()
    assert client.post(f"/api/games/{live['id']}/moves", json={'move': 'h5d1', 'version': 0, 'revision': 0, 'actor': 'human'}).status_code == 200
    assert client.post(f"/api/alternatives/episodes/{e['id']}/apply").status_code == 409
    assert client.get('/api/games/' + live['id']).json()['moves'] == ['h5d1']
    # Still at the same position: the found move is played through the usual game checks.
    other = game(client, QUEEN)
    e = attempt(client, reason(client, start(client, other)), 'h5f3').json()
    played = client.post(f"/api/alternatives/episodes/{e['id']}/apply")
    assert played.status_code == 200 and played.json()['moves'] == ['h5f3']


def test_reflection_classification_and_repetitions_stay_apart_from_new_positions(client):
    g = game(client, QUEEN)
    e = reason(client, start(client, g), threat='g6h5', threat_none=False, considered=['h5f3'], considered_none=False)
    path = f"/api/alternatives/episodes/{e['id']}"
    assert client.post(path + '/reflection', json={'considered': 'rejected', 'detail': 'reply'}).status_code == 409
    for level in range(1, 5):
        e = client.post(path + '/hint', json={'level': level}).json()
    assert e['hints'][3]['move'] in {'h5d1', 'h5f3', 'h5e2'}
    after = chess.Board(QUEEN)
    after.push_uci(e['hints'][3]['move'])
    reply = next(iter(after.legal_moves)).uci()
    e = client.post(path + '/prediction', json={'move': reply}).json()
    assert e['prediction']['san'] and client.post(path + '/prediction', json={'move': reply}).status_code == 409
    e = attempt(client, e, e['hints'][3]['move']).json()
    assert e['found']['level'] == 4
    e = client.post(path + '/reflection', json={'considered': 'rejected', 'detail': 'reply', 'note': 'Temevo d5'}).json()
    assert e['status'] == 'complete' and e['outcome'] == 'understood_after'
    c = e['classification']
    # The considered Qf3 was valid: the hypothesis says so, the player's own answer decides the final label.
    assert c['declared'] == 'rejected_reply' and c['inferred'] == 'rejected_reply' and c['final'] == 'rejected_reply'
    e = client.post(path + '/classification', json={'label': 'evaluation'}).json()
    assert e['classification']['final'] == 'evaluation' and e['classification']['corrected'] == 'evaluation'
    repeat = e['links'][0]
    assert repeat['role'] == 'repeat'
    r = client.get(f"/api/alternatives/episodes/{repeat['id']}").json()
    assert r['exposure'] == 'seen' and r['gameId'] == g['id'] and r['fen'] == QUEEN and r['parentId'] == e['id']
    # Due tomorrow: not in today's plan until it is ready.
    assert not [i for i in client.get('/api/training-plan').json()['queue'] if i['kind'] == 'alternative']
    with main.database() as con:
        con.execute('UPDATE stuck_episodes SET due_at=? WHERE id=?', ('2000-01-01T00:00:00+00:00', repeat['id']))
    assert [i['id'] for i in client.get('/api/training-plan').json()['queue'] if i['kind'] == 'alternative'] == [repeat['id']]
    r = attempt(client, reason(client, r), 'h5d1').json()
    r = client.post(f"/api/alternatives/episodes/{r['id']}/reflection", json={'considered': 'unsure', 'detail': 'resource'}).json()
    assert r['outcome'] == 'independent'
    progress = client.get('/api/alternatives/progress').json()
    assert progress['newPositions']['all']['total'] == 1 and progress['newPositions']['all']['understood_after'] == 1
    assert progress['seenPositions']['total'] == 1 and progress['seenPositions']['independent'] == 1
    assert progress['byRole']['repeat']['independent'] == 1 and progress['difficulties'][0]['count'] == 1
    assert client.get('/api/training-plan').json()['completed'] == 1


def test_games_with_help_during_play_are_counted_apart_from_autonomous_ones(client):
    mate = '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'
    helped, alone = game(client, mate), game(client, mate)
    e = reason(client, start(client, helped))
    client.post(f"/api/alternatives/episodes/{e['id']}/hint", json={'level': 1})
    for g in (helped, alone):
        assert client.post(f"/api/games/{g['id']}/moves", json={'move': 'g6g7', 'version': 0, 'revision': 0, 'actor': 'human'}).json()['result'] == '1-0'
    local = client.get('/api/alternatives/progress').json()['localMaia']
    assert local == [{'level': 1500, 'assisted': {'games': 1, 'win': 1, 'draw': 0, 'loss': 0}, 'autonomous': {'games': 1, 'win': 1, 'draw': 0, 'loss': 0}}]


def test_analogues_and_counterexamples_are_verified_or_reported_missing(client):
    e = attempt(client, guided(client, COUNTER), 'c4f7').json()
    e = client.post(f"/api/alternatives/episodes/{e['id']}/reflection", json={'considered': 'not_considered', 'detail': 'resource'}).json()
    path = f"/api/alternatives/episodes/{e['id']}/followups"
    report = client.post(path, json={'kinds': ['analog', 'counterexample']}).json()['followups']
    assert report['analog']['id'] is None and 'Nessun caso' in report['analog']['message']
    # Analysed decisions of the player's games are the material: a mirrored copy shares the idea, the queen trap refutes it.
    for identity, fen, color, pv in (('mirror', chess.Board(COUNTER).mirror().fen(), 'b', ['c5f2', 'e1f1']), ('trap', QUEEN, 'w', ['h5d1'])):
        decision = {'ply': 0, 'fen': fen, 'played': pv[0], 'playedSan': '?', 'loss': 300, 'best': {'cp': 0, 'mate': None, 'pv': pv}, 'actual': {'cp': -300, 'mate': None, 'pv': []}}
        with main.database() as con:
            con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (identity, fen, '[]', color, 1500, identity, main.now(), json.dumps({'decisions': [decision]}), 0, 'pgn'))
    report = client.post(path, json={'kinds': ['analog', 'counterexample']}).json()['followups']
    analog = client.get(f"/api/alternatives/episodes/{report['analog']['id']}").json()
    assert analog['role'] == 'analog' and analog['gameId'] == 'mirror' and analog['exposure'] == 'new'
    counter = client.get(f"/api/alternatives/episodes/{report['counterexample']['id']}").json()
    assert counter['role'] == 'counterexample' and counter['gameId'] == 'trap' and 'sembra possibile' in counter['goal']
    plan = [i for i in client.get('/api/training-plan').json()['queue'] if i['kind'] == 'alternative']
    assert {i['id'] for i in plan} <= {analog['id'], counter['id']} and plan


@pytest.fixture
def engine():
    # Outside a TestClient nobody closes Stockfish, which would keep the test run alive.
    yield evaluator
    evaluator.close()


def test_tutor_text_is_kept_only_when_every_reference_checks(monkeypatch, engine):
    board = chess.Board(QUEEN)
    assert alternatives.checked_text('Osserva la donna in h5.', board, set(), {'h5'}) == 'Osserva la donna in h5.'
    assert alternatives.checked_text('Osserva la torre in h5.', board, set(), {'h5'}) is None  # Wrong piece.
    assert alternatives.checked_text('Guarda la casa h6.', board, set(), {'h5'}) is None        # Square not in the evidence.
    assert alternatives.checked_text('Prova Qd1.', board, {'Qd1'}, {'d1'}, {'Qd1'}) is None      # Names the solution.
    evidence = alternatives.analyse(board, {}, alternatives.thresholds())
    hints = alternatives.build_hints(board, {}, evidence)
    answer = {'level1': 'Che cosa succede alla tua donna in h5 dopo gxh5?', 'level2': 'Sposta la donna in d1.',
              'level3': 'Osserva l’alfiere in c4 e la casa f7.', 'detail': 'Il dettaglio è la casa h6, mai citata.'}
    monkeypatch.setattr(alternatives.tutor, 'configuration', lambda: ('key', 'deepseek-flash'))
    monkeypatch.setattr(alternatives.tutor, 'request_json', lambda context, model, system: (json.dumps(answer), {}))
    result, source = alternatives.tutor_hints(board, {}, evidence, hints)
    assert source == 'tutor' and result['1']['text'] == answer['level1']
    assert result['2']['text'] == hints['2']['text'] and result['5']['detail'] == hints['5']['detail']

    def unavailable(*args):
        raise alternatives.tutor.TutorError('down')
    monkeypatch.setattr(alternatives.tutor, 'request_json', unavailable)
    assert alternatives.tutor_hints(board, {}, evidence, hints) == (hints, 'rules')


def test_thresholds_are_configurable(monkeypatch):
    monkeypatch.setenv(alternatives.THRESHOLDS_ENV, '{"validLossCp": 10, "unknown": 3, "marginCp": "x"}')
    t = alternatives.thresholds()
    assert t['validLossCp'] == 10 and t['marginCp'] == 25 and 'unknown' not in t
    best, line = {'cp': 30, 'mate': None, 'depth': 20}, {'cp': 0, 'mate': None, 'depth': 20}
    assert alternatives.judge(best, line, t)[0] == 'concession'
    assert alternatives.judge(best, line, alternatives.DEFAULTS)[0] == 'valid'
    # Centipawns and expected score stay distinct: −6 → −9 is a big loss in a game already lost.
    verdict, metrics = alternatives.judge({'cp': -600, 'mate': None}, {'cp': -900, 'mate': None}, alternatives.DEFAULTS)
    assert verdict == 'insufficient' and metrics['lossCp'] == 300 and metrics['scoreDrop'] < 10
    assert alternatives.judge({'cp': 99997, 'mate': 3}, {'cp': 99990, 'mate': 10}, alternatives.DEFAULTS)[0] == 'valid'
    assert alternatives.judge({'cp': 50, 'mate': None}, {'cp': -99998, 'mate': -2}, alternatives.DEFAULTS)[0] == 'insufficient'
