"""Local bounded training, resumable checkpoints, held-out metrics and prediction."""
import argparse
from collections import Counter, defaultdict
from contextlib import nullcontext
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import signal
import sqlite3
import time

import torch
from torch.nn import functional as F
from torch.utils.data import ConcatDataset, DataLoader

from dataset import Positions
from policy import Config, Policy, collate, inputs, predict


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024**2), b""):
            h.update(chunk)
    return h.hexdigest()


@torch.inference_mode()
def evaluate(model, dataset, device, batch_size=32):
    model.eval()
    totals = defaultdict(lambda: dict(count=0, nll=0., uniform_nll=0., top1=0, top3=0, top5=0))
    bins = [dict(n=0, confidence=0., correct=0.) for _ in range(10)]
    for batch in DataLoader(dataset, batch_size=batch_size, collate_fn=collate):
        logits = model(*inputs(batch, device)).float()
        target = batch["target"].to(device)
        losses = F.cross_entropy(logits, target, reduction="none").cpu().tolist()
        probs = logits.softmax(-1)
        confidence, choice = probs.max(-1)
        ranking = logits.topk(min(5, logits.shape[1]), dim=1).indices
        matches = ranking.eq(target[:, None]).cpu()
        correct_items = choice.eq(target).cpu().tolist()
        confidence_items = confidence.cpu().tolist()
        counts = (batch["legal"] >= 0).sum(-1).tolist()
        for i, (elo, loss, choices) in enumerate(zip(batch["elo"].tolist(), losses, counts)):
            bucket = str(elo // 200 * 200)
            correct = int(correct_items[i])
            conf = confidence_items[i]
            bin_item = bins[min(9, int(conf * 10))]
            bin_item["n"] += 1
            bin_item["confidence"] += conf
            bin_item["correct"] += correct
            for key in ("all", bucket, "non_forced" if choices > 1 else "forced"):
                s = totals[key]
                s["count"] += 1
                s["nll"] += loss
                s["uniform_nll"] += math.log(choices)
                for k in (1, 3, 5):
                    s[f"top{k}"] += int(matches[i, :k].any())
    report = {}
    for key, values in totals.items():
        n = values["count"]
        report[key] = {k: v if k == "count" else v / n for k, v in values.items()}
    count = totals["all"]["count"]
    report["top1_ece"] = sum(
        abs(b["confidence"] - b["correct"]) for b in bins
    ) / count if count else None
    report["warning"] = "Campione esplorativo; calibrazione e generalizzazione non dimostrate"
    return report


def train(args):
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else torch.device(args.device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    cfg = Config() if args.preset == "tiny" else Config(dim=256, layers=6, heads=8, head_dim=64)
    validation_path = getattr(args, "validation_data", None) or args.data
    replay_path = getattr(args, "replay_data", None)
    initialize_from = getattr(args, "initialize_from", None)
    if args.resume and initialize_from:
        raise ValueError("Scegliere ripresa oppure passaggio da un checkpoint precedente")
    train_data, validation = Positions(args.data, "train"), Positions(validation_path, "validation")
    if not len(train_data) or not len(validation):
        raise ValueError("Servono posizioni sia train sia validation: ampliare il campione")
    with sqlite3.connect(args.data) as db:
        settings = json.loads(db.execute("SELECT value FROM meta WHERE key='settings'").fetchone()[0])
    signature = fingerprint(args.data)
    validation_signature = fingerprint(validation_path)
    replay_signature = fingerprint(replay_path) if replay_path else None
    run = Path(args.run)
    run.mkdir(parents=True, exist_ok=True)
    checkpoint = run / "last.pt"
    if checkpoint.exists() and not args.resume:
        raise FileExistsError("Run esistente: usare --resume o un'altra directory")
    model = Policy(cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    start_step = 0
    sampler = torch.Generator().manual_seed(args.seed)
    records = list(train_data.records)
    band_counts = Counter(elo // 200 for _, elo in records)
    sampling = "sqrt_inverse_frequency_capped_4_v1"
    largest_band = max(band_counts.values())
    weights = torch.tensor([min(4., math.sqrt(largest_band / band_counts[elo // 200]))
                            for _, elo in train_data.records], dtype=torch.double)
    replay_count = 0
    if replay_path:
        replay = Positions(replay_path, "train")
        replay_count = len(replay)
        if replay_count:
            replay_bands = Counter(elo // 200 for _, elo in replay.records)
            largest = max(replay_bands.values())
            replay_weights = torch.tensor([min(4., math.sqrt(largest/replay_bands[elo//200]))
                                           for _, elo in replay.records], dtype=torch.double)
            weights = torch.cat((.8*weights/weights.sum(), .2*replay_weights/replay_weights.sum()))
            records += replay.records
            train_data = ConcatDataset([train_data, replay])
            sampling += "_replay20"
    parent_sha256 = None
    previous_bounds = []
    if initialize_from:
        state = torch.load(initialize_from, map_location="cpu", weights_only=True)
        if state["config"] != asdict(cfg) or state["dataset"]["speed"] != settings["speed"]:
            raise ValueError("Checkpoint precedente incompatibile con rete o ritmo di gioco")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        start_step = state["step"]
        previous_bounds = state["rating_bounds"]
        parent_sha256 = fingerprint(initialize_from)
    if args.resume:
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if state["dataset_sha256"] != signature or state["config"] != asdict(cfg):
            raise ValueError("Checkpoint incompatibile con dataset o configurazione")
        if state["batch_size"] != args.batch_size:
            raise ValueError("Ripresa: mantenere la stessa batch size")
        if state.get("sampling") != sampling:
            raise ValueError("Campionamento cambiato: iniziare una nuova run")
        if (state.get("validation_sha256", state["dataset_sha256"]) != validation_signature
            or state.get("replay_sha256") != replay_signature):
            raise ValueError("Validation o memoria dei mesi precedenti cambiata")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        start_step = state["step"]
        parent_sha256 = state.get("parent_sha256")
        previous_bounds = state["rating_bounds"]
        sampler.set_state(state["sampler_rng"])
        torch.set_rng_state(state["cpu_rng"])
        if device.type == "cuda" and state["cuda_rng"] is not None:
            torch.cuda.set_rng_state(state["cuda_rng"])
    stop = False

    def on_stop(signum, frame):
        nonlocal stop
        stop = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, on_stop)
    ratings = [elo for _, elo in records] + previous_bounds
    rating_bounds = [min(ratings), max(ratings)]
    setup = dict(device=str(device), gpu=torch.cuda.get_device_name() if device.type == "cuda" else None,
                 parameters=sum(p.numel() for p in model.parameters()),
                 train_positions=len(train_data), validation_positions=len(validation),
                 rating_counts={str(k * 200): v for k, v in sorted(band_counts.items())},
                 preset=args.preset, batch_size=args.batch_size, sampling=sampling,
                 replay_positions=replay_count, parent_sha256=parent_sha256)
    print(json.dumps(setup), flush=True)
    t0, completed, step = time.monotonic(), 0, start_step

    def save():
        state = dict(config=asdict(cfg), model=model.state_dict(), optimizer=optimizer.state_dict(),
                     step=step, dataset=settings, dataset_sha256=signature, batch_size=args.batch_size,
                     rating_bounds=rating_bounds, cpu_rng=torch.get_rng_state(),
                     cuda_rng=torch.cuda.get_rng_state() if device.type == "cuda" else None,
                     sampler_rng=sampler.get_state(), setup=setup, sampling=sampling,
                     validation_sha256=validation_signature, replay_sha256=replay_signature,
                     parent_sha256=parent_sha256)
        temp = checkpoint.with_suffix(".tmp")
        torch.save(state, temp)
        temp.replace(checkpoint)

    with (run / "training.jsonl").open("a", encoding="utf-8") as log:
        for step in range(start_step + 1, start_step + args.steps + 1):
            model.train()
            indices = torch.multinomial(weights, args.batch_size, replacement=True, generator=sampler).tolist()
            batch = collate([train_data[i] for i in indices])
            optimizer.zero_grad(set_to_none=True)
            amp = torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" and torch.cuda.is_bf16_supported() else nullcontext()
            with amp:
                logits = model(*inputs(batch, device))
                loss = F.cross_entropy(logits.float(), batch["target"].to(device))
            if not torch.isfinite(loss):
                raise RuntimeError("Loss non finita: il checkpoint precedente è conservato")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            completed += 1
            if step % 10 == 0 or completed == 1:
                record = dict(step=step, loss=float(loss.detach()), seconds=time.monotonic() - t0)
                log.write(json.dumps(record) + "\n")
                log.flush()
                print(json.dumps(record), flush=True)
            if step % args.save_every == 0 or stop:
                save()
            if stop:
                break
    save()
    elapsed = time.monotonic() - t0
    metrics = evaluate(model, validation, device, args.batch_size)
    report = dict(**setup, step=step, additional_steps=completed, training_seconds=elapsed,
                  positions_per_second=completed * args.batch_size / elapsed,
                  gpu_peak_mib=torch.cuda.max_memory_allocated() / 1024**2 if device.type == "cuda" else None,
                  validation=metrics, dataset_sha256=signature, interrupted=stop,
                  validation_sha256=validation_signature, replay_sha256=replay_signature)
    (run / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", default="data/positions.sqlite")
    t.add_argument("--run", default="runs/tiny")
    t.add_argument("--preset", choices=["tiny", "small"], default="tiny")
    t.add_argument("--steps", type=int, default=100, help="Passi aggiuntivi, anche con --resume")
    t.add_argument("--batch-size", type=int, default=16)
    t.add_argument("--threads", type=int, default=4)
    t.add_argument("--lr", type=float, default=0.0003)
    t.add_argument("--seed", type=int, default=42)
    t.add_argument("--save-every", type=int, default=50)
    t.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    t.add_argument("--resume", action="store_true")
    t.add_argument("--initialize-from", help="Nuovo mese: conserva rete e ottimizzatore; nuovo campionamento")
    t.add_argument("--validation-data", help="Dataset di verifica fisso, separato dai mesi")
    t.add_argument("--replay-data", help="Memoria train dei mesi precedenti: 20%% dei campionamenti")
    p = sub.add_parser("predict")
    p.add_argument("--checkpoint", default="runs/tiny/last.pt")
    p.add_argument("--fen", required=True)
    p.add_argument("--elo", type=int, required=True)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.command == "train":
        if min(args.steps, args.batch_size, args.threads, args.save_every) < 1:
            parser.error("steps, batch-size, threads e save-every devono essere positivi")
        train(args)
    else:
        print(json.dumps(predict(args.checkpoint, args.fen, args.elo, args.device, args.top_k), indent=2))
