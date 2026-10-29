import json
from pathlib import Path

import chess
import pytest

from backend.maia import Maia, maia

REFERENCE = json.loads((Path(__file__).parent / 'fixtures' / 'maia_reference.json').read_text())['positions']
needs_model = pytest.mark.skipif(not maia.available(), reason='modello Maia o onnxruntime assenti')


@pytest.mark.parametrize('case', REFERENCE, ids=lambda c: c['fen'])
def test_encoding_matches_browser(case):
    tokens, legal, _ = maia.encode(case['fen'])
    assert [int(i) for i in tokens.flatten().nonzero()[0]] == case['tokens']
    assert sorted([uci, index] for uci, index in legal) == case['legal']


@needs_model
def test_probabilities_match_browser_in_one_batch():
    cases = [c for c in REFERENCE if 'browserTop3' in c]
    for case, prediction in zip(cases, maia.predict_many([(c['fen'], 1500, 1500) for c in cases])):
        assert [m['uci'] for m in prediction['moves'][:3]] == [uci for uci, _ in case['browserTop3']]
        for move, (_, expected) in zip(prediction['moves'], case['browserTop3']):
            assert move['probability'] == pytest.approx(expected, abs=0.005)
        assert sum(m['probability'] for m in prediction['moves']) == pytest.approx(1, abs=1e-4)


@needs_model
def test_value_head_is_from_white_and_terminal_positions_need_no_model():
    mated = chess.Board('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3')
    black, white = maia.predict_many([('6k1/8/8/8/8/8/1q6/K7 b - - 0 1', 1500, 1500), ('k7/1Q6/8/8/8/8/8/6K1 w - - 0 1', 1500, 1500)])
    assert black['whiteExpectedScore'] < 0.2 and black['whiteOutcome']['loss'] > black['whiteOutcome']['win']
    # The mirrored position is the same decision for the other colour.
    assert black['whiteExpectedScore'] == pytest.approx(1 - white['whiteExpectedScore'], abs=1e-4)
    assert maia.predict(mated.fen(), 1500, 1500) == {'moves': [], 'whiteExpectedScore': 0.5, 'whiteOutcome': {'win': 0, 'draw': 1, 'loss': 0}}


@needs_model
def test_elo_changes_the_human_choice_and_batches_keep_order():
    fen = REFERENCE[3]['fen']
    weak, strong, again = maia.predict_many([(fen, 800, 800), (fen, 2200, 2200), (fen, 800, 800)])
    assert weak == again and weak['moves'] != strong['moves']


def test_missing_model_is_reported_not_raised(tmp_path):
    assert not Maia(tmp_path / 'missing.onnx').available()
