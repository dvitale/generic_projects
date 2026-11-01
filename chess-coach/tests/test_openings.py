import chess
from backend import openings
from test_coach import client


def ucis(san):
    board = chess.Board()
    return [board.push_san(m).uci() for m in san.split()]


def test_named_positions_and_book_exit():
    found = openings.classify(chess.STARTING_FEN, ucis('e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 h3 h6'))
    assert (found['eco'], found['name']) == ('C70', 'Ruy Lopez: Morphy Defense')
    # 4. Ba4 Nf6 has no name of its own but lies on named lines, so it is still theory; 5. h3 leaves.
    assert found['ply'] == 6 and found['bookPlies'] == 8
    assert [p['ply'] for p in found['positions']][:3] == [1, 2, 3]


def test_transpositions_reach_the_same_name():
    direct = openings.classify(chess.STARTING_FEN, ucis('e4 e5 Nf3 Nc6 Bb5'))
    other = openings.classify(chess.STARTING_FEN, ucis('Nf3 Nc6 e4 e5 Bb5'))
    assert other['name'] == direct['name'] == 'Ruy Lopez' and other['bookPlies'] == 5


def test_unnamed_games_and_positions():
    assert openings.classify(chess.STARTING_FEN, []) is None
    assert openings.classify('7k/8/5KQ1/8/8/8/8/8 w - - 0 1', ['g6g7']) is None


def test_opening_in_game_list_review_and_pgn(client):
    game = client.post('/api/import', json={'pgn': '1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. h4 *', 'color': 'w'}).json()
    assert game['opening']['name'] == 'Sicilian Defense: Najdorf Variation' and game['opening']['bookPlies'] == 10
    listed = next(g for g in client.get('/api/games').json() if g['id'] == game['id'])
    assert listed['opening'] == {'eco': 'B90', 'name': 'Sicilian Defense: Najdorf Variation', 'bookPlies': 10}
    assert '[ECO "B90"]' in game['pgn'] and '[Opening "Sicilian Defense: Najdorf Variation"]' in game['pgn']
    # Headers of an imported PGN win over the catalogue.
    tagged = client.post('/api/import', json={'pgn': '[ECO "B00"]\n\n1. e4 c5 *', 'color': 'w'}).json()
    assert '[ECO "B00"]' in tagged['pgn'] and '[Opening ' not in tagged['pgn']


def entry(i, san, color='w', score=None, losses=()):
    moves = ucis(san)
    opening = openings.classify(chess.STARTING_FEN, moves)
    book = opening['bookPlies']
    return {'id': f'g{i}', 'number': i, 'title': f'Partita {i}', 'color': color, 'moves': moves, 'opening': opening, 'score': score,
            'decisions': [{'ply': book + 2 * k, 'loss': loss} for k, loss in enumerate(losses)]}


def test_repertoire_groups_families_and_judges_after_the_book():
    ruy = 'e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 h3 h6 a3'
    games = [entry(1, ruy, score=0, losses=(10, 200, 10)), entry(2, ruy, score=0.5, losses=(10, 10, 90)),
             entry(3, 'e4 e5 Nf3 Nc6 Bb5 Nf6 h3', score=0), entry(4, 'd4 d5 c4 e6 h3', color='b', score=1, losses=(10, 10)),
             entry(5, ruy)]
    result = openings.repertoire(games)
    ruy_lopez = result['families'][0]
    assert (ruy_lopez['family'], ruy_lopez['color'], ruy_lopez['games'], ruy_lopez['finished']) == ('Ruy Lopez', 'w', 4, 3)
    assert ruy_lopez['score'] == 0.5 / 3 and ruy_lopez['status'] == 'weak'
    assert ruy_lopez['decisions'] == 6 and ruy_lopez['errors'] == 1 and ruy_lopez['firstMistake'] == 2.5
    # The newest game still past the book gives the position to review and train.
    assert ruy_lopez['exit']['gameId'] == 'g1' and ruy_lopez['exit']['ply'] == 8
    assert ruy_lopez['exit']['fen'].startswith('r1bqkb1r/1ppp1ppp/p1n2n2/4p3/B3P3/5N2')
    gambit = result['families'][1]
    assert (gambit['family'], gambit['color'], gambit['status'], gambit['sound']) == ("Queen's Gambit Declined", 'b', 'watch', 1)


def test_repertoire_endpoint_and_drill_from_the_book_exit(client):
    # Different games (an identical PGN is imported once), all leaving the book after 2...d6.
    for third, result in (('h3', '0-1'), ('a3', '0-1'), ('h4', '1/2-1/2')):
        client.post('/api/import', json={'pgn': f'1. e4 e5 2. Nf3 d6 3. {third} h6 {result}', 'color': 'w'})
    families = client.get('/api/openings/repertoire').json()['families']
    philidor = next(f for f in families if f['family'] == 'Philidor Defense' and f['color'] == 'w')
    assert philidor['games'] == 3 and philidor['score'] == 0.5 / 3 and philidor['status'] == 'weak'
    drill = next(d for d in client.get('/api/drills').json() if d['id'] == 'opening:' + philidor['exit']['gameId'])
    assert drill['name'] == 'Fine della teoria: Philidor Defense' and drill['fen'] == philidor['exit']['fen'] and drill['color'] == 'w'
    game = client.post(f"/api/drills/{drill['id']}/start", json={'color': 'b', 'elo': 1500}).json()
    assert game['moves'] == ucis('e4 e5 Nf3 d6') and game['playerColor'] == 'w' and game['source'] == 'drill'
    assert game['drill']['startPly'] == 4
