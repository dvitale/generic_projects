import json

from backend.engine import DECISIVE_CP, load_analysis, review_loss


def score(cp=None, mate=None):
    # Same convention as Evaluator._format: mate scores use the 100000 sentinel.
    return {'cp': (100000 - mate if mate > 0 else -100000 - mate) if mate is not None else cp, 'mate': mate}


def test_long_mates_count_as_a_decisive_edge_and_short_ones_keep_full_weight():
    # Missing a mate in 8 while staying at +6 is not a blunder; dropping to +3 still costs something.
    assert review_loss(score(mate=8), score(cp=600)) == 0
    assert review_loss(score(mate=4), score(cp=300)) == DECISIVE_CP - 300
    # Missing a mate in 1 or 2 stays a blunder.
    assert review_loss(score(mate=2), score(cp=600)) > 90000
    assert review_loss(score(mate=1), score(cp=600)) > 90000
    # Allowing a long mate when already lost is not a new blunder; allowing mate in 2 is.
    assert review_loss(score(cp=-400), score(mate=-7)) == 100
    assert review_loss(score(cp=-400), score(mate=-2)) > 90000
    # Two mates for the same side: still mating, the difference stays small.
    assert review_loss(score(mate=1), score(mate=5)) == 4
    assert review_loss(score(cp=50), score(cp=-150)) == 200


def test_stored_analyses_are_rescored_on_load():
    item = {'ply': 10, 'best': score(mate=6), 'actual': score(cp=700), 'loss': 99294}
    small = {'ply': 12, 'best': score(cp=100), 'actual': score(cp=-50), 'loss': 150}
    analysis = load_analysis(json.dumps({'moves': [item, small], 'decisions': [item, small], 'critical': [item]}))
    assert [d['loss'] for d in analysis['decisions']] == [0, 150]
    assert [d['ply'] for d in analysis['critical']] == [12]
