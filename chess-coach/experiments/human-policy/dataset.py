"""Bounded public-data download and deterministic game-disjoint PGN extraction."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import random
import sqlite3
import struct
import urllib.request

import chess
import chess.pgn
import zstandard

URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2026-09.pgn.zst"


class CompleteGameBuilder(chess.pgn.GameBuilder):
    def visit_result(self, result):
        self.game.has_movetext_result = True
        super().visit_result(result)


def download(path, mib=32):
    if not 1 <= mib <= 1024:
        raise ValueError("Il campione deve essere fra 1 e 1024 MiB")
    path = Path(path)
    meta = path.with_suffix(path.suffix + ".json")
    if path.exists():
        raise FileExistsError(f"{path} esiste: riutilizzarlo o scegliere un altro percorso")
    path.parent.mkdir(parents=True, exist_ok=True)
    limit, count, digest = mib * 1024**2, 0, hashlib.sha256()
    req = urllib.request.Request(URL, headers={"Range": f"bytes=0-{limit - 1}",
                                               "User-Agent": "SparringMateResearch/0.1"})
    part = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(req, timeout=60) as response, part.open("wb") as out:
        while count < limit:
            chunk = response.read(min(1024**2, limit - count))
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            count += len(chunk)
    part.replace(path)
    metadata = dict(source=URL, bytes=count, sha256=digest.hexdigest(),
                    license="CC0", sample="prefix, NOT representative of entire month")
    meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


def speed_of(control):
    try:
        base, increment = map(int, control.split("+"))
        if base < 0 or increment < 0:
            return None
        seconds = base + 40 * increment
        return "bullet" if seconds < 180 else "blitz" if seconds < 480 else "rapid" if seconds < 1500 else "classical"
    except (ValueError, AttributeError):
        return None


def game_key(game):
    site = game.headers.get("Site", "")
    if site.startswith("https://lichess.org/") and len(site.rstrip("/").split("/")[-1]) >= 8:
        identity = site.rstrip("/").split("/")[-1][:8]
    else:
        identity = str(game.headers) + " ".join(m.uci() for m in game.mainline_moves())
    return hashlib.sha256(identity.encode()).hexdigest()


def split_for(key):
    bucket = int(key[:8], 16) % 100
    return "test" if bucket < 10 else "validation" if bucket < 20 else "train"


def extract(path, output, max_games=5000, positions_per_game=16, speed="rapid", low=600, high=2600):
    from features import encode, move_id

    if max_games < 1 or positions_per_game < 1 or low > high:
        raise ValueError("Limiti del campione non validi")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS positions(
      id INTEGER PRIMARY KEY, game_id TEXT NOT NULL, ply INTEGER NOT NULL,
      split TEXT NOT NULL, elo INTEGER NOT NULL, fen TEXT NOT NULL,
      pieces BLOB NOT NULL, ep BLOB NOT NULL, context BLOB NOT NULL,
      legal BLOB NOT NULL, target INTEGER NOT NULL, UNIQUE(game_id, ply));
    CREATE INDEX IF NOT EXISTS positions_split ON positions(split);
    """)
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024**2), b""):
            digest.update(chunk)
    settings = dict(schema=1, source_sha256=digest.hexdigest(), speed=speed,
                    low=low, high=high, positions_per_game=positions_per_game)
    old = db.execute("SELECT value FROM meta WHERE key='settings'").fetchone()
    if old and json.loads(old[0]) != settings:
        raise ValueError("Dataset già presente con filtri o sorgente diversi")
    db.execute("INSERT OR REPLACE INTO meta VALUES('settings', ?)", (json.dumps(settings),))
    db.commit()
    stats = Counter()
    opener = zstandard.ZstdDecompressor().stream_reader
    try:
        with Path(path).open("rb") as raw:
            stream = opener(raw) if str(path).endswith(".zst") else raw
            with io.TextIOWrapper(stream, encoding="utf-8") as text:
                for _ in range(max_games):
                    game = chess.pgn.read_game(text, Visitor=CompleteGameBuilder)
                    if game is None:
                        break
                    stats["scanned"] += 1
                    if (not getattr(game, "has_movetext_result", False) or game.errors
                        or game.headers.get("Result") not in ("1-0", "0-1", "1/2-1/2")):
                        stats["incomplete_or_invalid"] += 1
                        continue
                    h = game.headers
                    if (not h.get("Event", "").startswith("Rated ")
                        or h.get("Variant", "Standard") != "Standard"
                        or "BOT" in (h.get("WhiteTitle"), h.get("BlackTitle"))
                        or speed_of(h.get("TimeControl")) != speed):
                        stats["filtered"] += 1
                        continue
                    key = game_key(game)
                    if db.execute("SELECT 1 FROM games WHERE id=?", (key,)).fetchone():
                        stats["already_processed"] += 1
                        continue
                    board, rows = game.board(), []
                    if not board.is_valid():
                        stats["invalid_start"] += 1
                        continue
                    for ply, move in enumerate(game.mainline_moves()):
                        legal_moves = list(board.legal_moves)
                        if move not in legal_moves:
                            raise ValueError("Mossa illegale dopo parsing")
                        rating_str = h.get("WhiteElo" if board.turn else "BlackElo", "")
                        if rating_str.isdigit() and low <= int(rating_str) <= high:
                            rating = int(rating_str)
                            pieces, ep, context = encode(board, rating)
                            ids = [move_id(m) for m in legal_moves]
                            rows.append((key, ply, split_for(key), rating, board.fen(en_passant="fen"),
                                         bytes(pieces), bytes(ep), struct.pack("<8f", *context),
                                         struct.pack(f"<{len(ids)}H", *ids), ids.index(move_id(move))))
                        board.push(move)
                    rng = random.Random(key)
                    selected = rng.sample(rows, min(len(rows), positions_per_game))
                    # A single transaction makes re-running safe after interruption.
                    with db:
                        db.execute("INSERT INTO games VALUES(?)", (key,))
                        db.executemany("""INSERT INTO positions(
                          game_id,ply,split,elo,fen,pieces,ep,context,legal,target
                        ) VALUES(?,?,?,?,?,?,?,?,?,?)""", selected)
                    stats["accepted_games"] += 1
                    stats["new_positions"] += len(selected)
    except zstandard.ZstdError:
        # A bounded compressed prefix may stop in the middle of a frame.
        stats["compressed_prefix_end"] += 1
    finally:
        totals = db.execute("SELECT split, (elo/200)*200, count(*) FROM positions GROUP BY 1,2").fetchall()
        report = dict(settings=settings, this_run=dict(stats),
                      counts=[dict(split=s, rating_bin=b, positions=n) for s, b, n in totals],
                      limitation="Prefix sample; game-disjoint split, NOT temporal or player-disjoint",
                      provisional_ratings="Not reliably identifiable from standard dump; not filtered")
        output.with_suffix(".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        db.close()
    print(json.dumps(report, indent=2))
    return report


class Positions:
    def __init__(self, path, split):
        self.db = sqlite3.connect(path)
        self.records = self.db.execute("SELECT id,elo FROM positions WHERE split=? ORDER BY id", (split,)).fetchall()

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        row = self.db.execute("SELECT pieces,ep,context,legal,target,elo FROM positions WHERE id=?",
                              (self.records[index][0],)).fetchone()
        pieces, ep, context, legal, target, elo = row
        return dict(pieces=list(pieces), ep=list(ep), context=list(struct.unpack("<8f", context)),
                    legal=list(struct.unpack(f"<{len(legal)//2}H", legal)), target=target, elo=elo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download")
    dl.add_argument("--output", default="data/lichess-prefix.pgn.zst")
    dl.add_argument("--mib", type=int, default=32)
    prep = sub.add_parser("prepare")
    prep.add_argument("--input", default="data/lichess-prefix.pgn.zst")
    prep.add_argument("--output", default="data/positions.sqlite")
    prep.add_argument("--max-games", type=int, default=5000, help="Totale partite da scorrere, incluse quelle già lette")
    prep.add_argument("--positions-per-game", type=int, default=16)
    prep.add_argument("--speed", choices=["rapid", "blitz", "classical", "bullet"], default="rapid")
    prep.add_argument("--low", type=int, default=600)
    prep.add_argument("--high", type=int, default=2600)
    args = parser.parse_args()
    if args.command == "download":
        download(args.output, args.mib)
    else:
        extract(args.input, args.output, args.max_games, args.positions_per_game, args.speed, args.low, args.high)
