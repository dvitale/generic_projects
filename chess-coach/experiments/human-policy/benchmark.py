"""Isolated comparison on validation only; never opens the application's data."""
import argparse
from collections import deque
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import chess
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import Subset

from dataset import Positions
from features import encode, move_id
from policy import Config, Policy, collate, inputs
from train import evaluate, fingerprint


class FixedRating(nn.Module):
    """Ablation: remove rating information at inference, leaving targets unchanged."""
    def __init__(self, model, rating=1500):
        super().__init__()
        self.model = model
        self.rating = rating

    def forward(self, pieces, ep, context, legal):
        context = context.clone()
        context[:, 0] = (self.rating - 1500) / 1000
        return self.model(pieces, ep, context, legal)


class MaiaReference(nn.Module):
    def __init__(self, root, checkpoint, device):
        super().__init__()
        sys.path.insert(0, str(Path(root).resolve()))
        from maia3.uci import parse_args
        from maia3.models import MAIA3Model
        from maia3.utils import get_all_possible_moves, mirror_move
        self.cfg = parse_args(["--model", "maia3-5m", "--checkpoint-path", str(checkpoint),
                               "--device", str(device), "--no-use-amp"])
        self.model = MAIA3Model(self.cfg)
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        state = state.get("model_state_dict", state)
        self.model.load_state_dict({k.replace("smolgen", "gab"): v for k, v in state.items()}, strict=True)
        mapping = torch.full((2, 20480), -1, dtype=torch.long)
        for i, uci in enumerate(get_all_possible_moves()):
            # The vocabulary also contains impossible same-square moves.
            if uci[:2] == uci[2:4]:
                continue
            for side, text in ((1, uci), (0, mirror_move(uci))):
                mapping[side, move_id(chess.Move.from_uci(text))] = i
        self.register_buffer("mapping", mapping)
        self.to(device).eval()

    def tokens(self, pieces, context):
        mirrored = pieces[:, torch.arange(64, device=pieces.device) ^ 56]
        mirrored = torch.where(mirrored == 0, 0, (mirrored - 1 + 6) % 12 + 1)
        oriented = torch.where(context[:, 1:2].bool(), pieces, mirrored)
        tokens = F.one_hot(oriented, 13)[..., 1:].float().repeat(1, 1, self.cfg.history)
        return torch.cat((tokens, torch.zeros_like(tokens[..., :1])), dim=-1)

    def forward(self, pieces, ep, context, legal):
        rating = (context[:, 0] * 1000 + 1500).round().long()
        logits, _, _ = self.model(self.tokens(pieces, context), rating, rating)
        ids = self.mapping[context[:, 1].long()[:, None], legal.clamp_min(0)]
        if ((ids < 0) & (legal >= 0)).any():
            raise ValueError("Mossa legale assente dal vocabolario Maia")
        return logits.gather(1, ids.clamp_min(0)).masked_fill(legal < 0, float("-inf"))


def position_batch(fen, elo):
    board = chess.Board(fen)
    pieces, ep, context = encode(board, elo)
    return collate([dict(pieces=pieces, ep=ep, context=context, elo=elo, target=0,
                         legal=[move_id(m) for m in board.legal_moves])])


@torch.inference_mode()
def check_reference(model, device):
    from maia3.dataset import tokenize_board, get_historical_tokens
    from maia3.uci import Maia3UCIEngine
    # Both sides, castling, en passant and promotions; compare official UCI probabilities.
    fens = [chess.STARTING_FEN,
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "r3k2r/ppp2ppp/8/3pP3/8/8/PPP2PPP/R3K2R w KQkq d6 0 10",
            "7k/P7/8/8/8/8/7p/K7 w - - 0 1",
            "7k/P7/8/8/8/8/7p/K7 b - - 0 1"]
    engine = Maia3UCIEngine(model.cfg)
    engine.model = model.model
    engine.self_elo = engine.oppo_elo = 1000
    max_error = 0.
    for fen in fens:
        batch = position_batch(fen, 1000)
        args = inputs(batch, device)
        official = get_historical_tokens(deque([tokenize_board(chess.Board(fen))]),
                                         model.cfg, 0, 0, 0, 0)
        torch.testing.assert_close(model.tokens(args[0], args[2])[0].cpu(), official)
        probs = model(*args).softmax(-1)[0].cpu()
        engine.cmd_position("position fen " + fen)
        _, candidates = engine.score_moves()
        own = {int(key): float(p) for key, p in zip(batch["legal"][0], probs)}
        assert candidates, "Il controllo UCI deve produrre mosse"
        for item in candidates:
            delta = abs(own[move_id(item["move"])] - item["policy"])
            max_error = max(max_error, delta)
            assert delta < 2e-5, (fen, item, delta)
    return dict(positions=len(fens), max_probability_difference=max_error, precision="float32")


@torch.inference_mode()
def latency(model, batch, device, repeats=30):
    model.to(device).eval()
    args = inputs(batch, device)
    def synchronize():
        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
    for _ in range(5):
        model(*args)
    synchronize()
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        model(*args)
        synchronize()
        times.append(1000 * (time.perf_counter() - start))
    return dict(p50_ms=statistics.median(times), p95_ms=sorted(times)[int(.95 * (repeats - 1))],
                repeats=repeats, batch=1, scope="Warm forward only; excludes loading, FEN parsing and legal generation")


def compare(args):
    torch.set_num_threads(4)
    torch.manual_seed(42)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    data = Positions(args.data, "validation")
    if not len(data):
        raise ValueError("Validation vuota")
    rows = data.db.execute("SELECT id,game_id,ply,elo,fen FROM positions WHERE split='validation' ORDER BY id").fetchall()
    manifest = output / "positions.json"
    manifest.write_text(json.dumps(rows), encoding="utf-8")
    train_fens = {" ".join(row[0].split()[:4]) for row in
                  data.db.execute("SELECT fen FROM positions WHERE split='train'")}
    overlaps = sum(" ".join(row[4].split()[:4]) in train_fens for row in rows)
    novel = Subset(data, [i for i, row in enumerate(rows)
                         if " ".join(row[4].split()[:4]) not in train_fens])
    meta = json.loads(Path(args.reference).with_suffix(".json").read_text())
    actual_commit = subprocess.check_output(["git", "-C", args.reference_code, "rev-parse", "HEAD"], text=True).strip()
    if fingerprint(args.reference) != meta["sha256"] or actual_commit != meta["code_commit"]:
        raise ValueError("Riferimento diverso dal manifest scaricato")
    if subprocess.check_output(["git", "-C", args.reference_code, "diff", "HEAD", "--"], text=True):
        raise ValueError("Codice ufficiale modificato: confronto interrotto")
    report = dict(dataset_sha256=fingerprint(args.data), manifest_sha256=fingerprint(manifest),
                  validation_positions=len(data), validation_games=len({row[1] for row in rows}),
                  validation_positions_seen_in_train=overlaps, reference=meta, device=args.device,
                  torch=str(torch.__version__), gpu=torch.cuda.get_device_name() if torch.cuda.is_available() else None,
                  source_sha256={name: fingerprint(name) for name in
                                 ("features.py", "dataset.py", "policy.py", "train.py", "benchmark.py")},
                  test_split="Not evaluated", models={})
    example = collate([data[0]])
    for name, path in (("tiny", args.tiny), ("small", args.small), ("maia3_5m", args.reference)):
        if name == "maia3_5m":
            model = MaiaReference(args.reference_code, path, args.device)
            report["reference_adapter_check"] = check_reference(model, args.device)
        else:
            state = torch.load(path, map_location="cpu", weights_only=True)
            if state["dataset_sha256"] != report["dataset_sha256"]:
                raise ValueError("Checkpoint addestrato su un dataset diverso")
            model = Policy(Config(**state["config"])).to(args.device)
            model.load_state_dict(state["model"], strict=True)
        model.eval()
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        start = time.perf_counter()
        metrics = evaluate(model, data, args.device, 64)
        elapsed = time.perf_counter() - start
        novel_metrics = evaluate(model, novel, args.device, 64) if len(novel) else None
        fixed_metrics = evaluate(FixedRating(model), novel, args.device, 64) if len(novel) else None
        result = dict(checkpoint_sha256=fingerprint(path), parameters=sum(p.numel() for p in model.parameters()),
                      validation=metrics, evaluation_seconds=elapsed, positions_per_second=len(data)/elapsed,
                      novel_positions=novel_metrics, novel_fixed_rating_1500=fixed_metrics,
                      gpu_peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2 if args.device == "cuda" else None,
                      gpu_latency=latency(model, example, args.device) if args.device == "cuda" else None,
                      cpu_latency=latency(model, example, "cpu"))
        report["models"][name] = result
        print(json.dumps(dict(model=name, metrics=metrics["all"], cpu=result["cpu_latency"])), flush=True)
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        (output / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Confronto pilota — solo laboratorio", "",
             f"Validation: {len(data)} posizioni in {report['validation_games']} partite. Test finale non valutato.", "",
             "| Modello | Parametri | Top-1 | Top-3 | Top-5 | NLL ↓ | CPU mediana/mossa |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name, value in report["models"].items():
        m = value["validation"]["all"]
        lines.append(f"| {name} | {value['parameters']:,} | {m['top1']:.1%} | {m['top3']:.1%} | {m['top5']:.1%} | {m['nll']:.3f} | {value['cpu_latency']['p50_ms']:.2f} ms |")
    lines += ["", "Top-k: frequenza con cui la mossa umana registrata è fra le k proposte. Non è una misura di Elo o di vittorie.",
              "", "## Posizioni non presenti nel train e utilità del rating", "",
              "| Modello | Posizioni | Top-1 | NLL con rating reale ↓ | NLL con rating fisso 1500 ↓ |",
              "|---|---:|---:|---:|---:|"]
    for name, value in report["models"].items():
        if value["novel_positions"]:
            m = value["novel_positions"]["all"]
            fixed = value["novel_fixed_rating_1500"]["all"]
            lines.append(f"| {name} | {m['count']} | {m['top1']:.1%} | {m['nll']:.3f} | {fixed['nll']:.3f} |")
    lines += ["", "L'ablazione cambia solo il rating in ingresso: una NLL più bassa col rating reale suggerisce informazione utile su questo campione, non dimostra forza calibrata.",
              "", "## Limiti del confronto", "",
              f"- {overlaps} posizioni di validation ricompaiono anche nel train (primi quattro campi FEN): split per partita, non per posizione.",
              "- Prototipi: 1.000 passi da 64 esempi; Maia è già addestrato su un corpus molto più ampio. Non è un confronto di architetture a parità di addestramento.",
              "- Campione rapid da un prefisso di settembre 2026, con fasce rare. Maia è un riferimento preaddestrato con dominio diverso.",
              "- Per Maia: sola FEN, storia riempita ripetendo la posizione corrente; rating avversario posto uguale al proprio; nessun tempo. Non riproduce il sito Maia.",
              "- Tutti i modelli: probabilità normalizzate sulle mosse legali, temperatura 1, nessuna ricerca Stockfish, inferenza float32.",
              "- Tempi CPU/GPU: modello già caricato, batch 1, 30 ripetizioni; esclusi caricamento, parsing FEN e generazione delle mosse legali.",
              "- Nessun collegamento con il gioco, le analisi, i dati o il servizio di SparringMate."]
    (output / "CONFRONTO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/pilot.sqlite")
    parser.add_argument("--tiny", default="runs/tiny-pilot/last.pt")
    parser.add_argument("--small", default="runs/small-pilot/last.pt")
    parser.add_argument("--reference", default="baselines/maia3-5m.pt")
    parser.add_argument("--reference-code", default="baselines/maia3")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--output", default="runs/comparison-pilot")
    compare(parser.parse_args())
