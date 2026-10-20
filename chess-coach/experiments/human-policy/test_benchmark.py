from pathlib import Path

import chess
import pytest
import torch

from benchmark import FixedRating, MaiaReference, check_reference, latency, position_batch
from policy import inputs


@pytest.fixture(scope="module")
def reference():
    if not Path("baselines/maia3-5m.pt").exists():
        pytest.skip("Riferimento opzionale non scaricato")
    torch.set_num_threads(2)
    return MaiaReference("baselines/maia3", "baselines/maia3-5m.pt", "cpu")


def test_reference_matches_official_uci(reference):
    result = check_reference(reference, "cpu")
    assert result["positions"] == 5
    assert result["max_probability_difference"] < 2e-5


def test_reference_padding_cannot_receive_probability(reference):
    batch = position_batch(chess.STARTING_FEN, 600)
    batch["legal"] = torch.cat((batch["legal"], torch.full((1, 4), -1)), dim=1)
    with torch.inference_mode():
        probs = reference(*inputs(batch, "cpu")).softmax(-1)
    assert probs[0, -4:].sum() == 0
    assert float(probs.sum()) == pytest.approx(1.)
    assert torch.isfinite(probs).all()


def test_latency_returns_finite_measurements(reference):
    result = latency(reference, position_batch(chess.STARTING_FEN, 1000), "cpu", repeats=3)
    assert result["p50_ms"] > 0
    assert result["repeats"] == 3


def test_rating_ablation_matches_explicit_rating_and_preserves_input(reference):
    original = position_batch(chess.STARTING_FEN, 600)
    fixed = position_batch(chess.STARTING_FEN, 1500)
    saved = original["context"].clone()
    with torch.inference_mode():
        expected = reference(*inputs(fixed, "cpu"))
        actual = FixedRating(reference)(*inputs(original, "cpu"))
    torch.testing.assert_close(actual, expected)
    torch.testing.assert_close(original["context"], saved)


def test_reference_fetch_checks_existing_weights_without_network(tmp_path, monkeypatch):
    import hashlib
    import fetch_reference
    (tmp_path / "maia3").mkdir()
    target = tmp_path / "maia3-5m.pt"
    target.write_bytes(b"fixture")
    monkeypatch.setattr(fetch_reference, "SHA256", hashlib.sha256(b"fixture").hexdigest())
    monkeypatch.setattr(fetch_reference.subprocess, "check_output", lambda *a, **kw: fetch_reference.CODE_COMMIT)
    def no_network(*a, **kw):
        pytest.fail("Existing weights must not trigger a network request")
    monkeypatch.setattr(fetch_reference.urllib.request, "urlopen", no_network)
    assert fetch_reference.fetch(tmp_path)["bytes"] == 7
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Pesi esistenti"):
        fetch_reference.fetch(tmp_path)
