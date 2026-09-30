import json

import pytest
from backend import main, mistakes, tutor
from test_coach import client
from test_prevention import seed, session, attempt
from test_tutor import install_transport


def provider_payload():
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
        'reason': 'La donna diventa catturabile dalla torre.',
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
