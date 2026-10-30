import json
import sys
from pathlib import Path

import chess
import pytest

from backend.maia import MODEL_VERSION
from backend import main, opponents
from test_coach import client  # noqa: F401

sys.path.insert(0, str(Path(__file__).parent / 'fixtures'))
import fake_policy_service  # noqa: E402


@pytest.fixture
def policy(client, monkeypatch):
    server, state = fake_policy_service.start()
    monkeypatch.setenv('SPARRINGMATE_EXPERIMENTAL_ENGINE', f'http://127.0.0.1:{server.server_port}/')
    yield state
    server.shutdown()


def reply(client, g):
    return client.post(f"/api/games/{g['id']}/policy-move", json={'version': g['version'], 'revision': g['revision']})


def test_selector_is_hidden_without_configuration_and_maia_games_record_their_engine(client, monkeypatch):
    monkeypatch.delenv('SPARRINGMATE_EXPERIMENTAL_ENGINE', raising=False)
    monkeypatch.setattr(main, 'ENV_PATH', Path('/nonexistent/.env'))
    assert client.get('/api/opponents').json()['experimental'] == {'enabled': False}
    assert client.post('/api/games', json={'engine': 'experimental'}).status_code == 409
    g = client.post('/api/games', json={'elo': 1100, 'engine_version': 'maia3-test'}).json()
    # The server names the model it runs: a version sent by the page is ignored.
    assert (g['engine'], g['engineLabel'], g['engineVersion'], g['moveSelection']) == ('maia', 'Maia', MODEL_VERSION, opponents.SELECTION)
    g = client.post(f"/api/games/{g['id']}/moves", json={'move': 'e2e4', 'version': 0, 'actor': 'human'}).json()
    g = client.post(f"/api/games/{g['id']}/moves", json={'move': 'e7e5', 'version': 1, 'actor': 'maia'}).json()
    assert '[OpponentEngine "maia"]' in g['pgn'] and f'[OpponentEngineVersion "{MODEL_VERSION}"]' in g['pgn'] and '[Black "Maia 1100"]' in g['pgn']
    # Maia moves come from the browser, never from the experimental endpoint.
    assert reply(client, g).status_code == 409


def test_experimental_game_fixes_engine_and_draws_reproducible_legal_moves(client, policy):
    status = client.get('/api/opponents').json()['experimental']
    assert status == {'enabled': True, 'available': True, 'engine': 'sparringmate-human-policy',
                      'version': fake_policy_service.VERSION, 'ratingBounds': [600, 2596], 'calibrated': False}
    assert client.post('/api/games', json={'engine': 'experimental', 'elo': 2600}).status_code == 422
    g = client.post('/api/games', json={'engine': 'experimental', 'elo': 1300, 'color': 'b', 'engine_version': 'ignored'}).json()
    assert (g['engineLabel'], g['engineVersion'], g['title']) == ('Sperimentale', fake_policy_service.VERSION, 'Allenamento con Sperimentale 1300')
    # The browser may not play the experimental engine's moves.
    assert client.post(f"/api/games/{g['id']}/moves", json={'move': 'e2e4', 'version': 0, 'actor': 'maia'}).status_code == 409
    r = reply(client, g)
    assert r.status_code == 200, r.text
    g = r.json()
    assert g['version'] == 1
    assert chess.Move.from_uci(g['moves'][0]) in chess.Board().legal_moves
    assert policy['requests'][-1] == {'fen': chess.STARTING_FEN, 'elo': 1300, 'context': {'gameId': g['id'], 'ply': 0, 'playerColor': 'b'}}
    with main.database() as con:
        choice = json.loads(main.find_game(con, g['id'])['move_choices'])[0]
    assert choice['engine'] == 'experimental' and choice['version'] == fake_policy_service.VERSION
    # Same distribution and seed, same move: the draw can be replayed.
    moves = [(m['uci'], m['probability']) for m in fake_policy_service.distribution(chess.STARTING_FEN)]
    assert opponents.sample(moves, choice['seed'])[0] == g['moves'][0]
    assert '[OpponentEngine "experimental"]' in g['pgn'] and '[White "Sperimentale 1300"]' in g['pgn'] and '[OpponentElo "1300"]' in g['pgn']
    listed = next(item for item in client.get('/api/games').json() if item['id'] == g['id'])
    assert listed['engineLabel'] == 'Sperimentale' and listed['engineVersion'] == fake_policy_service.VERSION
    # Undo drops the player's move and the reply together, with their records.
    g = client.post(f"/api/games/{g['id']}/moves", json={'move': 'e7e5' if g['moves'][0] != 'e7e5' else 'd7d5', 'version': 1, 'actor': 'human'}).json()
    g = reply(client, g).json()
    g = client.post(f"/api/games/{g['id']}/undo", json={'version': 3, 'revision': 0}).json()
    with main.database() as con:
        assert len(json.loads(main.find_game(con, g['id'])['move_choices'])) == g['version'] == 1


def test_sampling_follows_the_whole_distribution():
    moves = [('a', .5), ('b', .3), ('c', .2)]
    draws = [opponents.sample(moves, seed)[0] for seed in range(3000)]
    assert abs(draws.count('c') / 3000 - .2) < .03 and set(draws) == {'a', 'b', 'c'}
    assert opponents.sample(list(reversed(moves)), 7) == opponents.sample(moves, 7)


@pytest.mark.parametrize('mode,message', [('down', 'Errore del motore sperimentale'), ('illegal', 'diverse da quelle legali'), ('partial', 'diverse da quelle legali'),
                                          ('badsum', 'probabilità non valide'), ('version', 'iniziata con')])
def test_a_failing_service_stops_the_game_without_falling_back_to_maia(client, policy, mode, message):
    g = client.post('/api/games', json={'engine': 'experimental', 'color': 'b'}).json()
    policy['mode'] = mode
    r = reply(client, g)
    assert r.status_code == 503 and message in r.json()['detail']
    assert client.get('/api/games/' + g['id']).json()['moves'] == []
    policy['mode'] = 'ok'
    assert reply(client, g).json()['version'] == 1


def test_unavailable_service_blocks_new_experimental_games_but_not_maia(client, policy):
    policy['mode'] = 'down'
    status = client.get('/api/opponents').json()['experimental']
    assert status['enabled'] and not status['available']
    assert client.post('/api/games', json={'engine': 'experimental'}).status_code == 503
    assert client.post('/api/games', json={}).status_code == 200


def test_promotion_and_game_end_are_handled_by_the_experimental_engine(client, policy):
    # Black to move: a1 promotions are legal, and a1=Q is mate-free; the engine must pick a legal promotion when sampled.
    g = client.post('/api/games', json={'engine': 'experimental', 'color': 'w', 'fen': '7k/8/8/8/8/8/p7/4K3 b - - 0 1'}).json()
    g = reply(client, g).json()
    assert chess.Move.from_uci(g['moves'][0]) in chess.Board('7k/8/8/8/8/8/p7/4K3 b - - 0 1').legal_moves
    mate = client.post('/api/games', json={'engine': 'experimental', 'color': 'w', 'fen': '7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}).json()
    mate = client.post(f"/api/games/{mate['id']}/moves", json={'move': 'g6g7', 'version': 0, 'actor': 'human'}).json()
    assert mate['result'] == '1-0'
    assert reply(client, mate).status_code == 409


def test_maia_game_fixes_its_move_selection_and_records_it_per_move(client):
    assert client.post('/api/games', json={'move_selection': 'temperature-9'}).status_code == 422
    g = client.post('/api/games', json={'elo': 600, 'engine_version': 'maia3-test', 'move_selection': 'temperature-0.4-top-p-0.8'}).json()
    assert g['moveSelection'] == 'temperature-0.4-top-p-0.8'
    g = client.post(f"/api/games/{g['id']}/moves", json={'move': 'e2e4', 'version': 0, 'actor': 'human'}).json()
    g = client.post(f"/api/games/{g['id']}/moves", json={'move': 'e7e5', 'version': 1, 'actor': 'maia'}).json()
    assert '[MoveSelection "temperature-0.4-top-p-0.8"]' in g['pgn']
    with main.database() as con:
        choices = json.loads(main.find_game(con, g['id'])['move_choices'])
    assert choices == [None, {'engine': 'maia', 'version': MODEL_VERSION, 'selection': 'temperature-0.4-top-p-0.8'}]


def test_experimental_game_ignores_the_maia_selection(client, policy):
    g = client.post('/api/games', json={'engine': 'experimental', 'elo': 1300, 'move_selection': 'top-move'}).json()
    assert g['moveSelection'] == opponents.SELECTION


def test_experimental_engine_offers_to_resign_a_lost_game_instead_of_asking_the_service(client, policy, monkeypatch):
    monkeypatch.setattr(main, 'RESIGN_MIN_PLY', 0)
    g = client.post('/api/games', json={'engine': 'experimental', 'elo': 1300, 'fen': '7k/8/8/8/8/8/8/2QRK3 w - - 0 1'}).json()
    for human in ['e1e2', 'e2e3', 'e3e4']:
        g = client.post(f"/api/games/{g['id']}/moves", json={'move': human, 'version': g['version'], 'revision': g['revision'], 'actor': 'human'}).json()
        asked = len(policy['requests'])
        g = reply(client, g).json()
    assert g['resignOffer'] and g['termination'] is None and g['result'] is None and len(g['moves']) == 5
    # The third reply was an offer to resign: the service was not asked for it, nor while the offer waits.
    assert len(policy['requests']) == asked and reply(client, g).json()['resignOffer'] and len(policy['requests']) == asked
    g = client.post(f"/api/games/{g['id']}/resign-offer", json={'version': g['version'], 'revision': g['revision'], 'accept': True}).json()
    assert g['termination'] == 'engine_resign' and g['result'] == '1-0' and not g['resignOffer']
