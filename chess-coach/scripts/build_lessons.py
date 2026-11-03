"""Check backend/data/logical_chess.json and store Stockfish's analysis of each lesson in it.

Each position is replayed from its moves and compared with the stored FEN; every listed move must be legal. Then
Stockfish, at a fixed depth, gives its best lines (MultiPV) and an evaluation of each move the lesson lists, from the
side to move. The book's idea and these numbers are shown apart in the app: they do not always agree.
The same is done for every move of the «Segui la partita» games (walks), with the moves each one accepts.
Usage: python scripts/build_lessons.py [--depth 22] [--walk-depth 20] [--only-walks]
Walk searches stop at the depth or after WALK_SECONDS, whichever comes first: the stored depth is the one reached.
"""
import argparse
import json
import sys
from pathlib import Path

import chess
import chess.engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.engine import stockfish_path  # noqa: E402
from backend.lessons import DATA, replay, validate, validate_walks, walk_step_moves  # noqa: E402

LINES = 5
WALK_SECONDS = 8


def score(info, board):
    value = info['score'].pov(board.turn)
    return {'cp': value.score(mate_score=100000), 'mate': value.mate()}


def analyse(engine, board, sans, depth, lines_count, seconds=None):
    # Near a forced mate Stockfish may never reach the depth: the walks also cap the time per search.
    limit = chess.engine.Limit(depth=depth, time=seconds)
    infos = engine.analyse(board, limit, multipv=lines_count)
    lines = [{'san': board.san(i['pv'][0]), **score(i, board), 'pv': [m.uci() for m in i['pv'][:6]]} for i in infos]
    moves = {}
    for san in sans:
        known = next((l for l in lines if l['san'] == san), None)
        if known is None:
            info = engine.analyse(board, limit, root_moves=[board.parse_san(san)])
            known = {'san': san, **score(info, board)}
        moves[san] = {'cp': known['cp'], 'mate': known['mate']}
    return {'depth': min(depth, infos[0].get('depth', depth)), 'lines': lines, 'moves': moves}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--depth', type=int, default=22)
    parser.add_argument('--walk-depth', type=int, default=20)
    parser.add_argument('--only-walks', action='store_true')
    args = parser.parse_args()
    data = json.loads(DATA.read_text(encoding='utf-8'))
    errors = validate(data, engine=False) + validate_walks(data, engine=False)
    if errors:
        sys.exit('\n'.join(errors))
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path())
    engine.configure({'Threads': 4, 'Hash': 256})
    try:
        for lesson in [] if args.only_walks else data['lessons']:
            lesson['engine'] = analyse(engine, replay(lesson['history']), lesson['moves'], args.depth, LINES)
            lines, moves = lesson['engine']['lines'], lesson['engine']['moves']
            print(lesson['id'], 'migliore', lines[0]['san'], lines[0]['cp'], '·',
                  ', '.join(f"{s} {m['cp']}" for s, m in moves.items()))
        lessons = {l['id']: l for l in data['lessons']}
        for walk in data.get('walks', []):
            board = chess.Board()
            for ply, entry in enumerate(walk['moves']):
                entry['engine'] = analyse(engine, board, walk_step_moves(walk, ply, lessons), args.walk_depth, 3, WALK_SECONDS)
                print(walk['id'], ply, entry['san'], entry['engine']['moves'][entry['san']], 'migliore', entry['engine']['lines'][0]['san'])
                board.push_san(entry['san'])
    finally:
        engine.quit()
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    errors = validate(data) + validate_walks(data)
    if errors:
        sys.exit('\n'.join(errors))


if __name__ == '__main__':
    main()
