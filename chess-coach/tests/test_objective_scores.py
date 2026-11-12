from backend import alternatives, prevention, study
from backend.engine import LOSS_NOTE, objective
from test_coach import client  # noqa: F401


def test_scores_are_shown_on_one_objective_scale_whoever_moves():
    # The same loss of 1,20 for the player: down for White, up for Black.
    assert objective({'cp': -120, 'mate': None}, True) == '−1,20'
    assert objective({'cp': -120, 'mate': None}, False) == '+1,20'
    assert objective({'cp': 0, 'mate': None}, False) == '+0,00'
    assert objective({'cp': 0, 'mate': 3}, False) == 'matto del Nero in 3'
    assert objective({'cp': 0, 'mate': -2}, False) == 'matto del Bianco in 2'
    assert study.score_text({'cp': 250, 'mate': None}, False) == '−2,50'
    assert 'per il Nero, salire di 1,20' in LOSS_NOTE


def test_rules_and_messages_no_longer_speak_from_the_players_side():
    # The prevention rule speaks in expected-score points, the same for both colours.
    assert 'tuo punto di vista' not in prevention.RULE and '20 punti' in prevention.RULE
    import chess
    black = chess.Board('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1')
    assert alternatives.fmt({'cp': 80, 'mate': None}, black) == '−0,80'


def test_the_guide_explains_the_score_where_the_screens_link_to_it(client):
    html = client.get('/api/training-guide/html').text
    assert 'id="come-si-legge-il-punteggio"' in html and 'per il Nero, salire di 1,20' in html
    assert '## Come si legge il punteggio' in client.get('/api/training-guide').text
