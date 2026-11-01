"""Opening names from the Lichess chess-openings catalogue (CC0), matched by position so transpositions count.

The catalogue lists named lines and the positions they pass through: the book ends at the last position of
the game found in it, a fixed and checkable rule. It is a catalogue of names, not a full opening book.
Regenerate the data with scripts/build_openings.py.
"""
from functools import lru_cache
from pathlib import Path

import chess

DATA = Path(__file__).parent / 'data' / 'openings.tsv'


@lru_cache(1)
def catalogue():
    """EPD -> (eco, name); positions passed through by a named line have empty names."""
    lines = [line for line in DATA.read_text().splitlines() if not line.startswith('#')][1:]
    return {epd: (eco, name) for eco, name, epd, _ in (line.split('\t') for line in lines)}


def classify(initial_fen, moves):
    """Every named position the game reaches, by ply; the opening is the last one, where the book ends."""
    names, board = catalogue(), chess.Board(initial_fen)
    found, book = [], 0
    for ply in range(len(moves) + 1):
        if ply:
            board.push_uci(moves[ply - 1])
        if board.epd() in names:
            eco, name = names[board.epd()]
            book = ply
            if name:
                found.append({'ply': ply, 'eco': eco, 'name': name})
    if not found:
        return None
    return {**found[-1], 'bookPlies': book, 'positions': found}


# Repertoire: own decisions within AFTER_BOOK plies of the book exit are the ones the theory no longer covers.
# A family needs WATCH_MIN games before it is judged; it is weak with a score under WEAK_SCORE or a share of
# sound decisions after the book WEAK_DROP below the player's own share across all families.
AFTER_BOOK, WATCH_MIN, WEAK_SCORE, WEAK_DROP = 20, 3, 0.40, 0.20
SOUND, ERROR = 80, 180


def family(name):
    return name.split(':')[0]


def exit_fen(game):
    board = chess.Board()
    for uci in game['moves'][:game['opening']['bookPlies']]:
        board.push_uci(uci)
    return board.fen()


def repertoire(games):
    """games: dicts with id, number, title, color, opening (classify), moves from the standard start, decisions
    (player's, analysed) and score (1, ½, 0 or None while unfinished), newest first. Families by colour, most played first."""
    groups = {}
    for g in games:
        if g['opening']:
            groups.setdefault((g['color'], family(g['opening']['name'])), []).append(g)
    def after(g):
        book = g['opening']['bookPlies']
        return [d for d in g['decisions'] if book <= d['ply'] < book + AFTER_BOOK]
    def share(items):
        decisions = [d for g in items for d in after(g)]
        return sum(d['loss'] < SOUND for d in decisions) / len(decisions) if decisions else None
    overall = share([g for items in groups.values() for g in items])
    result = []
    for (color, name), items in groups.items():
        scores = [g['score'] for g in items if g['score'] is not None]
        decisions = [d for g in items for d in after(g)]
        # Own moves from the book exit to the first inaccuracy or error, for the games that have one.
        first = [next(i for i, d in enumerate(sorted(after(g), key=lambda d: d['ply']), 1) if d['loss'] >= SOUND)
                 for g in items if any(d['loss'] >= SOUND for d in after(g))]
        sound = share(items)
        score = sum(scores) / len(scores) if scores else None
        weak = len(items) >= WATCH_MIN and (score is not None and score < WEAK_SCORE
                                            or sound is not None and overall is not None and sound <= overall - WEAK_DROP)
        latest = next((g for g in items if g['opening']['bookPlies'] < len(g['moves'])), None)
        ecos = [g['opening']['eco'] for g in items]
        result.append({'color': color, 'family': name, 'eco': max(set(ecos), key=ecos.count), 'games': len(items),
                       'finished': len(scores), 'score': score, 'analysed': sum(bool(g['decisions']) for g in items),
                       'decisions': len(decisions), 'sound': sound, 'errors': sum(d['loss'] >= ERROR for d in decisions),
                       'firstMistake': sum(first) / len(first) if first else None,
                       'status': 'weak' if weak else 'watch' if len(items) < WATCH_MIN else 'ok',
                       'variations': sorted({g['opening']['name'] for g in items}),
                       'exit': latest and {'gameId': latest['id'], 'number': latest['number'], 'title': latest['title'],
                                           'ply': latest['opening']['bookPlies'], 'fen': exit_fen(latest)}})
    result.sort(key=lambda r: (-r['games'], r['color'], r['family']))
    return {'families': result, 'overallSound': overall,
            'rules': {'afterBook': AFTER_BOOK, 'watch': WATCH_MIN, 'weakScore': WEAK_SCORE, 'weakDrop': WEAK_DROP}}
