import pytest
from backend import main
from test_coach import client

def move(client,game,uci,actor):
    r=client.post(f"/api/games/{game['id']}/moves",json={'move':uci,'actor':actor,'version':game['version'],'revision':game['revision']})
    assert r.status_code==200,r.text
    return r.json()

@pytest.mark.parametrize('color,result,resigner',[('w','0-1','White'),('b','1-0','Black')])
def test_resign_persists_result_exports_pgn_and_starts_analysis(client,color,result,resigner):
    g=client.post('/api/games',json={'color':color}).json()
    g=move(client,g,'e2e4','human' if color=='w' else 'maia')
    path='/api/games/'+g['id']
    r=client.post(path+'/resign',json={'version':g['version'],'revision':g['revision']})
    assert r.status_code==200,r.text
    ended=r.json()
    assert ended['result']==result and ended['termination']=='resign'
    assert not ended['canUndo'] and ended['moves']==g['moves']
    assert client.get(path).json()['result']==result
    pgn=client.get(path+'/pgn').text
    assert f'[Result "{result}"]' in pgn and f'[Resignation "{resigner}"]' in pgn
    assert len([j for j in main.jobs.values() if j['gameId']==g['id'] and j['automatic']])==1
    assert client.post(path+'/moves',json={'move':'e7e5','version':1,'revision':ended['revision'],'actor':'maia' if color=='w' else 'human'}).status_code==409
    assert client.post(path+'/undo',json={'version':1,'revision':ended['revision']}).status_code==409
    assert client.post(path+'/resign',json={'version':1,'revision':ended['revision']}).status_code==409

def test_resign_before_any_move_saves_defeat_without_empty_analysis(client):
    g=client.post('/api/games',json={'color':'b'}).json()
    r=client.post(f"/api/games/{g['id']}/resign",json={'version':0,'revision':0}).json()
    assert r['result']=='1-0' and r['analysisJobId'] is None
    assert not any(j['gameId']==g['id'] for j in main.jobs.values())

def test_resign_tolerates_only_one_late_bot_reply(client):
    g=client.post('/api/games',json={}).json()
    g=move(client,g,'e2e4','human')
    g=move(client,g,'e7e5','maia')
    path='/api/games/'+g['id']
    assert client.post(path+'/resign',json={'version':1,'revision':0}).status_code==200
    other=client.post('/api/games',json={}).json()
    other=move(client,other,'e2e4','human')
    assert client.post(f"/api/games/{other['id']}/resign",json={'version':0,'revision':0}).status_code==409
    assert client.post(f"/api/games/{other['id']}/resign",json={'version':1,'revision':2}).status_code==409

def test_cannot_resign_imported_or_board_finished_games(client):
    imported=client.post('/api/import',json={'pgn':'1. e4 e5 *','color':'w'}).json()
    assert client.post(f"/api/games/{imported['id']}/resign",json={'version':2,'revision':0}).status_code==409
    # A game cannot start from a finished position; it can end on the board and then not be resigned.
    assert client.post('/api/games',json={'fen':'7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'}).status_code==422
    finished=client.post('/api/games',json={'fen':'7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}).json()
    finished=move(client,finished,'g6g7','human')
    assert finished['result']=='1-0'
    assert client.post(f"/api/games/{finished['id']}/resign",json={'version':1,'revision':0}).status_code==409


def answer(client,g,accept):
    r=client.post(f"/api/games/{g['id']}/resign-offer",json={'version':g['version'],'revision':g['revision'],'accept':accept})
    assert r.status_code==200,r.text
    return r.json()


def lost_game(client,monkeypatch):
    """Queen and rook against a lone king after quiet king moves: the bot's third lost turn is due."""
    g=client.post('/api/games',json={'fen':'7k/8/8/8/8/8/8/2QRK3 w - - 0 1'}).json()
    plies=[('e1e2','h8g8'),('e2e3','g8h8'),('e3e4','h8g8')]
    # Past the default minimum of 20 plies only: this short game never offers to resign.
    for human,bot in plies[:2]:
        g=move(client,g,human,'human');g=move(client,g,bot,'maia')
    assert g['termination'] is None and not g['resignOffer']
    monkeypatch.setattr(main,'RESIGN_MIN_PLY',0)
    return move(client,g,plies[2][0],'human')


def test_bot_offers_to_resign_and_the_accepted_offer_ends_the_game(client,monkeypatch):
    g=lost_game(client,monkeypatch)
    offered=client.post(f"/api/games/{g['id']}/moves",json={'move':'h8g8','actor':'maia','version':g['version'],'revision':g['revision']}).json()
    # The third lost turn: the bot asks instead of playing, and nothing ends until the player answers.
    assert offered['resignOffer'] and offered['termination'] is None and offered['result'] is None and len(offered['moves'])==5
    assert client.get(f"/api/games/{g['id']}").json()['resignOffer']
    assert not [j for j in main.jobs.values() if j['gameId']==g['id']]
    ended=answer(client,offered,True)
    assert ended['termination']=='engine_resign' and ended['result']=='1-0' and not ended['resignOffer'] and len(ended['moves'])==5
    pgn=client.get(f"/api/games/{g['id']}/pgn").text
    assert '[Result "1-0"]' in pgn and '[Resignation "Black"]' in pgn
    assert len([j for j in main.jobs.values() if j['gameId']==g['id'] and j['automatic']])==1
    assert client.post(f"/api/games/{g['id']}/moves",json={'move':'h8g8','actor':'maia','version':5,'revision':ended['revision']}).status_code==409
    assert client.post(f"/api/games/{g['id']}/resign-offer",json={'version':5,'revision':ended['revision'],'accept':True}).status_code==409


def test_declined_offer_lets_the_bot_play_and_is_not_repeated_at_once(client,monkeypatch):
    g=lost_game(client,monkeypatch)
    offered=move(client,g,'h8g8','maia')
    assert offered['resignOffer']
    g=answer(client,offered,False)
    assert not g['resignOffer'] and g['termination'] is None and g['revision']==offered['revision']
    g=move(client,g,'h8g8','maia')
    assert len(g['moves'])==6 and not g['resignOffer']
    g=move(client,g,'e4d4','human');g=move(client,g,'g8h8','maia')
    assert len(g['moves'])==8 and not g['resignOffer']
    # Past the quiet window the still-lost bot asks again.
    monkeypatch.setattr(main,'RESIGN_RETRY_PLIES',4)
    g=move(client,g,'d4d5','human')
    assert move(client,g,'h8g8','maia')['resignOffer']


def test_undo_withdraws_a_pending_offer(client,monkeypatch):
    g=lost_game(client,monkeypatch)
    offered=move(client,g,'h8g8','maia')
    assert offered['resignOffer']
    r=client.post(f"/api/games/{g['id']}/undo",json={'version':offered['version'],'revision':offered['revision']})
    assert r.status_code==200,r.text
    back=r.json()
    assert len(back['moves'])==4 and not back['resignOffer']
    assert client.post(f"/api/games/{g['id']}/resign-offer",json={'version':back['version'],'revision':back['revision'],'accept':True}).status_code==409


def test_bot_keeps_playing_a_balanced_position(client,monkeypatch):
    monkeypatch.setattr(main,'RESIGN_MIN_PLY',0)
    g=client.post('/api/games',json={}).json()
    for human,bot in [('e2e4','e7e5'),('g1f3','b8c6'),('f1c4','g8f6')]:
        g=move(client,g,human,'human');g=move(client,g,bot,'maia')
    assert g['termination'] is None and len(g['moves'])==6
