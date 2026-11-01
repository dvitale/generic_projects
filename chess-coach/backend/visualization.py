"""Visualization training: a position from the player's games, a few of its moves to play only in the head, then a
question on the final position that python-chess answers exactly (Queen paper, arXiv 2610.03695, appendix D).

The answer stays on the server until the player chooses. The length of the line adapts: STEP_UP right answers in a
row at the current length add a half-move, a wrong one removes it, between MIN_PLIES and MAX_PLIES."""
import json
import random
import uuid

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .explain import NAMES, label

MIN_PLIES, MAX_PLIES, START_PLIES, STEP_UP = 1, 8, 2, 3
# Positions start after the opening, where the moves are the player's own and not memorised theory.
FIRST_PLY = 16
RECENT = 20
SIDES = {chess.WHITE: ('bianco', 'bianca', 'il Bianco', 'bianchi'), chess.BLACK: ('nero', 'nera', 'il Nero', 'neri')}


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS visualization_questions(
      id TEXT PRIMARY KEY, created_at TEXT NOT NULL, game_id TEXT NOT NULL, ply INTEGER NOT NULL, fen TEXT NOT NULL,
      moves TEXT NOT NULL, plies INTEGER NOT NULL, kind TEXT NOT NULL, question TEXT NOT NULL, options TEXT NOT NULL,
      answer INTEGER NOT NULL, explanation TEXT NOT NULL, final_fen TEXT NOT NULL, choice INTEGER, success INTEGER,
      answered_at TEXT);
    ''')


def level(answers):
    """Line length for the next question, replayed from the answers in order: (plies, success) pairs."""
    plies, streak = START_PLIES, 0
    for length, success in answers:
        if success and length >= plies:
            streak += 1
            if streak == STEP_UP:
                plies, streak = min(MAX_PLIES, plies + 1), 0
        elif not success and length <= plies:
            plies, streak = max(MIN_PLIES, plies - 1), 0
    return plies


def named(piece):
    name, _, gender = NAMES[piece.piece_type]
    return f"{'la' if gender == 'f' else 'il'} {name} {SIDES[piece.color][1 if gender == 'f' else 0]}"


def long(board, move):
    """Long algebraic notation, also for moves that are not legal: Re1-d1, e2-e4."""
    piece = board.piece_at(move.from_square).symbol().upper()
    return f"{'' if piece == 'P' else piece}{chess.square_name(move.from_square)}-{chess.square_name(move.to_square)}"


def line_text(board, moves):
    cursor, parts = board.copy(stack=False), []
    for i, move in enumerate(moves):
        parts.append(label(cursor, move) if i == 0 or cursor.turn else cursor.san(move))
        cursor.push(move)
    return ' '.join(parts)


def question(start, moves, rng):
    """(kind, question, options, answer index, explanation) about the position after `moves`."""
    end = start.copy(stack=False)
    for move in moves:
        end.push(move)
    side = SIDES[end.turn][2]
    asks = ['piece', 'piece', 'attackers', 'captures', 'check']
    if end.is_check():
        asks += ['mate', 'escape', 'escape']
    kind = rng.choice(asks)
    if kind == 'escape':
        illegal = [m for m in end.pseudo_legal_moves if not end.is_legal(m)]
        if len(illegal) >= 2:
            right = rng.choice(list(end.legal_moves))
            options = [right] + rng.sample(illegal, min(3, len(illegal)))
            rng.shuffle(options)
            # One notation for all, so the legal move does not stand out by its SAN.
            return ('escape', f"{side.capitalize()} è sotto scacco. Quale di queste mosse è legale?", [long(end, m) for m in options],
                    options.index(right), f"È legale {end.san(right)}; le altre lasciano il re sotto scacco.")
        kind = 'mate'
    if kind == 'mate':
        mate = end.is_checkmate()
        checking = [named(end.piece_at(s)) + ' in ' + chess.square_name(s) for s in end.checkers()]
        return ('mate', f"{side.capitalize()} è sotto scacco ({', '.join(checking)}). È scacco matto?", ['Sì', 'No'], 0 if mate else 1,
                'Sì: non ci sono mosse legali.' if mate else f"No: per esempio {end.san(next(iter(end.legal_moves)))}.")
    if kind == 'check':
        checking = [named(end.piece_at(s)) + ' in ' + chess.square_name(s) for s in end.checkers()]
        return ('check', f"Alla fine della linea {side} è sotto scacco?", ['Sì', 'No'], 0 if checking else 1,
                f"Sì: dà scacco {', '.join(checking)}." if checking else 'No: nessun pezzo attacca il re.')
    if kind == 'captures':
        count = sum(end.is_capture(m) for m in end.legal_moves)
        options = ['Nessuna', '1', '2', '3 o più']
        captures = [end.san(m) for m in end.legal_moves if end.is_capture(m)]
        return ('captures', f"Quante catture legali ha {side} alla fine della linea?", options, min(count, 3),
                f"{len(captures)}: {', '.join(captures)}." if captures else 'Nessuna.')
    if kind == 'attackers':
        targets = [m.to_square for m in moves if end.piece_at(m.to_square)]
        if targets:
            square = rng.choice(targets)
            piece = end.piece_at(square)
            attackers = end.attackers(not piece.color, square)
            options = ['Nessuno', '1', '2', '3 o più']
            listed = ', '.join(named(end.piece_at(s)) + ' in ' + chess.square_name(s) for s in attackers)
            return ('attackers', f"Quanti pezzi {SIDES[not piece.color][3]} attaccano {named(piece)} in "
                                 f"{chess.square_name(square)}?", options, min(len(attackers), 3),
                    f"{len(attackers) or 'Nessuno'}{': ' + listed if listed else ''}.")
    # What stands on a square the line touched: a landing square, or one a piece left.
    squares = list(dict.fromkeys([m.to_square for m in moves] + [m.from_square for m in moves]))
    square = rng.choice(squares[:4])
    present = end.piece_at(square)
    seen = [start.piece_at(s) for s in squares if start.piece_at(s)] + [start.piece_at(m.from_square) for m in moves]
    choices = list(dict.fromkeys([named(present) if present else 'Casa vuota'] + [named(p) for p in seen if p] + ['Casa vuota']))
    right = choices[0]
    options = [right] + rng.sample(choices[1:], min(3, len(choices) - 1))
    rng.shuffle(options)
    return ('piece', f"Alla fine della linea che cosa c'è in {chess.square_name(square)}?", [o[0].upper() + o[1:] for o in options],
            options.index(right), f"In {chess.square_name(square)} c'è {right}." if present else f"{chess.square_name(square)} è vuota.")


def install(app, database, now):
    class AnswerBody(BaseModel):
        choice: int = Field(ge=0, le=7)

    def answers(con):
        return [(r['plies'], bool(r['success'])) for r in con.execute(
            'SELECT plies, success FROM visualization_questions WHERE answered_at IS NOT NULL ORDER BY answered_at')]

    def summary(con):
        done = answers(con)
        recent = done[-RECENT:]
        by_depth = {}
        for plies, success in done:
            by_depth.setdefault(plies, [0, 0])[success] += 1
        return {'plies': level(done), 'answered': len(done), 'recent': len(recent), 'recentCorrect': sum(s for _, s in recent),
                'byDepth': [{'plies': p, 'answered': w + r, 'correct': r} for p, (w, r) in sorted(by_depth.items())],
                'rules': {'min': MIN_PLIES, 'max': MAX_PLIES, 'start': START_PLIES, 'stepUp': STEP_UP}}

    @app.get('/api/visualization/summary')
    def visualization_summary():
        with database() as con:
            return summary(con)

    @app.post('/api/visualization/next')
    def visualization_next():
        with database() as con:
            plies = level(answers(con))
            games = con.execute("SELECT id, initial_fen, moves, player_color FROM games WHERE source NOT IN ('snapshot')").fetchall()
        rng = random.Random()
        usable = [g for g in games if len(json.loads(g['moves'])) >= FIRST_PLY + plies]
        if not usable:
            raise HTTPException(409, f'Serve almeno una partita di {(FIRST_PLY + plies + 1) // 2} mosse: gioca o importa una partita.')
        game = rng.choice(usable)
        moves = [chess.Move.from_uci(u) for u in json.loads(game['moves'])]
        ply = rng.randrange(FIRST_PLY, len(moves) - plies + 1)
        board = chess.Board(game['initial_fen'])
        for move in moves[:ply]:
            board.push(move)
        line = moves[ply:ply + plies]
        kind, text, options, answer, explanation = question(board, line, rng)
        end = board.copy(stack=False)
        for move in line:
            end.push(move)
        ident = str(uuid.uuid4())
        with database() as con:
            con.execute('''INSERT INTO visualization_questions(id, created_at, game_id, ply, fen, moves, plies, kind, question, options,
                           answer, explanation, final_fen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (ident, now(), game['id'], ply, board.fen(), json.dumps([m.uci() for m in line]), plies, kind, text,
                         json.dumps(options), answer, explanation, end.fen()))
        return {'id': ident, 'fen': board.fen(), 'orientation': game['player_color'], 'line': line_text(board, line),
                'plies': plies, 'question': text, 'options': options}

    @app.post('/api/visualization/{question_id}/answer')
    def visualization_answer(question_id: str, body: AnswerBody):
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM visualization_questions WHERE id=?', (question_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Domanda non trovata')
            if row['answered_at'] is not None:
                raise HTTPException(409, 'Domanda già risposta')
            if body.choice >= len(json.loads(row['options'])):
                raise HTTPException(422, 'Scelta non valida')
            success = body.choice == row['answer']
            con.execute('UPDATE visualization_questions SET choice=?, success=?, answered_at=? WHERE id=?',
                        (body.choice, int(success), now(), question_id))
            result = summary(con)
        return {'correct': success, 'answer': row['answer'], 'explanation': row['explanation'], 'finalFen': row['final_fen'],
                'moves': json.loads(row['moves']), 'summary': result}
