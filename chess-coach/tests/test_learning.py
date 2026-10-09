import json
import chess
from test_coach import client
from backend import main, learning


def evaluation(cp, color='w', mate=None):
    return {'cp':cp,'mate':mate,'perspective':color,'pv':['e2e4'],'san':['e4'],'depth':18,'nodes':10000}


def seed(client, color='w', source='pgn'):
    game=client.post('/api/import',json={'pgn':'1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *','color':color}).json()
    board=chess.Board();items=[]
    for ply,move in enumerate(game['moves']):
        if board.turn==(color=='w'):
            items.append({'ply':ply,'fen':board.fen(),'played':move,'playedSan':board.san(chess.Move.from_uci(move)),
                          'best':evaluation(350,color),'actual':evaluation(300,color),'loss':50})
        board.push_uci(move)
    with main.database() as con:
        con.execute('UPDATE games SET source=?,analysis=?,analysis_version=? WHERE id=?',
                    (source,json.dumps({'decisions':items}),game['version'],game['id']))
    return game, items


def test_quality_thresholds_and_mates():
    items=[{'best':evaluation(200),'actual':evaluation(200-loss),'loss':loss} for loss in (0,79,80,179,180)]
    result=learning.quality(items)
    assert result=={'decisions':5,'sound':2,'inaccuracies':2,'errors':1,'advantages':5,'maintained':1}
    assert learning.quality([{'best':evaluation(0,mate=3),'actual':evaluation(0,mate=-2),'loss':20000}])['maintained']==0
    for cp,expected in [(-300,'much_worse'),(-101,'worse'),(-100,'equal'),(100,'equal'),(101,'better'),(300,'much_better')]:
        assert learning.category(evaluation(cp))==expected


def test_black_perspective_drill_scope_and_stale_analysis(client):
    game,items=seed(client,'b','drill')
    with main.database() as con:
        con.execute('INSERT INTO drill_sessions VALUES(?,?,?,?,?,?,?)',(game['id'],'test','Test','Test','Test',3,5))
    data=client.get(f"/api/games/{game['id']}/decision-quality").json()
    assert data['ready'] and data['decisions']==2 and data['maintained']==2
    p=client.get('/api/learning-progress').json()
    assert p['groups'][0]['recent']['games']==0 and p['groups'][1]['recent']['decisions']==2
    with main.database() as con:
        con.execute('UPDATE games SET analysis_version=0 WHERE id=?',(game['id'],))
    assert not client.get(f"/api/games/{game['id']}/decision-quality").json()['ready']
    assert client.get('/api/learning-progress').json()['groups'][1]['recent']['decisions']==0


def test_judgment_hidden_until_answer_immutable_persistent_and_deduplicated(client):
    game,_=seed(client)
    p=client.post('/api/position-judgments/next').json()
    assert p and set(p)=={'id','fen','ply','color'}
    assert client.post('/api/position-judgments/next').json()==p
    answer={'assessment':'much_worse','confidence':'confident','fearedLost':True,'familiar':False,'threat':'Temo le torri'}
    response=client.post('/api/position-judgments/'+p['id'],json=answer)
    assert response.status_code==200
    result=response.json();assert result['falseAlarm'] and result['expected']=='much_better'
    assert result['gameId']==game['id'] and result['evidence']['cp']==350
    assert client.post('/api/position-judgments/'+p['id'],json=answer).json()==result
    assert client.post('/api/position-judgments/'+p['id'],json={**answer,'assessment':'equal'}).status_code==409
    main.init_db()
    stat=client.get('/api/learning-progress').json()['judgments']
    assert stat=={'total':1,'fresh':1,'matched':0,'fearedLost':1,'falseAlarms':1}
    p2=client.post('/api/position-judgments/next').json()
    assert p2['fen']!=p['fen']
    client.post('/api/position-judgments/'+p2['id'],json={**answer,'familiar':True})
    assert client.get('/api/learning-progress').json()['judgments']=={**stat,'total':2}


def test_empty_active_game_and_exhaustion(client):
    assert client.post('/api/position-judgments/next').json() is None
    game,_=seed(client,source='maia')
    assert client.post('/api/position-judgments/next').json() is None
    with main.database() as con:con.execute("UPDATE games SET source='pgn' WHERE id=?",(game['id'],))
    for _ in range(3):
        p=client.post('/api/position-judgments/next').json()
        assert p
        assert client.post('/api/position-judgments/'+p['id'],json={'assessment':'equal','confidence':'uncertain'}).status_code==200
    assert client.post('/api/position-judgments/next').json() is None
    assert client.post('/api/position-judgments/missing',json={'assessment':'equal','confidence':'uncertain'}).status_code==404


def test_no_error_only_selection_and_forced_moves(client):
    game,items=seed(client)
    items[0]['forced']=True
    items[1]['best']=evaluation(-450)
    items[2]['best']=evaluation(0)
    with main.database() as con:con.execute('UPDATE games SET analysis=? WHERE id=?',(json.dumps({'decisions':items}),game['id']))
    assert client.get(f"/api/games/{game['id']}/decision-quality").json()['decisions']==2
    outcomes=[]
    for _ in range(2):
        p=client.post('/api/position-judgments/next').json()
        outcomes.append(client.post('/api/position-judgments/'+p['id'],json={'assessment':'equal','confidence':'uncertain'}).json()['expected'])
    assert set(outcomes)=={'much_worse','equal'}


def test_progress_uses_denominators_and_two_windows(client):
    game,items=seed(client)
    with main.database() as con:
        row=dict(main.find_game(con,game['id']))
        for i in range(11):
            con.execute('INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (str(i),row['initial_fen'],row['moves'],'w',600,'Test',f'2030-01-{i+1:02d}',row['analysis'],6,'pgn'))
    p=client.get('/api/learning-progress').json()['groups'][0]
    assert p['recent']['games']==10 and p['recent']['decisions']==30
    assert p['previous']['games']==2 and p['previous']['decisions']==6
