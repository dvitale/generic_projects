import json

import chess
from backend import insights, main, tutor
from test_coach import client, wait_analysis
from test_tutor import install_transport, sample_coaching


def value(board, moves, cp=0, mate=None):
    cursor=board.copy();san=[]
    for move in moves:
        san.append(cursor.san(chess.Move.from_uci(move)));cursor.push_uci(move)
    return {'pv':moves,'san':san,'cp':cp,'mate':mate,'perspective':'w' if board.turn else 'b','nodes':100,'depth':8}


def test_no_material_loss_can_have_positional_evidence_but_not_proven_cause():
    b=chess.Board()
    best=value(b,['e2e4','e7e5'],60);actual=value(b,['e2e3','e7e5'],-80)
    result=insights.compare(b.fen(),'e2e3',best,actual)
    assert result['kind']=='positional'
    assert not result['tacticalFacts'] and result['positionalFacts'] and result['plans']
    assert result['material']==dict.fromkeys(['before','immediate','playedLine','bestLine'],0)
    assert 'non provano da soli la causa' in result['note']
    assert result['features'][0]['before']['center']!=result['features'][0]['played']['center']


def test_silence_in_a_short_line_is_not_automatically_positional():
    b=chess.Board('7k/8/8/8/8/8/8/K7 w - - 0 1')
    result=insights.compare(b.fen(),'a1b1',value(b,['a1a2'],50),value(b,['a1b1'],-300))
    assert result['kind']=='unclear' and not result['positionalFacts']


def test_recapture_restores_material_and_does_not_create_spurious_tactical_loss():
    b=chess.Board();b.push_san('e4');b.push_san('d5')
    result=insights.compare(b.fen(),'e4d5',value(b,['g1f3','g8f6'],50),value(b,['e4d5','d8d5'],-150))
    assert result['material']['immediate']==1
    assert result['material']['playedLine']==result['material']['bestLine']==0
    assert not result['tacticalFacts']


def test_tactics_mates_and_material_perspective_for_both_colors():
    for black in (False,True):
        b=chess.Board('r6k/8/5KQ1/8/8/8/8/8 w - - 0 1')
        if black:b=b.mirror()
        played='g3g1' if black else 'g6g8'
        best=value(b,['g3g2' if black else 'g6g7'],99999,1)
        actual=value(b,[played,'h1g1' if black else 'h8g8'],-500)
        result=insights.compare(b.fen(),played,best,actual)
        assert result['kind']=='tactical' # Incidental geometric differences do not make every error mixed.
        assert result['material']['before']==4 and result['material']['playedLine']==-5
        assert any('matto' in f for f in result['tacticalFacts'])
        assert result['features'][0]['side']==('b' if black else 'w')


def test_small_differences_are_not_labeled_as_an_error_and_incomplete_lines_are_unknown():
    b=chess.Board()
    result=insights.compare(b.fen(),'e2e3',value(b,['e2e4'],20),value(b,['e2e3'],0))
    assert result['kind']=='neutral'
    assert insights.compare(b.fen(),'e2e3',value(b,[]),value(b,['e2e3']))['kind']=='unclear'


def test_promoted_bishops_on_the_same_color_are_not_a_bishop_pair():
    b=chess.Board('7k/8/8/8/8/4B3/8/2B4K w - - 0 1')
    assert not insights.features(b,chess.WHITE)['bishopPair']
    b.set_piece_at(chess.D1,chess.Piece(chess.BISHOP,chess.WHITE))
    assert insights.features(b,chess.WHITE)['bishopPair']


def test_mixed_requires_a_structural_change_as_well_as_tactical_evidence():
    b=chess.Board()
    # Controlled scores isolate classification from search variability.
    result=insights.compare(b.fen(),'f2f4',value(b,['g1f3','g8f6'],30),value(b,['f2f4','e7e5'],-99997,-3))
    assert result['kind']=='mixed' and result['tacticalFacts'] and result['positionalFacts']


def test_historical_analysis_is_enriched_without_rewriting_it_and_tutor_receives_facts(client,monkeypatch):
    g=client.post('/api/import',json={'pgn':'1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *'}).json()
    wait_analysis(client,g['id'])
    with main.database() as con:
        a=json.loads(main.find_game(con,g['id'])['analysis'])
        for key in ('moves','decisions','critical'):
            for d in a[key]:d.pop('insight',None)
        old=json.dumps(a)
        con.execute('UPDATE games SET analysis=? WHERE id=?',(old,g['id']))
    view=client.get('/api/games/'+g['id']).json()
    assert all('insight' in d for d in view['analysis']['moves'])
    with main.database() as con:assert main.find_game(con,g['id'])['analysis']==old
    transport=install_transport(monkeypatch)
    response=client.post(f"/api/games/{g['id']}/tutor",json={'version':6})
    assert response.status_code==200,response.text
    sent=json.loads(transport.call_args.kwargs['json']['messages'][1]['content'])
    assert all('features' in d['insight'] and 'lines' in d['insight'] for d in sent['decisions'])
    assert 'domains' in sent['practice']
    assert response.json()['coaching']['observations'][0]['strategicPlan']
    assert 'insight' in response.json()['evidence'][0]
    profile=client.get('/api/profile').json()
    assert sum(d['examples'] for d in profile['domains'])>0
    assert 'blunder misura il peggioramento' in tutor.PEDAGOGY


def test_new_tutor_rejects_explanations_without_the_three_dimensions(client,monkeypatch):
    g=client.post('/api/import',json={'pgn':'1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *'}).json()
    wait_analysis(client,g['id'])
    payload=sample_coaching();payload['observations'][0].pop('positional')
    install_transport(monkeypatch,payload={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]})
    response=client.post(f"/api/games/{g['id']}/tutor",json={'version':6})
    assert response.status_code==502
    assert client.get(f"/api/games/{g['id']}/tutor").json() is None
