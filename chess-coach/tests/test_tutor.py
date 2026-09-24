import json
from unittest.mock import Mock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from backend import main, tutor
from test_coach import wait_analysis


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'coach.sqlite3')
    monkeypatch.setattr(tutor, 'CONFIG_PATH', tmp_path / 'absent.json')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with TestClient(main.app) as c:
        yield c


def sample_coaching(ply=4, exercise_id=None):
    return {'summary':'Una decisione da rivedere.', 'observations':[{'ply':ply,'explanation':'Confronta la tua mossa con la variante Stockfish.',
            'hypothesis':'Potresti aver trascurato una risposta: è da verificare.','question':'Quale risposta avevi previsto?'}],
            'plan':[{'title':'Ripassa la decisione','minutes':5,'description':'Confronta due mosse candidate.','exerciseId':exercise_id,'drillId':None}]}


def install_transport(monkeypatch, status=200, payload=None):
    if payload is None:
        payload={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(sample_coaching())}}], 'usage':{'total_tokens':50}}
    transport=Mock(return_value=httpx.Response(status, json=payload))
    external_client = MagicMock()
    external_client.__enter__.return_value.post = transport
    monkeypatch.setattr(tutor, 'HTTP_CLIENT', Mock(return_value=external_client))
    monkeypatch.setenv('DEEPSEEK_API_KEY','unit-test-placeholder')
    return transport


def analyzed_game(client):
    game=client.post('/api/import',json={'pgn':'[White "PRIVATE NAME"]\n[Black "OTHER PRIVATE"]\n\n1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *'}).json()
    wait_analysis(client,game['id'])
    return game


def test_tutor_requires_configuration_and_analysis(client, monkeypatch):
    assert client.get('/api/tutor/status').json()['configured'] is False
    game=client.post('/api/games',json={}).json()
    assert client.post(f"/api/games/{game['id']}/tutor",json={'version':0}).status_code==503
    transport=install_transport(monkeypatch)
    assert client.post(f"/api/games/{game['id']}/tutor",json={'version':0}).status_code==409
    assert not transport.called


def test_tutor_cache_privacy_and_stale_analysis(client,monkeypatch):
    game=analyzed_game(client)
    transport=install_transport(monkeypatch)
    path=f"/api/games/{game['id']}/tutor"
    result=client.post(path,json={'version':6,'reflection':'Volevo guadagnare un pedone.'})
    assert result.status_code==200,result.text
    assert not result.json()['cached']
    assert 'unit-test-placeholder' not in result.text
    sent=transport.call_args.kwargs['json']
    assert 'PRIVATE NAME' not in json.dumps(sent) and 'OTHER PRIVATE' not in json.dumps(sent)
    assert 'unit-test-placeholder' not in json.dumps(sent)
    assert len(json.loads(sent['messages'][1]['content'])['decisions'])<=3
    assert client.post(path,json={'version':6,'reflection':'Volevo guadagnare un pedone.'}).json()['cached']
    assert transport.call_count==1
    assert client.get(path).json()['coaching']['summary']==sample_coaching()['summary']
    assert client.post(path,json={'version':5}).status_code==409
    with main.database() as con:
        con.execute('UPDATE games SET analysis=NULL WHERE id=?',(game['id'],))
    assert client.get(path).json() is None


@pytest.mark.parametrize('status,expected',[(401,503),(402,503),(429,429),(500,502)])
def test_provider_errors_are_sanitized(client,monkeypatch,status,expected):
    game=analyzed_game(client)
    install_transport(monkeypatch,status,{'error':{'message':'unit-test-placeholder confidential provider details'}})
    response=client.post(f"/api/games/{game['id']}/tutor",json={'version':6})
    assert response.status_code==expected
    assert 'unit-test-placeholder' not in response.text and 'confidential' not in response.text


@pytest.mark.parametrize('coaching',[sample_coaching(ply=500),sample_coaching(exercise_id='invented-id')])
def test_unsupported_evidence_not_saved(client,monkeypatch,coaching):
    game=analyzed_game(client)
    install_transport(monkeypatch,payload={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(coaching)}}]})
    path=f"/api/games/{game['id']}/tutor"
    assert client.post(path,json={'version':6}).status_code==502
    assert client.get(path).json() is None


def test_timeout_incomplete_and_concurrent_requests(client,monkeypatch):
    game=analyzed_game(client)
    transport=install_transport(monkeypatch)
    path=f"/api/games/{game['id']}/tutor"
    transport.side_effect=httpx.ReadTimeout('Sensitive diagnostic omitted')
    response=client.post(path,json={'version':6})
    assert response.status_code==504 and 'Sensitive' not in response.text
    transport.side_effect=None
    transport.return_value=httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})
    assert client.post(path,json={'version':6}).status_code==502
    main.tutor_lock.acquire()
    try:
        assert client.post(path,json={'version':6}).status_code==429
    finally:
        main.tutor_lock.release()
