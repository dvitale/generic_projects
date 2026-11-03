import json

from backend import mistakes
from backend.engine import OUTCOME_CAP_CP, critical, load_analysis, missed_mate, review_label, review_loss


def score(cp=None, mate=None):
    # Same convention as Evaluator._format: mate scores use the 100000 sentinel.
    return {'cp': (100000 - mate if mate > 0 else -100000 - mate) if mate is not None else cp, 'mate': mate}


def test_the_outcome_cap_ignores_margins_beyond_a_decided_game():
    # +18 or +12: still won (game #100, 32. Ne2 against Re1+).
    assert review_loss(score(cp=1828), score(cp=1252)) == 0
    # Mate in 4 or +13.7: still won (game #37, Bc3+ against Nc7).
    assert review_loss(score(mate=4), score(cp=1371)) == 0
    # Already lost: drowning in 3 or 1200 metres of water is the same.
    assert review_loss(score(cp=-1200), score(cp=-1800)) == 0
    assert review_loss(score(cp=-900), score(mate=-2)) == 0
    # From won to unclear and from unclear to lost are real losses.
    assert review_loss(score(cp=800), score(cp=200)) == OUTCOME_CAP_CP - 200
    assert review_loss(score(cp=100), score(cp=-700)) == 100 + OUTCOME_CAP_CP
    assert review_loss(score(cp=300), score(mate=-2)) == 300 + OUTCOME_CAP_CP
    assert review_loss(score(cp=50), score(cp=-150)) == 200


def test_a_short_mate_missed_is_its_own_kind_of_mistake():
    assert missed_mate(score(mate=1), score(cp=1500))
    assert missed_mate(score(mate=2), score(mate=5))
    assert not missed_mate(score(mate=1), score(mate=2))
    assert not missed_mate(score(mate=4), score(cp=1500))
    item = {'best': score(mate=1), 'actual': score(cp=1500), 'loss': 0, 'missedMate': True}
    assert review_label(item) == 'Matto mancato'
    assert review_label({**item, 'forced': True}) == 'Mossa obbligata'
    assert review_label({'loss': 576, 'missedMate': False}) == 'Errore'
    assert review_label({'loss': 100}) == 'Imprecisione'
    assert review_label({'loss': 0}) == 'Buona scelta'


def test_puzzles_follow_the_same_rule():
    assert mistakes.accepted(score(cp=1828), score(cp=1252))
    assert not mistakes.accepted(score(mate=1), score(cp=1500))
    assert mistakes.accepted(score(mate=1), score(mate=2))
    assert not mistakes.accepted(score(cp=150), score(cp=60))


def test_stored_analyses_are_rescored_and_relabelled_on_load():
    won = {'ply': 10, 'best': score(cp=1828), 'actual': score(cp=1252), 'loss': 576, 'label': 'Errore'}
    mate = {'ply': 11, 'best': score(mate=1), 'actual': score(cp=900), 'loss': 0, 'label': 'Buona scelta'}
    small = {'ply': 12, 'best': score(cp=100), 'actual': score(cp=-50), 'loss': 150, 'label': 'Imprecisione'}
    analysis = load_analysis(json.dumps({'moves': [won, mate, small], 'decisions': [won, mate, small], 'critical': [won]}))
    assert [(d['loss'], d['label']) for d in analysis['decisions']] == [(0, 'Buona scelta'), (0, 'Matto mancato'), (150, 'Imprecisione')]
    assert [d['ply'] for d in analysis['critical']] == [11, 12]
    assert [d['ply'] for d in critical(analysis['decisions'])] == [11, 12]
