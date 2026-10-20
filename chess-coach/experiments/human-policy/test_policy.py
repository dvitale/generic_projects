import io
import json
import sqlite3
from dataclasses import asdict

import chess
import chess.pgn
import pytest
import torch

from dataset import CompleteGameBuilder, extract, speed_of, split_for
from policy import Config, Policy, collate, encode, inputs, move_id, predict
from train import evaluate

torch.set_num_threads(2)


@pytest.mark.parametrize("fen", [
    chess.STARTING_FEN,
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
    "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
    "4k3/P7/8/8/8/8/7p/4K3 w - - 0 1",
])
def test_legal_action_encoding_is_unique(fen):
    board = chess.Board(fen)
    moves = list(board.legal_moves)
    ids = [move_id(m) for m in moves]
    assert len(ids) == len(set(ids))
    assert all(0 <= i < 64 * 64 * 5 for i in ids)
    if board.piece_at(chess.A7):
        assert len({move_id(chess.Move.from_uci("a7a8" + p)) for p in "nbrq"}) == 4


def test_position_context_preserves_turn_castling_ep_and_rating():
    board = chess.Board()
    first = encode(board, 600)
    second = encode(board, 1600)
    assert first[:2] == second[:2]
    assert second[2][0] - first[2][0] == pytest.approx(1.)
    board.push_uci("e2e4")
    _, ep, context = encode(board, 600)
    assert ep[chess.E3] == 1
    assert context[1] == 0
    assert context[2:6] == [1., 1., 1., 1.]


def test_model_legal_mask_rating_conditioning_and_gradient():
    torch.manual_seed(5)
    board = chess.Board()
    pieces, ep, context = encode(board, 600)
    item = dict(pieces=pieces, ep=ep, context=context, elo=600,
                legal=[move_id(m) for m in board.legal_moves], target=0)
    shorter = {**item, "legal": item["legal"][:2]}
    batch = collate([item, shorter])
    model = Policy(Config(dim=32, layers=1, heads=4, head_dim=8, dropout=0))
    logits = model(*inputs(batch, "cpu"))
    assert torch.isneginf(logits[1, 2:]).all()
    assert torch.allclose(logits.softmax(-1).sum(-1), torch.ones(2))
    modified = batch["context"].clone()
    modified[:, 0] += 1
    changed = model(batch["pieces"], batch["ep"], modified, batch["legal"])
    assert not torch.allclose(logits[0], changed[0])
    torch.nn.functional.cross_entropy(logits, batch["target"]).backward()
    assert model.context[0].weight.grad.abs().sum() > 0


def pgn(site="abcdefgh", white=600, black=1600, title="", result="0-1"):
    return f'''[Event "Rated Rapid game"]
[Site "https://lichess.org/{site}"]
[WhiteElo "{white}"]
[BlackElo "{black}"]
[WhiteTitle "{title}"]
[TimeControl "900+10"]
[Result "{result}"]

1. e4 e5 2. Nf3 Nc6 {result}

'''


def test_extraction_side_ratings_filter_bots_and_resume(tmp_path):
    source, dest = tmp_path / "sample.pgn", tmp_path / "positions.sqlite"
    source.write_text(pgn() + pgn("ijklmnop", title="BOT") + pgn("qrstuvwx", result="*"))
    extract(source, dest, max_games=10)
    with sqlite3.connect(dest) as db:
        rows = db.execute("SELECT ply,elo,split FROM positions ORDER BY ply").fetchall()
    assert [r[1] for r in rows] == [600, 1600, 600, 1600]
    assert len({r[2] for r in rows}) == 1
    extract(source, dest, max_games=10)
    with sqlite3.connect(dest) as db:
        assert db.execute("SELECT count(*) FROM positions").fetchone()[0] == 4
    with pytest.raises(ValueError, match="diversi"):
        extract(source, dest, speed="blitz")


def test_truncated_movetext_is_not_accepted(tmp_path):
    text = pgn().replace("2. Nf3 Nc6 0-1", "2. Nf3")
    game = chess.pgn.read_game(io.StringIO(text), Visitor=CompleteGameBuilder)
    assert not getattr(game, "has_movetext_result", False)
    source, dest = tmp_path / "partial.pgn", tmp_path / "partial.sqlite"
    source.write_text(text)
    extract(source, dest)
    with sqlite3.connect(dest) as db:
        assert db.execute("SELECT count(*) FROM positions").fetchone()[0] == 0


def test_speed_and_split():
    assert speed_of("900+10") == "rapid"
    assert speed_of("300+0") == "blitz"
    assert speed_of("-") is None
    assert split_for("00000005" + "0" * 56) == "test"
    assert split_for("0000000f" + "0" * 56) == "validation"
    assert split_for("00000020" + "0" * 56) == "train"


def test_uniform_policy_metrics():
    class Uniform(torch.nn.Module):
        def forward(self, pieces, ep, context, legal):
            return torch.zeros_like(legal, dtype=torch.float).masked_fill(legal < 0, -torch.inf)
    pieces, ep, context = encode(chess.Board(), 600)
    item = dict(pieces=pieces, ep=ep, context=context, legal=[0, 1, 2, 3], target=0, elo=600)
    metrics = evaluate(Uniform(), [item], "cpu")
    assert metrics["all"]["nll"] == pytest.approx(metrics["all"]["uniform_nll"])
    assert metrics["all"]["top5"] == 1
    assert metrics["600"]["count"] == 1


def test_prediction_top5_keeps_full_distribution_probabilities(tmp_path):
    cfg = Config(dim=32, layers=1, heads=4, head_dim=8, dropout=0)
    model = Policy(cfg)
    # A zero policy is uniform over the 20 legal starting moves.
    for parameter in model.parameters():
        parameter.data.zero_()
    checkpoint = tmp_path / "model.pt"
    torch.save(dict(config=asdict(cfg), model=model.state_dict(), rating_bounds=[600, 2600],
                    dataset={"speed": "rapid"}, step=0), checkpoint)
    result = predict(checkpoint, chess.STARTING_FEN, 600)
    assert len(result["moves"]) == 5
    assert result["legal_move_count"] == 20
    assert all(m["probability"] == pytest.approx(.05) for m in result["moves"])
    assert result["other_probability"] == pytest.approx(.75)
    with pytest.raises(ValueError, match="fuori"):
        predict(checkpoint, chess.STARTING_FEN, 500)
    terminal = predict(checkpoint, "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", 600)
    assert terminal["terminal"] and terminal["moves"] == []
    assert terminal["other_probability"] == 0


def test_dataset_roundtrip_preserves_legal_targets_and_fen(tmp_path):
    from dataset import Positions
    from policy import PROMOTIONS
    source, dest = tmp_path / "sample.pgn", tmp_path / "positions.sqlite"
    source.write_text(pgn())
    extract(source, dest)
    with sqlite3.connect(dest) as db:
        split = db.execute("SELECT split FROM positions LIMIT 1").fetchone()[0]
        fens = db.execute("SELECT fen FROM positions ORDER BY id").fetchall()
    data = Positions(dest, split)
    for i in range(len(data)):
        item = data[i]
        board = chess.Board(fens[i][0])
        action = item["legal"][item["target"]]
        move = chess.Move(action // 320, action // 5 % 64, promotion=PROMOTIONS[action % 5])
        assert move in board.legal_moves
        encoded = encode(board, item["elo"])
        assert item["pieces"] == encoded[0]
        assert item["ep"] == encoded[1]
        assert item["context"] == pytest.approx(encoded[2])


def test_resume_matches_uninterrupted_training(tmp_path, monkeypatch):
    import signal
    from types import SimpleNamespace
    import train as training

    source, dest = tmp_path / "resume.pgn", tmp_path / "resume.sqlite"
    source.write_text("".join(pgn(f"{i:08d}") for i in range(80)))
    extract(source, dest, max_games=100)
    monkeypatch.setattr(training, "Config", lambda: Config(dim=32, layers=1, heads=4, head_dim=8))
    base = dict(data=str(dest), preset="tiny", device="cpu", threads=2, seed=42,
                batch_size=4, lr=.001, save_every=1)
    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        training.train(SimpleNamespace(**base, run=str(tmp_path / "full"), steps=2, resume=False))
        training.train(SimpleNamespace(**base, run=str(tmp_path / "split"), steps=1, resume=False))
        training.train(SimpleNamespace(**base, run=str(tmp_path / "split"), steps=1, resume=True))
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    full = torch.load(tmp_path / "full/last.pt", weights_only=True)
    resumed = torch.load(tmp_path / "split/last.pt", weights_only=True)
    assert resumed["step"] == full["step"] == 2
    assert torch.equal(full["sampler_rng"], resumed["sampler_rng"])
    for name, value in full["model"].items():
        assert torch.equal(value, resumed["model"][name]), name
