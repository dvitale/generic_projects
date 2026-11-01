"""How many opening families Maia plays against itself in each move selection mode of Play.

Every game uses the same seeds across modes, as in Mobile Maia's study (mobilemaia.org/research), so the modes
differ only by their rule. The sharpened modes run with the current opening rule (backend/maia.py OPENING_MOVES and
OPENING) and with the previous one, «regola fino al 1/11» (temperature 1, top-p 0.9 up to move 8).
Families come from backend/openings.py.

Usage: python scripts/measure_opening_variety.py [games=300] [elo=1500] [plies=16]
"""
import collections
import os
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import maia as maia_module, openings  # noqa: E402
from backend.maia import maia  # noqa: E402

GAMES, ELO, PLIES = (int(a) for a in (sys.argv[1:] + ['300', '1500', '16'][len(sys.argv) - 1:])[:3])


def play(selection, rule):
    maia_module.OPENING_MOVES, maia_module.OPENING = rule
    boards = [chess.Board() for _ in range(GAMES)]
    for ply in range(PLIES):
        live = [b for b in boards if not b.is_game_over()]
        predictions = maia.predict_many([(b.fen(), ELO, ELO) for b in live])
        for game, (board, prediction) in enumerate(zip(live, predictions)):
            uci, _ = maia_module.choose(prediction['moves'], selection, board.fullmove_number, f'{game}:{ply}')
            board.push_uci(uci)
    found = [openings.classify(chess.STARTING_FEN, [m.uci() for m in b.move_stack]) for b in boards]
    families = collections.Counter(openings.family(f['name']) if f else '(nessuna)' for f in found)
    first = collections.Counter(b.move_stack[0].uci() for b in boards)
    return families, len({f['name'] for f in found if f}), first


if not maia.available():
    sys.exit('Maia non disponibile: scarica il modello con scripts/download_assets.py')
current, previous = (maia_module.OPENING_MOVES, maia_module.OPENING), (8, (1, 0.9))
runs = [(s, current, s) for s in maia_module.SELECTIONS]
runs += [(s, previous, s + ' (regola fino al 1/11)') for s, rule in maia_module.SELECTIONS.items() if rule[2]]
print(f'{GAMES} partite Maia {ELO} contro Maia {ELO}, prime {PLIES} semimosse; apertura delle modalità affinate: '
      f'fino alla mossa {current[0]} con {current[1]}')
print(f'{"modalità":44} famiglie  varianti  1.e4  1.d4  famiglia più frequente')
for selection, opening, label in runs:
    families, names, first = play(selection, opening)
    top, count = families.most_common(1)[0]
    print(f'{label:44} {len(families):8} {names:9} {first["e2e4"] / GAMES:5.0%} {first["d2d4"] / GAMES:5.0%}  {top} ({count / GAMES:.0%})')
sys.stdout.flush()
os._exit(0)  # The ONNX session's threads can keep the interpreter alive at exit.
