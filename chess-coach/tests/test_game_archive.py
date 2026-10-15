from test_coach import client
from test_resign import move


def test_archive_lists_result_colour_level_position_and_quality(client):
    g=client.post('/api/games',json={'color':'b','elo':1100}).json()
    g=move(client,g,'e2e4','maia')
    r=client.post(f"/api/games/{g['id']}/resign",json={'version':g['version'],'revision':g['revision']})
    assert r.status_code==200,r.text
    open_game=client.post('/api/games',json={'color':'w'}).json()
    rows={row['id']:row for row in client.get('/api/games').json()}
    ended=rows[g['id']]
    assert ended['result']=='1-0' and ended['playerColor']=='b' and ended['elo']==1100
    assert ended['fen']=='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
    assert ended['quality'] is None
    assert rows[open_game['id']]['result'] is None


def test_game_view_exposes_recorded_move_times(client):
    g=client.post('/api/games',json={'color':'w'}).json()
    r=client.post(f"/api/games/{g['id']}/moves",json={'move':'e2e4','actor':'human','version':0,'revision':0,'elapsed_seconds':4.25})
    assert r.status_code==200,r.text
    assert r.json()['moveTimes']==[4.25]


def test_archive_exports_several_games_in_one_pgn(client):
    first=client.post('/api/games',json={'color':'w'}).json()
    move(client,first,'e2e4','human')
    second=client.post('/api/games',json={'color':'b'}).json()
    r=client.get(f"/api/games/pgn?ids={second['id']},{first['id']}&include_times=false")
    assert r.status_code==200 and 'sparringmate-2-partite.pgn' in r.headers['content-disposition']
    assert r.text.count('[Event ')==2 and r.text.index(second['id'])<r.text.index(first['id'])
    assert '1. e4' in r.text
    assert client.get('/api/games/pgn?ids=missing').status_code==404


def test_evaluation_bar_scores_any_position_of_the_game(client):
    g=client.post('/api/games',json={'color':'w'}).json()
    for uci in ['f2f3','e7e5','g2g4','d8h4']:
        g=move(client,g,uci,'human' if g['turn']=='w' else 'maia')
    start=client.get(f"/api/games/{g['id']}/evaluation?ply=0").json()
    assert start['ply']==0 and start['evaluation']['perspective']=='w' and start['evaluation']['mate'] is None
    mate=client.get(f"/api/games/{g['id']}/evaluation?ply=4").json()['evaluation']
    assert mate['mate']==0 and mate['perspective']=='w'
    assert client.get(f"/api/games/{g['id']}/evaluation?ply=5").status_code==404


def test_new_game_can_start_from_a_reviewed_position_with_its_own_title(client):
    fen='rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2'
    g=client.post('/api/games',json={'color':'b','elo':1700,'fen':fen,'title':'Da Partita X · 2.'}).json()
    assert g['initialFen']==fen and g['playerColor']=='b' and g['turn']=='w' and g['title']=='Da Partita X · 2.'
    mated='rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3'
    assert client.post('/api/games',json={'fen':mated}).status_code==422
