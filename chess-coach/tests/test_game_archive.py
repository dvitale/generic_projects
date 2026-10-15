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
