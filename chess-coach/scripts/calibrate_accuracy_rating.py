"""Build web/src/data/accuracy-rating.json: how likely each game accuracy is at each Lichess rating level.

Streams a monthly Lichess database dump (CC0) and keeps the rated rapid and classical games that carry the
server analysis ([%eval] after every move). Accuracy uses the same formula as web/src/accuracy.ts. The dump
(~30 GB) is never stored: reading stops once enough games are collected.

The app estimates a rating from one or more accuracies with a flat prior over 600–2600 (web/src/performance.ts,
mirrored by `estimate` here). Players set aside by name check that the 80% range holds their rating as often
as it claims; the likelihood is tempered by the factor that makes it so.
Usage: .venv/bin/python scripts/calibrate_accuracy_rating.py [--games 150000] [--month 2025-09] [--file dump.pgn.zst]
"""
import argparse
import io
import json
import math
import re
import statistics
import time
import urllib.request
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / 'web' / 'src' / 'data' / 'accuracy-rating.json'
URL = 'https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst'
MIN_MOVES = 10       # evaluated moves per side, as required by the app before showing an estimate
MIN_ESTIMATED = 480  # Lichess estimated duration (base + 40 × increment): rapid and classical only
INITIAL_CP = 15      # Lichess evaluates the starting position as +0.15 when computing accuracy
BANDS = list(range(600, 2601, 100))  # ratings outside are counted in the first or last level
ACCURACY_SIGMA = 3   # smoothing of the accuracy histograms, in accuracy points
BAND_SIGMA = 1       # smoothing across neighbouring levels, in levels
FLOOR = 1e-5         # no accuracy is impossible at any level
HOLDOUT = 5          # one player in HOLDOUT, by name, is kept out of the histograms for validation
TEMPERS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3)
HEADER = re.compile(r'^\[(\w+) "(.*)"\]$')
EVAL = re.compile(r'\[%eval ([^\]]+)\]')


def win_percent(cp=None, mate=None):
    """Lichess win percentage for White; mates count as certain results."""
    if mate:
        return 100.0 if mate == 'w' else 0.0
    cp = max(-1000, min(1000, cp or 0))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(before, after):
    raw = 103.1668100711649 * math.exp(-0.04354415386753951 * max(0, before - after)) - 3.166924740191411
    return max(0.0, min(100.0, raw + 1))


def game_accuracy(wins):
    """Per-side accuracy and move count from White win percentages after each ply, starting position first."""
    size = max(2, min(8, len(wins) // 10))
    windows = [wins[:size]] * max(0, size - 2) + [wins[i:i + size] for i in range(len(wins) - size + 1)]
    weights = [max(0.5, min(12, statistics.pstdev(w))) for w in windows]
    moves = {'w': [], 'b': []}
    for i in range(len(wins) - 1):
        color = 'w' if i % 2 == 0 else 'b'
        before, after = (wins[i], wins[i + 1]) if color == 'w' else (100 - wins[i], 100 - wins[i + 1])
        moves[color].append((move_accuracy(before, after), weights[i]))
    result = {}
    for color, items in moves.items():
        if not items:
            result[color] = (None, 0)
            continue
        weighted = sum(a * w for a, w in items) / sum(w for _, w in items)
        harmonic = len(items) / sum(1 / max(1, a) for a, _ in items)
        result[color] = ((weighted + harmonic) / 2, len(items))
    return result


def parse_eval(text):
    text = text.strip()
    if text.startswith('#'):
        return {'mate': 'w' if not text[1:].startswith('-') else 'b'}
    return {'cp': round(float(text) * 100)}


def games(lines):
    """Yield (headers, movetext) from PGN lines."""
    headers, moves = {}, []
    for line in lines:
        line = line.rstrip('\n')
        match = HEADER.match(line)
        if match:
            if moves:
                yield headers, ' '.join(moves)
                headers, moves = {}, []
            headers[match[1]] = match[2]
        elif line:
            moves.append(line)
    if headers:
        yield headers, ' '.join(moves)


def samples(headers, movetext):
    """(player, rating, accuracy) for each side of an eligible analysed game, else nothing."""
    if '[%eval' not in movetext or headers.get('Termination') not in ('Normal', 'Time forfeit'):
        return []
    if headers.get('Variant', 'Standard') != 'Standard' or 'FEN' in headers:
        return []
    base, _, increment = headers.get('TimeControl', '-').partition('+')
    if not base.isdigit() or int(base) + 40 * int(increment or 0) < MIN_ESTIMATED:
        return []
    comments = re.findall(r'\{([^}]*)\}', movetext)
    evals: list = [EVAL.search(c) for c in comments]
    # The mating move carries no evaluation: the last ply may go without, any other gap disqualifies the game.
    if evals and evals[-1] is None:
        evals = evals[:-1]
    if not evals or any(e is None for e in evals):
        return []
    accuracy = game_accuracy([win_percent(INITIAL_CP)] + [win_percent(**parse_eval(e[1])) for e in evals])
    result = []
    for color, name, rating in (('w', 'White', 'WhiteElo'), ('b', 'Black', 'BlackElo')):
        value, count = accuracy[color]
        if value is not None and count >= MIN_MOVES and headers.get(rating, '?').isdigit():
            result.append((headers.get(name, '?'), int(headers[rating]), value))
    return result


def band(rating):
    return min(len(BANDS) - 1, max(0, round((rating - BANDS[0]) / 100)))


def likelihood(points):
    """Smoothed probability of each whole accuracy point at each level, rows summing to 1."""
    counts = [[0.0] * 101 for _ in BANDS]
    for _, rating, accuracy in points:
        counts[band(rating)][round(accuracy)] += 1
    kernel = lambda d, s: math.exp(-d * d / (2 * s * s))  # noqa: E731
    by_accuracy = [[sum(row[j] * kernel(i - j, ACCURACY_SIGMA) for j in range(101)) for i in range(101)] for row in counts]
    rows = []
    for b in range(len(BANDS)):
        weights = [kernel(b - o, BAND_SIGMA) for o in range(len(BANDS))]
        row = [sum(w * by_accuracy[o][i] for o, w in enumerate(weights)) for i in range(101)]
        total = sum(row) or 1
        row = [max(FLOOR, v / total) for v in row]
        total = sum(row)
        rows.append([round(v / total, 7) for v in row])
    return rows


def estimate(rows, accuracies, temper=1.0):
    """Rating quantiles (10, 50, 90) from game accuracies, flat prior over the levels; each spans ±50."""
    def chance(row, accuracy):
        a = max(0.0, min(100.0, accuracy))
        i = min(99, math.floor(a))
        return row[i] + (row[i + 1] - row[i]) * (a - i)
    logs = [temper * sum(math.log(chance(row, a)) for a in accuracies) for row in rows]
    top = max(logs)
    weights = [math.exp(v - top) for v in logs]
    total = sum(weights)
    result = []
    for q in (0.1, 0.5, 0.9):
        cumulative, value = 0.0, BANDS[-1] + 50
        for level, weight in zip(BANDS, weights):
            share = weight / total
            if cumulative + share >= q:
                value = level - 50 + 100 * (q - cumulative) / share
                break
            cumulative += share
        result.append(min(BANDS[-1], max(BANDS[0], value)))
    return tuple(result)


def coverage(rows, players, count, temper):
    """Share of held-out players with `count` games whose mean rating falls in the 80% range, and its median width."""
    hits, widths = [], []
    for games_of in players.values():
        if len(games_of) < count:
            continue
        chosen = games_of[:count]
        low, _, high = estimate(rows, [a for _, a in chosen], temper)
        truth = min(BANDS[-1], max(BANDS[0], sum(r for r, _ in chosen) / count))
        hits.append(low <= truth <= high)
        widths.append(high - low)
    if not hits:
        return {'games': count, 'players': 0}
    return {'games': count, 'players': len(hits), 'coverage': round(sum(hits) / len(hits), 3), 'medianWidth': round(statistics.median(widths))}


def held_out(name):
    return zlib.crc32(name.encode()) % HOLDOUT == 0


def build(points):
    """Likelihood from most players, tempering and validation from the held-out ones."""
    rows = likelihood([p for p in points if not held_out(p[0])])
    players = defaultdict(list)
    for name, rating, accuracy in points:
        if held_out(name) and name != '?':
            players[name].append((rating, accuracy))
    reference = 10 if sum(len(g) >= 10 for g in players.values()) >= 30 else 5
    temper = min(TEMPERS, key=lambda t: (abs(coverage(rows, players, reference, t).get('coverage', 0.8) - 0.8), -t))
    return rows, temper, [coverage(rows, players, n, temper) for n in (1, 5, 10)]


def open_source(source):
    raw = urllib.request.urlopen(source, timeout=60) if source.startswith('https://') else open(source, 'rb')
    if source.endswith('.zst'):
        import zstandard  # type: ignore[import-not-found]
        raw = zstandard.ZstdDecompressor().stream_reader(raw)
    return io.TextIOWrapper(raw, encoding='utf-8', errors='replace')


def calibrate(source, wanted, target):
    points, kept, seen, started = [], 0, 0, time.time()
    for headers, movetext in games(open_source(source)):
        seen += 1
        found = samples(headers, movetext)
        if found:
            points.extend(found)
            kept += 1
            if kept % 10000 == 0:
                print(f'{kept} partite analizzate su {seen} lette ({time.time() - started:.0f} s)', flush=True)
            if kept >= wanted:
                break
    if not points:
        raise SystemExit('Nessuna partita utilizzabile nella sorgente')
    rows, temper, validation = build(points)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        'source': source.rsplit('/', 1)[-1], 'createdAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'games': kept, 'samples': len(points), 'minMoves': MIN_MOVES, 'minEstimatedSeconds': MIN_ESTIMATED,
        'bands': BANDS, 'temper': temper, 'validation': validation, 'likelihood': rows}, separators=(',', ':')) + '\n')
    print(f'{kept} partite, {len(points)} giocatori, attenuazione {temper} → {target}')
    for v in validation:
        print(v)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('--games', type=int, default=150000)
    parser.add_argument('--month', default='2025-09')
    parser.add_argument('--file', help='dump .pgn o .pgn.zst locale, al posto del download')
    parser.add_argument('--target', type=Path, default=TARGET)
    args = parser.parse_args()
    calibrate(args.file or URL.format(month=args.month), args.games, args.target)
