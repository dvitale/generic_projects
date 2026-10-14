import json

import pytest
from backend import main, mistakes, tutor
from test_coach import client
from test_prevention import seed, session, attempt
from test_tutor import install_transport


def provider_payload():
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
        'reason': 'La donna diventa catturabile dalla torre.',
        'sharedIdea': 'Entrambe muovono la donna vicino al re.',
        'difference': 'Solo una delle case lascia catturare la donna.',
        'alternative': 'La donna protetta evita la cattura nella linea fornita.',
        'continuation': 'La variante mostra la risposta della torre dopo lo scacco.',
        'lesson': 'Dopo la tua mossa, controlla tutte le catture avversarie.',
        'tactical':'La donna è catturata nella variante.', 'positional':'Non basta per stabilire un fattore posizionale dominante.',
        'strategicPlan':'Metti al sicuro la donna prima di scegliere un piano.', 'uncertainty':'Non tutte le risposte sono rappresentate.'})}}]}


@pytest.mark.parametrize('kind', ['prevention', 'puzzle'])
@pytest.mark.parametrize('black', [False, True])
def test_evidence_persists_and_explanation_is_explicit_scoped_cached(client, monkeypatch, kind, black):
    _, p = seed(client, black)
    if kind == 'prevention':
        target = p['id']; s = session(client, p); base = '/api/prevention/' + target
    else:
        target = client.get('/api/exercises').json()[0]['id']; base = '/api/exercises/' + target
        s = client.post(base + '/sessions', json={}).json()
    transport = install_transport(monkeypatch, payload=provider_payload())
    body = {'move': 'g3g1' if black else 'g6g8', 'session_id': s['id'], 'version': s['version']}
    result = client.post(base + '/attempts', json=body)
    assert result.status_code == 200 and not result.json()['success']
    assert client.post(base + '/attempts', json=body).status_code == 409
    path = f'/api/training/{kind}/{target}/mistakes'
    history = client.get(path).json()
    assert len(history) == 1 and not transport.called
    item = history[0]
    assert item['actual']['pv'][0] == body['move']
    assert item['turn'] == ('b' if black else 'w')
    assert item['lossCp'] is None and 'best' not in item # Best is a forced mate, not 1000 pawns.
    main.init_db()
    assert client.get(path).json() == history
    assert client.post(path.replace(target, 'wrong-target') + f"/{item['id']}/explain", json={}).status_code == 404
    url = path + f"/{item['id']}/explain"
    response = client.post(url, json={'fen': 'untrusted client data must not enter the prompt'})
    assert response.status_code == 200, response.text
    assert not response.json()['cached'] and transport.call_count == 1
    comparison = response.json()['comparison']
    assert comparison['actual']['steps'][0]['uci'] == body['move']
    assert not comparison['verification']['acceptedNow']
    assert comparison['best']['perspective'] == comparison['actual']['perspective'] == item['turn']
    sent = json.loads(transport.call_args.kwargs['json']['messages'][1]['content'])
    assert sent['fen'] == p['fen'] and sent['actual']['steps'][1]['captured'].lower() == 'q'
    assert 'gameId' not in sent and 'title' not in sent and 'untrusted' not in json.dumps(sent)
    assert client.post(url, json={}).json()['cached'] and transport.call_count == 1
    body['version'] = result.json()['version']
    assert client.post(base + '/attempts', json=body).status_code == 200
    assert len(client.get(path).json()) == 2
    assert client.get('/api/prevention').json()['stats']['firstSuccesses'] == 0


def test_losses_and_explanation_failure_retry(client, monkeypatch):
    _, p = seed(client); s = session(client, p)
    # Keep legal, engine-generated lines while controlling numeric score boundaries.
    original_compare = main.evaluator.compare
    def compare(*args, **kwargs):
        best, actual, _ = original_compare(*args, **kwargs)
        return {**best, 'cp': 80, 'mate': None}, {**actual, 'cp': -320, 'mate': None}, 400
    monkeypatch.setattr(main.evaluator, 'compare', compare)
    assert not attempt(client, p, s, 'g6g8').json()['success']
    path = f"/api/training/prevention/{p['id']}/mistakes"
    item = client.get(path).json()[0]
    assert item['lossCp'] == 400 and item['actual']['cp'] == -320
    transport = install_transport(monkeypatch, status=429, payload={'secret': 'provider-debug-detail'})
    url = path + f"/{item['id']}/explain"
    response = client.post(url, json={})
    assert response.status_code == 429 and 'provider-debug-detail' not in response.text
    with main.database() as con:
        assert con.execute('SELECT count(*) FROM mistake_explanations').fetchone()[0] == 0
    main.tutor_lock.acquire()
    try:
        assert client.post(url, json={}).status_code == 429
        assert transport.call_count == 1
    finally:
        main.tutor_lock.release()
    transport.return_value = __import__('httpx').Response(200, json=provider_payload())
    assert client.post(url, json={}).status_code == 200


def test_incomplete_mistake_response_is_not_accepted(monkeypatch):
    install_transport(monkeypatch, payload={'choices': [{'finish_reason':'stop', 'message':{'content':'{"reason":"incompleta"}'}}]})
    with pytest.raises(tutor.TutorError):
        tutor.explain_mistake({}, 'deepseek-flash')


@pytest.mark.parametrize('black', [False, True])
def test_rg1_comparison_explains_mate_becoming_check_and_preserves_perspective(black):
    import chess
    board = chess.Board('2k4r/p6q/1pp1p3/8/P2P1N2/2P2Pp1/1P3nK1/R1Q2R2 w - - 1 28')
    if black:
        board = board.mirror()
    move = chess.Move.from_uci('c8b8' if black else 'c1b1')
    best, actual, _ = main.evaluator.compare(board, move, nodes=80000)
    evidence = {'fen':board.fen(), 'move':move.uci(), 'san':board.san(move),
                'turn':'b' if black else 'w', 'best':best, 'actual':actual, 'lossCp':None}
    c = mistakes.verified_context(evidence, 'puzzle')
    assert c['best']['pv'][0] == ('f8g8' if black else 'f1g1')
    assert c['actual']['steps'][1]['checkmate']
    assert c['actual']['steps'][1]['checkFacts']['legalReplies'] == []
    assert {p['piece'].lower() for p in c['actual']['steps'][1]['checkFacts']['movedPieceDefenders']} == {'p','r'}
    assert c['sameReply']['line']['steps'][1]['checkFacts']['legalReplies'] == [('Kf8' if black else 'Kf1')]
    assert c['sameReply']['attemptReply'].endswith('#')
    assert c['sameReply']['alternativeReply'].endswith('+')
    line = c['sameReply']['line']
    assert not line['steps'][1]['checkmate']
    assert line['steps'][2]['uci'] == ('g7f8' if black else 'g2f1')
    assert line['perspective'] == evidence['turn'] and line['cp'] > 0
    assert c['actual']['mate'] == -1 and c['best']['mate'] is None
    assert not c['verification']['acceptedNow']
    explanation=mistakes.verified_mate_explanation(c)
    assert explanation['explanationSource']=='verified-mate-contrast'
    assert explanation['usage']==0
    assert ('f8' if black else 'f1') in explanation['explanation']['difference']
    assert 'vicina alla parità' in explanation['explanation']['alternative']


@pytest.mark.parametrize('kind', ['puzzle','prevention'])
def test_recheck_can_withdraw_original_rejection_without_rewriting_evidence(monkeypatch, kind):
    import chess,copy
    board=chess.Board()
    line=lambda cp,uci:dict(cp=cp,mate=None,pv=[uci],san=[board.san(chess.Move.from_uci(uci))],depth=15,nodes=80000,perspective='w')
    evidence=dict(fen=board.fen(),turn='w',move='d2d4',san='d4',best=line(100,'e2e4'),actual=line(-300,'d2d4'),lossCp=400)
    original=copy.deepcopy(evidence)
    monkeypatch.setattr(main.evaluator,'compare',lambda *a,**kw:(line(20,'e2e4'),line(0,'d2d4'),20))
    c=mistakes.verified_context(evidence,kind)
    assert c['verification']['acceptedNow']
    assert c['verification']['original']['lossCp']==400 and c['lossCp']==20
    assert evidence==original


def test_previous_uncontrasted_provider_format_is_rejected(monkeypatch):
    payload=provider_payload()
    content=json.loads(payload['choices'][0]['message']['content']);content.pop('difference')
    payload['choices'][0]['message']['content']=json.dumps(content)
    install_transport(monkeypatch,payload=payload)
    with pytest.raises(tutor.TutorError):tutor.explain_mistake({},'deepseek-flash')


def test_verified_mate_avoids_remote_generation_and_is_cached(client, monkeypatch):
    from test_coach import seed_exercise
    target=seed_exercise()
    fen='2k4r/p6q/1pp1p3/8/P2P1N2/2P2Pp1/1P3nK1/R1Q2R2 w - - 1 28'
    with main.database() as con:
        con.execute('UPDATE exercises SET initial_fen=? WHERE id=?',(fen,target))
    base='/api/exercises/'+target
    session=client.post(base+'/sessions',json={}).json()
    assert not client.post(base+'/attempts',json={'move':'c1b1','session_id':session['id'],'version':0}).json()['success']
    path='/api/training/puzzle/'+target+'/mistakes'
    item=client.get(path).json()[0]
    def forbidden(*args,**kwargs):raise AssertionError('No remote generation for verified mate contrast')
    monkeypatch.setattr(tutor,'explain_mistake',forbidden)
    first=client.post(path+'/'+str(item['id'])+'/explain',json={})
    assert first.status_code==200,first.text
    assert first.json()['explanationSource']=='verified-mate-contrast'
    assert 'Rg1 libera la casa f1' in first.json()['explanation']['difference']
    assert client.post(path+'/'+str(item['id'])+'/explain',json={}).json()['cached']
