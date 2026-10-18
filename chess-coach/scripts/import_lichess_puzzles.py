"""Build data/lichess_puzzles.sqlite3: a filtered, rating-stratified sample of the Lichess puzzle database (CC0).

The 300 MB compressed CSV is streamed and never stored. Reading stops as soon as every rating band is full.
Usage: .venv/bin/python scripts/import_lichess_puzzles.py [--per-band 3000] [--file lichess_db_puzzle.csv.zst]
"""
import argparse
import csv
import io
import os
import sqlite3
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.problems import BANDS, PUZZLES_FILE, band_of  # noqa: E402

URL = 'https://database.lichess.org/lichess_db_puzzle.csv.zst'
COLUMNS = ['PuzzleId', 'FEN', 'Moves', 'Rating', 'RatingDeviation', 'Popularity', 'NbPlays', 'Themes', 'GameUrl', 'OpeningTags']


def rows(source):
    """Yield CSV records from a URL or a local .csv/.csv.zst file, skipping the header when present."""
    raw = urllib.request.urlopen(source, timeout=60) if source.startswith('https://') else open(source, 'rb')
    if source.endswith('.zst'):
        import zstandard
        raw = zstandard.ZstdDecompressor().stream_reader(raw)
    for record in csv.reader(io.TextIOWrapper(raw, encoding='utf-8', newline='')):
        if record and record[0] != 'PuzzleId':
            yield record


def build(source, target, per_band, min_popularity, min_plays, max_rd):
    temporary = target.with_suffix('.tmp')
    temporary.unlink(missing_ok=True)
    con = sqlite3.connect(temporary)
    con.executescript('''
    CREATE TABLE puzzles(id TEXT PRIMARY KEY, fen TEXT NOT NULL, moves TEXT NOT NULL, rating INTEGER NOT NULL,
      rd INTEGER NOT NULL, popularity INTEGER NOT NULL, plays INTEGER NOT NULL, themes TEXT NOT NULL,
      game_url TEXT NOT NULL, opening TEXT NOT NULL, band INTEGER NOT NULL);
    CREATE TABLE themes(name TEXT PRIMARY KEY, count INTEGER NOT NULL);
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    filled, themes, read, started = Counter(), Counter(), 0, time.monotonic()
    for record in rows(source):
        read += 1
        if read % 500_000 == 0:
            print(f'  {read:,} righe lette, {sum(filled.values()):,} problemi tenuti ({time.monotonic() - started:.0f} s)', flush=True)
        puzzle_id, fen, moves, rating, rd, popularity, plays, tags, url, opening = (record + [''] * 10)[:10]
        rating, rd, popularity, plays = int(rating), int(rd), int(popularity), int(plays)
        band = band_of(rating)
        # Reliable ratings and well-liked problems only: few plays or a wide deviation mean an uncertain difficulty.
        if band is None or filled[band] >= per_band or popularity < min_popularity or plays < min_plays or rd > max_rd:
            continue
        con.execute('INSERT INTO puzzles VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (puzzle_id, fen, moves, rating, rd, popularity, plays, f' {tags} ', url, opening, band))
        filled[band] += 1
        themes.update(tags.split())
        if all(filled[i] >= per_band for i in range(len(BANDS))):
            break
    con.executemany('INSERT INTO themes VALUES(?,?)', themes.items())
    con.executemany('INSERT INTO meta VALUES(?,?)', [
        ('source', source), ('source_rows', str(read)), ('imported_at', datetime.now(timezone.utc).isoformat()),
        ('filters', f'popularity>={min_popularity} plays>={min_plays} rd<={max_rd} per_band={per_band}')])
    con.execute('CREATE INDEX puzzles_band ON puzzles(band, rating)')
    con.execute('CREATE INDEX puzzles_rating ON puzzles(rating)')
    con.commit()
    con.execute('VACUUM')
    con.close()
    # Atomic swap: a running server never sees a half-written file.
    os.replace(temporary, target)
    return filled, read


def main():
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('--file', help='CSV locale (.csv o .csv.zst) al posto del download')
    parser.add_argument('--per-band', type=int, default=3000, help='problemi per fascia di rating (default 3000)')
    parser.add_argument('--min-popularity', type=int, default=80, help='popolarità minima, da -100 a 100 (default 80)')
    parser.add_argument('--min-plays', type=int, default=200, help='tentativi minimi su Lichess (default 200)')
    parser.add_argument('--max-rd', type=int, default=90, help='deviazione massima del rating (default 90)')
    parser.add_argument('--data', default=os.environ.get('CHESS_COACH_DATA', str(ROOT / 'data')), help='cartella dati')
    args = parser.parse_args()
    target = Path(args.data) / PUZZLES_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    source = args.file or URL
    print(f'Importo da {source} in {target}', flush=True)
    filled, read = build(source, target, args.per_band, args.min_popularity, args.min_plays, args.max_rd)
    for i, (_, _, label) in enumerate(BANDS):
        print(f'  {label:>12}: {filled[i]:>6}')
    print(f'Totale {sum(filled.values()):,} problemi da {read:,} righe lette ({target.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
