import json

import chess
import pytest
from backend import final_review, main, tutor
from test_tutor import client, analyzed_game, install_transport


def commentary(ply=4):
    return {'summary':'Una partita con occasioni da rivedere.', 'course':'La valutazione cambia nella fase analizzata.',
            'strengths':[], 'focus':[{'title':'Confronta le difese', 'explanation':'Rivedi la risposta avversaria verificata.',
            'plies':[ply], 'kind':'tactical', 'practice':'Per 5 minuti confronta due mosse candidate nella posizione.'}],
            'uncertainty':'Una partita e una ricerca limitata non descrivono una carenza stabile.'}


def transport_for(monkeypatch, result=None):
    return install_transport(monkeypatch,payload={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result or commentary())}}]})


def test_final_review_is_on_demand_cached_and_contains_both_sides(client,monkeypatch):
    game=analyzed_game(client);transport=transport_for(monkeypatch)
    path=f"/api/games/{game['id']}/final-review"
    assert client.get(path).json() is None
    assert not transport.called
    response=client.post(path,json={'version':6,'revision':0})
    assert response.status_code==200,response.text
    assert response.json()['completeCoverage']
    assert response.json()['result']=='*'
    assert len(response.json()['references'])==6
    context=json.loads(transport.call_args.kwargs['json']['messages'][1]['content'])
    assert [p['byPlayer'] for p in context['trajectory']]==[True,False]*3
    assert len(context['trajectory'])==6 and len(context['evidence'])<=6
    assert 'PRIVATE' not in json.dumps(context) and 'referenceElo' not in context
    assert client.post(path,json={'version':6,'revision':0}).json()['cached']
    assert client.get(path).json()['commentary']==commentary()
    assert transport.call_count==1
    with main.database() as con:
        con.execute("UPDATE games SET termination='resign',revision=revision+1 WHERE id=?",(game['id'],))
    assert client.get(path).json() is None
    assert client.post(path,json={'version':6,'revision':0}).status_code==409
    result=client.post(path,json={'version':6,'revision':1})
    assert result.json()['result']=='0-1'
    assert transport.call_count==2


@pytest.mark.parametrize('ply',[1,500])
def test_bad_or_opponent_references_not_saved(client,monkeypatch,ply):
    game=analyzed_game(client);transport_for(monkeypatch,commentary(ply))
    path=f"/api/games/{game['id']}/final-review"
    assert client.post(path,json={'version':6,'revision':0}).status_code==502
    assert client.get(path).json() is None


def test_analysis_and_concurrency_guards(client,monkeypatch):
    game=client.post('/api/games',json={}).json();transport=transport_for(monkeypatch)
    path=f"/api/games/{game['id']}/final-review"
    assert client.post(path,json={'version':0,'revision':0}).status_code==409
    assert not transport.called
    game=analyzed_game(client);path=f"/api/games/{game['id']}/final-review"
    def change(context,model):
        with main.database() as con:con.execute('UPDATE games SET revision=revision+1 WHERE id=?',(game['id'],))
        return {'commentary':commentary(),'provider':'test','model':model}
    monkeypatch.setattr(final_review,'generate',change)
    assert client.post(path,json={'version':6,'revision':0}).status_code==409
    assert client.get(path).json() is None
    main.tutor_lock.acquire()
    try:assert client.post(path,json={'version':6,'revision':1}).status_code==429
    finally:main.tutor_lock.release()


def test_black_perspective_mate_and_partial_coverage(client):
    game=analyzed_game(client)
    with main.database() as con:
        row=dict(main.find_game(con,game['id']));row['player_color']='b'
        analysis=json.loads(row['analysis'])
        analysis['moves'][0]['actual']={'cp':99,'mate':None,'perspective':'w','san':[]}
        analysis['moves'][1]['actual']={'cp':100000,'mate':3,'perspective':'b','san':[]}
        row['analysis']=json.dumps(analysis)
        context=final_review.build_context(con,row,'*')
        assert context['trajectory'][0]['after']=={'cp':-99,'mate':None}
        assert context['trajectory'][1]['after']=={'cp':None,'mate':3}
        assert context['trajectory'][1]['byPlayer']
        analysis.pop('moves');row['analysis']=json.dumps(analysis)
        assert not final_review.build_context(con,row,'*')['completeCoverage']


def test_drill_preparation_is_not_credited_to_player(client):
    game=analyzed_game(client)
    with main.database() as con:
        con.execute('INSERT INTO drill_sessions VALUES(?,?,?,?,?,?,?)',(game['id'],'test','Test','Test','Test',4,2))
        row=dict(main.find_game(con,game['id']))
        context=final_review.build_context(con,row,'*')
    assert context['scope']=='drill' and context['startPly']==4
    assert [d['ply'] for d in context['trajectory']]==[4,5]
    assert context['quality']['decisions']==1
    assert context['completeCoverage']
