import json
from test_coach import client
from backend import main

def pgn(id='a',white='Tester',black='Maia 600'):
    return f'[ID "{id}"]\n[Site "https://maiachess.com/"]\n[White "{white}"]\n[Black "{black}"]\n[Result "*"]\n\n1. e4 {{ [%emt 0:00:03] }} e5 *'


def test_maia_batch_color_elo_distinct_ids_and_duplicate(client,monkeypatch):
    jobs=[]
    # Disable real analysis here; a separate browser test exercises the real queue.
    text=pgn()+'\n\n'+pgn('b','Maia 900','Tester')
    response=client.post('/api/import/batch',json={'pgn':text,'analyze':False})
    assert response.status_code==200,response.text
    report=response.json();assert report['imported']==2 and report['failed']==0
    a,b=[client.get('/api/games/'+r['id']).json() for r in report['results']]
    assert (a['playerColor'],a['elo'])==('w',600)
    assert (b['playerColor'],b['elo'])==('b',900)
    assert a['timedMoves']==1 and '[ID "a"]' in a['pgn']
    assert client.post('/api/import/batch',json={'pgn':text,'analyze':False}).json()['duplicates']==2
    assert client.post('/api/import/batch',json={'pgn':pgn('c'),'analyze':False}).json()['imported']==1
    conflict=client.post('/api/import/batch',json={'pgn':pgn().replace('e5 *','c5 *'),'analyze':False}).json()
    assert conflict['failed']==1 and len(client.get('/api/games').json())==3
    assert client.get('/api/training-guide').status_code==200


def test_import_partial_errors_and_limits(client):
    ambiguous='[White "A"]\n[Black "B"]\n\n1. d4 d5 *'
    r=client.post('/api/import/batch',json={'pgn':pgn()+'\n\n'+ambiguous,'analyze':False}).json()
    assert r['imported']==1 and r['failed']==1
    r=client.post('/api/import/batch',json={'pgn':ambiguous,'username':'B','analyze':False}).json()
    assert r['results'][0]['color']=='b'
    bad=client.post('/api/import/batch',json={'pgn':'[Event "Bad"]\n\n1. e5 *','color':'w','analyze':False}).json()
    assert bad['failed']==1
    response=client.post('/api/import/batch',json={'pgn':'\n\n'.join(pgn(str(i)) for i in range(21)),'analyze':False})
    assert response.status_code==422
    assert len(client.get('/api/games').json())==2
