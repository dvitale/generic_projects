import json
from datetime import datetime, timedelta

import chess

from test_coach import client
from backend import main, opening_lines


def play(client, s, uci):
    return client.post(f"/api/opening-lines/sessions/{s['id']}/move", json={'move': uci, 'version': s['version']})


def test_every_line_is_legal_starts_from_its_family_and_has_a_name():
    assert len(opening_lines.FAMILY) == 7 and len(opening_lines.LINE) == 63
    for family in opening_lines.FAMILY.values():
        for line in family['lines']:
            assert line['moves'][:len(family['rootMoves'])] == family['rootMoves'] and line['name']
    # Names come from the Lichess catalogue when the final position has one.
    assert opening_lines.LINE['italiana:fried-liver']['name'] == 'Two Knights Defense, Fried Liver Attack'
    assert opening_lines.LINE['russa:damiano']['name'] == 'Damiano Variation'
    # A line that another one extends is not an end of the review tree.
    ends = opening_lines.terminal('italiana')
    assert 'italiana:fried-liver' in ends and 'italiana:knight-attack' not in ends and 'italiana:giuoco-piano' not in ends


def test_catalog_counts_the_games_that_reached_each_line(client):
    moves = [m.uci() for m in _sans('e4 e5 Nf3 Nf6 Nxe5 Nxe4 Qe2')]
    with main.database() as con:
        con.execute("INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,source) VALUES(?,?,?,?,?,?,?,?)",
                    ('g1', chess.STARTING_FEN, json.dumps(moves), 'w', 1500, 'Petroff', main.now(), 'maia'))
    families = {f['id']: f for f in client.get('/api/opening-lines?color=w').json()}
    lines = {l['id']: l for l in families['russa']['lines']}
    assert families['russa']['games'] == 1 and lines['russa:damiano']['met'] == 1 and lines['russa:stafford']['met'] == 0
    assert families['italiana']['games'] == 0
    assert all(l['met'] == 0 for l in client.get('/api/opening-lines?color=b').json()[2]['lines'])


def _sans(text):
    board, out = chess.Board(), []
    for san in text.split():
        out.append(board.push_san(san))
    return out


def test_review_rejects_moves_out_of_book_shows_the_book_and_schedules_the_line(client):
    s = client.post('/api/opening-lines/sessions', json={'family': 'italiana', 'color': 'w', 'lines': ['italiana:hungarian']}).json()
    assert s['status'] == 'active' and s['turn'] == 'w' and s['moves'] == []
    wrong = play(client, s, 'd2d4').json()
    assert wrong['wrong'] == {'san': 'd4', 'expected': ['e4']} and wrong['moves'] == [] and wrong['expected'] == ['e4']
    s = play(client, wrong, 'e2e4').json()
    # The opponent answers from the book at once.
    assert s['sans'] == ['e4', 'e5'] and s['reply'] == 'e7e5' and s['expected'] is None
    assert play(client, {**s, 'version': 0}, 'g1f3').status_code == 409
    s = play(client, s, 'g1f3').json()
    s = play(client, s, 'f1c4').json()
    assert s['status'] == 'complete' and s['sans'][-1] == 'Be7' and s['line']['id'] == 'italiana:hungarian'
    assert s['errors'] == [{'ply': 0, 'played': ['d4'], 'expected': ['e4']}]
    # An error resets the line: it comes back in four hours, and the plan lists it.
    assert s['review']['streak'] == 0 and s['independent']
    with main.database() as con:
        rows = opening_lines.plan_rows(con)
    assert [(r['kind'], r['id'], r['stage']) for r in rows] == [('line', 'italiana:hungarian:w', 0)]
    assert play(client, s, 'e1g1').status_code == 409


def test_a_clean_review_promotes_the_line_and_an_early_repetition_is_practice(client):
    def clean():
        s = client.post('/api/opening-lines/sessions', json={'family': 'italiana', 'color': 'w', 'lines': ['italiana:hungarian']}).json()
        for uci in ('e2e4', 'g1f3', 'f1c4'):
            s = play(client, s, uci).json()
        return s
    first = clean()
    assert first['errors'] == [] and first['review']['streak'] == 1 and first['independent']
    second = clean()
    assert not second['independent'] and second['review']['streak'] == 1
    with main.database() as con:
        con.execute("UPDATE opening_line_reviews SET due_at=?", ((datetime.fromisoformat(main.now()) - timedelta(hours=1)).isoformat(),))
    assert clean()['review']['streak'] == 2
    assert client.get('/api/training-plan').status_code == 200


def test_as_black_the_opponent_opens_and_a_hint_counts_as_help(client):
    s = client.post('/api/opening-lines/sessions', json={'target': 'caro-kann:panov', 'color': 'b'}).json()
    assert s['family'] == 'caro-kann' and s['sans'] == ['e4'] and s['target'] == 'Panov Attack'
    s = client.post(f"/api/opening-lines/sessions/{s['id']}/hint", json={'version': s['version']}).json()
    assert s['expected'] == ['c6'] and s['hints'] == 1
    # The target steers the opponent: 2.d4 d5 3.exd5 cxd5 4.c4.
    for uci in ('c7c6', 'd7d5', 'c6d5'):
        s = play(client, s, uci).json()
    assert s['status'] == 'complete' and s['line']['name'] == 'Panov Attack' and s['review']['streak'] == 0


def test_a_drill_starts_against_maia_from_the_end_of_a_line(client):
    g = client.post('/api/drills/line:russa:damiano-qe2/start', json={'color': 'w', 'target': 3}).json()
    assert g['drill']['startPly'] == 11 and g['title'].startswith('Difesa russa (Petroff): Damiano Variation, 4.Qe2')
    assert client.post('/api/drills/line:russa:nope/start', json={}).status_code == 404
