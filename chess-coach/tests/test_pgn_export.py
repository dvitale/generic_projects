import io
import json
import chess
import chess.pgn
from backend import main
from test_coach import client, wait_analysis


def read(text):
    game=chess.pgn.read_game(io.StringIO(text))
    assert game and not game.errors
    return game


def play(client,g,move,seconds=None):
    r=client.post(f"/api/games/{g['id']}/moves",json={
        'move':move,'version':g['version'],'revision':g['revision'],
        'actor':'human' if g['turn']==g['playerColor'] else 'maia','elapsed_seconds':seconds})
    assert r.status_code==200,r.text
    return r.json()


def test_export_times_survive_fetch_and_undo_preserves_snapshot(client):
    g=client.post('/api/games',json={'fen':'7k/8/5KQ1/8/8/8/8/8 w - - 0 1','elo':600}).json()
    g=play(client,g,'g6g8',12.345)
    wait_analysis(client,g['id'])
    g=client.get('/api/games/'+g['id']).json()
    assert g['timedMoves']==1
    response=client.get(f"/api/games/{g['id']}/pgn")
    assert response.status_code==200 and 'attachment' in response.headers['content-disposition']
    pgn=read(response.text)
    assert pgn.headers['Black']=='Maia 600' and pgn.headers['TimeControl']=='-'
    assert pgn.headers['SetUp']=='1' and pgn.headers['FEN']==g['initialFen']
    assert list(pgn.mainline())[0].emt()==12.345
    plain=read(client.get(f"/api/games/{g['id']}/pgn?include_times=false").text)
    assert list(plain.mainline())[0].emt() is None
    assert list(plain.mainline_moves())==list(pgn.mainline_moves())
    g=client.post(f"/api/games/{g['id']}/undo",json={'version':g['version'],'revision':g['revision']}).json()
    assert g['timedMoves']==0 and '[%emt' not in g['pgn']
    snapshots=[r for r in client.get('/api/games').json() if r['source']=='snapshot']
    assert len(snapshots)==1
    assert list(read(client.get(f"/api/games/{snapshots[0]['id']}/pgn").text).mainline())[0].emt()==12.345
    g=play(client,g,'g6g7',3.5)
    assert g['result']=='1-0'
    assert list(read(g['pgn']).mainline())[0].emt()==3.5


def test_import_preserves_result_names_clock_and_elapsed(client):
    pgn='''[White "Giocatore"]
[Black "Maia 600"]
[Result "0-1"]
[TimeControl "900+10"]

1. e4 {[%clk 0:15:07] [%emt 0:00:03]} c6 {[%clk 0:15:08]} 2. d4 0-1'''
    g=client.post('/api/import',json={'pgn':pgn}).json()
    assert g['result']=='0-1' and g['timedMoves']==2
    exported=read(client.get(f"/api/games/{g['id']}/pgn").text)
    assert exported.headers['White']=='Giocatore' and exported.headers['Black']=='Maia 600'
    assert exported.headers['Result']=='0-1' and exported.headers['TimeControl']=='900+10'
    nodes=list(exported.mainline())
    assert nodes[0].emt()==3 and nodes[0].clock()==907 and nodes[1].clock()==908
    assert nodes[2].emt() is None and nodes[2].clock() is None
    plain=client.get(f"/api/games/{g['id']}/pgn?include_times=false").text
    assert '[%clk' not in plain and '[%emt' not in plain
    assert read(plain).headers['TimeControl']=='900+10'
    # A second import with elapsed times only must retain the clocks already stored.
    again=client.post('/api/import',json={'pgn':pgn.replace('[%clk 0:15:07] ', '')}).json()
    assert list(read(again['pgn']).mainline())[0].clock()==907


def test_legacy_missing_times_remain_unknown_and_invalid_values_rejected(client):
    g=client.post('/api/games',json={}).json()
    g=play(client,g,'e2e4')
    g=play(client,g,'e7e5',2)
    nodes=list(read(g['pgn']).mainline())
    assert nodes[0].emt() is None and nodes[1].emt()==2
    for seconds in (-1,604801):
        r=client.post(f"/api/games/{g['id']}/moves",json={'move':'g1f3','version':2,'revision':0,'actor':'human','elapsed_seconds':seconds})
        assert r.status_code==422
    assert client.get('/api/games/'+g['id']).json()['version']==2
    assert client.get('/api/games/missing/pgn').status_code==404
