import json
from backend import learning
from test_coach import client
from test_resign import move


def test_suggestion_only_on_player_turn_and_marks_the_ply_as_assisted(client):
    g=client.post('/api/games',json={'color':'w'}).json()
    path=f"/api/games/{g['id']}/suggestion"
    assert client.post(path,json={'version':1,'revision':0}).status_code==409
    r=client.post(path,json={'version':0,'revision':0})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['ply']==0 and data['assistedPlies']==[0]
    assert data['stockfish']['pv'][0] in client.get('/api/games/'+g['id']).json()['legalMoves']
    g=move(client,g,'e2e4','human')
    assert g['assistedPlies']==[0]
    assert client.post(path,json={'version':1,'revision':0}).status_code==409
    g=move(client,g,'e7e5','maia')
    assert client.post(path,json={'version':2,'revision':0}).json()['assistedPlies']==[0,2]
    undone=client.post(f"/api/games/{g['id']}/undo",json={'version':2,'revision':0}).json()
    assert undone['assistedPlies']==[]


def test_assisted_plies_are_excluded_from_decision_quality():
    analysis={'decisions':[{'ply':0,'fen':'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1','loss':300,'best':{'cp':30,'mate':None},'actual':{'cp':-270,'mate':None}},
                           {'ply':2,'fen':'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2','loss':0,'best':{'cp':30,'mate':None},'actual':{'cp':30,'mate':None}}]}
    row={'analysis':json.dumps(analysis),'analysis_version':4,'moves':json.dumps(['e2e4','e7e5','g1f3','b8c6']),'player_color':'w','assisted_plies':'[0]'}
    class Row(dict):
        def keys(self):return super().keys()
    items=learning.decisions(Row(row))
    assert [d['ply'] for d in items]==[2]
    assert learning.quality(items)['errors']==0
