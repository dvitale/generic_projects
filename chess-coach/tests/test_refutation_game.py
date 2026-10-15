from backend import main, learning
from test_coach import client

# After 1.e4 e5 2.Nf3 Nc6: 3.Nxe5? loses the knight to 3...Nxe5.
FEN='r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3'


def start(client,move='f3e5'):
    r=client.post('/api/games',json={'color':'w','fen':FEN,'opponent':'stockfish','moves':[move],'title':'Confutazione di Nxe5'})
    assert r.status_code==200,r.text
    return r.json()


def test_refutation_game_starts_after_the_training_move_and_stockfish_answers(client):
    g=start(client)
    assert g['source']=='stockfish' and g['moves']==['f3e5'] and g['turn']=='b' and g['playerColor']=='w'
    assert not g['canUndo']
    path='/api/games/'+g['id']
    # The opponent's move comes only from the engine endpoint.
    assert client.post(path+'/moves',json={'move':'c6e5','version':1,'revision':0,'actor':'maia'}).status_code==409
    assert client.post(path+'/engine-move',json={'version':0,'revision':0}).status_code==409
    r=client.post(path+'/engine-move',json={'version':1,'revision':0})
    assert r.status_code==200,r.text
    g=r.json()
    assert g['version']==2 and g['turn']=='w' and g['moves'][1] in client.get(path).json()['moves'] and len(g['moveTimes'])==2
    # Not the opponent's turn any more.
    assert client.post(path+'/engine-move',json={'version':2,'revision':0}).status_code==409
    reply=g['legalMoves'][0]
    g=client.post(path+'/moves',json={'move':reply,'version':2,'revision':0,'actor':'human'}).json()
    g=client.post(path+'/engine-move',json={'version':3,'revision':0}).json()
    assert g['canUndo']
    # Undo returns to the player's last decision but never removes the move under test.
    g=client.post(path+'/undo',json={'version':4,'revision':0}).json()
    assert g['moves'][0]=='f3e5' and g['version']==2 and not g['canUndo']


def test_refutation_game_rejects_illegal_or_misplaced_initial_moves(client):
    assert client.post('/api/games',json={'fen':FEN,'opponent':'stockfish','moves':['e1e3']}).status_code==422
    assert client.post('/api/games',json={'fen':FEN,'opponent':'stockfish','moves':['zz']}).status_code==422
    assert client.post('/api/games',json={'fen':FEN,'moves':['f3e5']}).status_code==422
    assert client.post('/api/games',json={'fen':FEN,'opponent':'stockfish','moves':['f3e5','c6e5']}).status_code==422


def test_finished_refutation_game_creates_no_exercises_or_statistics(client):
    g=start(client)
    path='/api/games/'+g['id']
    g=client.post(path+'/resign',json={'version':1,'revision':0}).json()
    assert g['result']=='0-1' and g['analysisJobId'] is None
    assert not any(j['gameId']==g['id'] for j in main.jobs.values())
    # A manual review is still possible but stays out of puzzles, prevention and progress.
    with main.database() as con:
        snapshot=dict(main.find_game(con,g['id']))
    main.jobs['manual']={'gameId':g['id'],'status':'running','progress':0}
    main.analyze_game('manual',snapshot)
    assert main.jobs['manual']['status']=='complete',main.jobs['manual']
    with main.database() as con:
        assert con.execute('SELECT count(*) FROM exercises WHERE game_id=?',(g['id'],)).fetchone()[0]==0
        assert con.execute('SELECT count(*) FROM prevention_positions WHERE game_id=?',(g['id'],)).fetchone()[0]==0
        assert all(row['id']!=g['id'] for row,_ in learning.records(con))
