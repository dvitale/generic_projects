"""Regenerate backend/data/openings.tsv from the Lichess chess-openings dataset (CC0) at a pinned commit.

Each named line is replayed with python-chess and stored with its final EPD, so the backend matches
positions (transpositions included) without parsing SAN at startup. The positions a line passes through
without a name of their own are stored too, with empty eco and name: they are still opening theory.
Usage: python scripts/build_openings.py
"""
import io
import urllib.request
from pathlib import Path

import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '712a58be746c143f4ab935b68acc50f4bac813eb'
SOURCE = f'https://raw.githubusercontent.com/lichess-org/chess-openings/{COMMIT}/{{}}.tsv'
TARGET = ROOT / 'backend/data/openings.tsv'

named, passed = {}, {}
for volume in 'abcde':
    lines = urllib.request.urlopen(SOURCE.format(volume), timeout=60).read().decode().splitlines()
    for line in lines[1:]:
        eco, name, pgn = line.split('\t')
        board = chess.Board()
        for move in chess.pgn.read_game(io.StringIO(pgn)).mainline_moves():
            board.push(move)
            passed.setdefault(board.epd(), len(board.move_stack))
        # The first name listed for a position wins, as in the Lichess sources' order.
        named.setdefault(board.epd(), (eco, name, len(board.move_stack)))
rows = [f'{eco}\t{name}\t{epd}\t{plies}' for epd, (eco, name, plies) in named.items()]
rows += [f'\t\t{epd}\t{plies}' for epd, plies in passed.items() if epd not in named]
TARGET.write_text(f'# lichess-org/chess-openings {COMMIT}, CC0 1.0\neco\tname\tepd\tplies\n' + '\n'.join(rows) + '\n')
print(len(named), 'posizioni con un nome e', len(rows) - len(named), 'intermedie in', TARGET.relative_to(ROOT))
