"""Rebuild the main line of each game in a scanned chess book (OCR text with garbled figurines), as a starting point
for the lessons in backend/data/logical_chess.json.

The OCR reads the piece figurines badly ('lDf3', 'tt:Jf3', "'ii'e7"...), so a token is never parsed as SAN: python-chess
picks the one legal move whose destination square, piece kind and capture match it. Figurine prefixes are learned
from the moves that could only be one piece, over a few passes. A game stops at the first move that stays ambiguous
or unreadable; the stops are listed as flags. The result is a draft, not a source: check every position against the
book's diagram before using it (see docs/lezioni-libro.md) — a wrong piece can still pass, e.g. Rd8 for Nd8.
Main-line moves are the short lines that start with the expected move number; variations inside the prose are skipped.

Needs PyMuPDF, not in the project requirements: pip install --target <scratch dir> pymupdf, then PYTHONPATH=<that dir>.
Usage: python scripts/extract_book_games.py book.pdf out_dir
Writes out_dir/book.txt (text by page) and out_dir/games.json (per game: header, moves with SAN, UCI, printed page,
OCR token, diagram mark, and flags).
"""
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import chess

SQUARE = re.compile(r'[a-h][1-8]')
MAIN = re.compile(r'^(\d+(?: \d+(?= ))?)\s*(\.\.\.)?\s*(\S+)(?:\s+(\S+))?\s*(\(D\))?$')
PASSES = 4
# Hand-collected OCR shapes of the figurines in the Batsford algebraic edition.
SHAPES = [('N', r'li:J|i:J|ltJ|lt\)|li\)|lD|tL|lb|lt|liJ|ll\)|t2l|tt:J|l2J|CiJ|llJ|lLl|ttJ|tDJ|t\[J|lll|lbl'),
          ('Q', r"YJ|^Y|'i|1i|'t|'W|'f|'V|W|'ii|'@|\"i"),
          ('K', r'\.\.ti|r:b|@|<;t|<t|\bc;t|\*|Wi|<it|ri;|c\;i|\.Ji'),
          ('R', r':|U|l%|ll|:t|l::|n|\.l|E|%'),
          ('B', r'\.\.t|i\.|^k|^3|\.i|ii\.|il\.|\.t|ill|i\b|^\.')]


def page_lines(text):
    """(printed page, line) pairs; the OCR's dot variants of '...' are normalised."""
    pages, lines = re.split(r'\n=====PAGE (\d+)=====\n', text), []
    for i in range(1, len(pages), 2):
        for line in pages[i + 1].split('\n'):
            line = line.replace('…', '...').strip()
            line = re.sub(r'^([\d ]*\d)?\s*[.•]\s?[.•]\s?[.•]?(?=\s|$|[^.•])', lambda m: (m.group(1) or '') + ' ... ', line).strip()
            # In this edition the PDF page index plus one is the printed page number.
            lines.append((int(pages[i]) + 1, re.sub(r'\s+', ' ', line)))
    return lines


def guess(token):
    if re.match(r'^(0-0|O-O)', token):
        return 'castle'
    if re.match(r'^[a-h](x|[1-8])', token):
        return 'P'
    return next((piece for piece, shape in SHAPES if re.search(shape, token)), None)


def clean(token):
    token = re.sub(r'[!?+#]+$|\(D\)', '', token.replace('’', "'").replace('‘', "'")).strip()
    token = token.replace('t"', 'f').replace('\\', '')
    token = re.sub(r'([a-h])[Ss]$', r'\g<1>5', token)
    token = re.sub(r'([a-h])[lI]$', r'\g<1>1', token)
    return re.sub(r'([a-h])B$', r'\g<1>8', token)


def prefix(token, destination):
    return re.sub(r'x$', '', token[:token.rfind(destination)])[:3]


def resolve(board, raw, stats):
    """Legal moves matching an OCR token (one when resolved) and the guessed piece."""
    token, legal = clean(raw), list(board.legal_moves)
    kind = guess(token)
    if kind == 'castle':
        long = token.count('0') + token.count('O') >= 3
        return [m for m in legal if board.is_castling(m) and (chess.square_file(m.to_square) == 2) == long], kind
    squares = SQUARE.findall(token)
    destination = squares[-1] if squares else None
    found = [m for m in legal if destination and chess.square_name(m.to_square) == destination]
    if kind:
        found = [m for m in found if board.piece_type_at(m.from_square) == 'PNBRQK'.index(kind) + 1] or found
    if not re.match(r'^[a-h]', token):
        found = [m for m in found if board.piece_type_at(m.from_square) != chess.PAWN] or found
    if re.match(r'^[a-h][x1-8]', token):
        found = [m for m in found if board.piece_type_at(m.from_square) == chess.PAWN] or found
    if len(found) > 1 and stats:
        start = prefix(token, destination)
        def score(m):
            piece = chess.piece_symbol(board.piece_type_at(m.from_square)).upper()
            return sum(stats.get((start[:n], piece), 0) for n in (1, 2, 3))
        ranked = sorted(found, key=score, reverse=True)
        if score(ranked[0]) >= 2 * max(1, score(ranked[1])):
            found = ranked[:1]
    if not found:
        # A misread destination (t3 for f3): the closest square, only when one move is clearly closest.
        scored = sorted(((difflib.SequenceMatcher(None, token[-2:], chess.square_name(m.to_square)).ratio(), m) for m in legal),
                        key=lambda x: -x[0])
        if kind:
            scored = [x for x in scored if board.piece_type_at(x[1].from_square) == 'PNBRQK'.index(kind) + 1]
        if scored and scored[0][0] >= 0.5 and (len(scored) == 1 or scored[1][0] < scored[0][0]):
            return [scored[0][1]], 'fuzzy'
    if len(found) > 1 and destination:
        before = token[:token.rfind(destination)][-2:]
        narrowed = [m for m in found if chess.square_name(m.from_square)[0] in before or chess.square_name(m.from_square)[1] in before]
        if len(narrowed) == 1:
            found = narrowed
    if len(found) > 1 and 'x' in token:
        found = [m for m in found if board.is_capture(m)] or found
    if len(found) > 1:
        found = [m for m in found if m.promotion in (None, chess.QUEEN)]
    return found, kind


def blocks(lines, start, end):
    """Lines of a game, with a lone move number (and '...') joined to the move on the next line."""
    i = start
    while i < end:
        page, line = lines[i]
        if re.match(r'^\d[\d ]{0,3}( \.\.\.)?$', line) and i + 1 < end:
            j = i + 1
            while j < end and lines[j][1] == '...' and '...' not in line:
                line += ' ...'
                j += 1
            if j < end:
                yield page, f'{line} {lines[j][1]}', i
                i = j + 1
                continue
        yield page, line, i
        i += 1


def rebuild(lines, stats):
    starts = [i for i, (_, line) in enumerate(lines) if re.match(r'^Game \d[\d ]*$', line)]
    games = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        board, moves, flags = chess.Board(), [], []
        for page, line, index in blocks(lines, start + 4, end):
            m = MAIN.match(line)
            if not m or int(m.group(1).replace(' ', '')) != board.fullmove_number or (m.group(2) and board.turn == chess.WHITE):
                continue
            tokens = [m.group(3)] + ([m.group(4)] if m.group(4) and m.group(4) != '(D)' and not re.match(r'^[!?]+$', m.group(4)) else [])
            for token in tokens:
                found, kind = resolve(board, token, stats)
                if len(found) != 1:
                    flags.append({'move': board.fullmove_number, 'token': token, 'candidates': [board.san(c) for c in found], 'page': page})
                    break
                move = found[0]
                entry = {'san': board.san(move), 'uci': move.uci(), 'page': page, 'token': token, 'line': index,
                         'diagram': '(D)' in line, 'guess': kind}
                if kind != 'castle' and board.piece_type_at(move.from_square) != chess.PAWN and chess.square_name(move.to_square) in clean(token):
                    entry['prefix'] = prefix(clean(token), chess.square_name(move.to_square))
                moves.append(entry)
                board.push(move)
        games.append({'game': re.sub(r'\s', '', lines[start][1][5:]), 'players': lines[start + 1][1], 'event': lines[start + 2][1],
                      'opening': lines[start + 3][1], 'moves': moves, 'flags': flags, 'fen': board.fen()})
    return games


def learn(games):
    stats = Counter()
    for game in games:
        board = chess.Board()
        for entry in game['moves']:
            move = chess.Move.from_uci(entry['uci'])
            if 'prefix' in entry:
                piece = chess.piece_symbol(board.piece_type_at(move.from_square)).upper()
                for n in (1, 2, 3):
                    stats[(entry['prefix'][:n], piece)] += 1
            board.push(move)
    return stats


def main():
    import pymupdf
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    text = ''.join(f'\n=====PAGE {i}=====\n' + page.get_text() for i, page in enumerate(pymupdf.open(source)))
    (out / 'book.txt').write_text(text, encoding='utf-8')
    lines = page_lines(text)
    games = rebuild(lines, {})
    for _ in range(PASSES - 1):
        games = rebuild(lines, learn(games))
    (out / 'games.json').write_text(json.dumps(games, ensure_ascii=False, indent=1), encoding='utf-8')
    for game in games:
        print(f"{game['game']:>3} {game['players']:<35} {len(game['moves']):>3} semimosse",
              f"· fermo a {game['flags'][0]}" if game['flags'] else '')


if __name__ == '__main__':
    main()
