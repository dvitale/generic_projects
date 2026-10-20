"""Rated problems from real games: a filtered copy of the Lichess puzzle database (CC0), solved offline.

Each Lichess puzzle starts with the opponent's move, usually the mistake to punish; the solution begins
with the second move. Puzzle ratings come from Lichess solvers (Glicko-2), not from the players of the game.
"""
import json
import random
import sqlite3
import uuid
from contextlib import closing

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import diagnosis

PUZZLES_FILE = 'lichess_puzzles.sqlite3'
SOURCE = 'https://database.lichess.org/#puzzles'
# (lower bound inclusive, upper bound exclusive, label). Shared with scripts/import_lichess_puzzles.py.
BANDS = [(0, 800, 'Fino a 800'), (800, 1000, '800–1000'), (1000, 1200, '1000–1200'), (1200, 1400, '1200–1400'),
         (1400, 1600, '1400–1600'), (1600, 1800, '1600–1800'), (1800, 2000, '1800–2000'), (2000, 2200, '2000–2200'),
         (2200, 2500, '2200–2500'), (2500, 4000, 'Oltre 2500')]
START_RATING = 1200
ADAPTIVE_RANGE = 100


def band_of(rating):
    return next(i for i, (low, high, _) in enumerate(BANDS) if low <= rating < high) if 0 <= rating < BANDS[-1][1] else None


def k_factor(games):
    # Faster convergence while the personal rating is still a guess.
    return 60 if games < 10 else 40 if games < 30 else 24


def expected(rating, opponent):
    return 1 / (1 + 10 ** ((opponent - rating) / 400))


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS problem_sessions(
      id TEXT PRIMARY KEY, puzzle_id TEXT NOT NULL, created_at TEXT NOT NULL,
      step INTEGER NOT NULL DEFAULT 1, failed INTEGER NOT NULL DEFAULT 0,
      revealed INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active');
    CREATE TABLE IF NOT EXISTS problem_attempts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL UNIQUE REFERENCES problem_sessions(id),
      puzzle_id TEXT NOT NULL, puzzle_rating INTEGER NOT NULL, success INTEGER NOT NULL,
      rating_before INTEGER NOT NULL, rating_after INTEGER NOT NULL, created_at TEXT NOT NULL);
    ''')
    # Wrong moves of the session as [step, uci]: the diagnosis shows them as the player's first candidates.
    if 'tried' not in {r[1] for r in con.execute('PRAGMA table_info(problem_sessions)')}:
        con.execute("ALTER TABLE problem_sessions ADD COLUMN tried TEXT NOT NULL DEFAULT '[]'")


class NextBody(BaseModel):
    band: int | None = Field(default=None, ge=0, le=len(BANDS) - 1)
    theme: str | None = Field(default=None, max_length=40, pattern=r'^[A-Za-z0-9]+$')


class MoveBody(BaseModel):
    move: str = Field(pattern=r'^[a-h][1-8][a-h][1-8][qrbn]?$')
    step: int = Field(ge=1)


class StepBody(BaseModel):
    step: int = Field(ge=1)


def install(app, database, data_dir, now):
    def puzzles():
        path = data_dir() / PUZZLES_FILE
        if not path.exists():
            return None
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        return con

    def require():
        con = puzzles()
        if con is None:
            raise HTTPException(404, 'Database dei problemi non installato: esegui make puzzles.')
        return con

    def rating(con):
        row = con.execute('SELECT rating_after, (SELECT COUNT(*) FROM problem_attempts) n FROM problem_attempts ORDER BY id DESC LIMIT 1').fetchone()
        return (row['rating_after'], row['n']) if row else (START_RATING, 0)

    def puzzle(store, puzzle_id):
        row = store.execute('SELECT * FROM puzzles WHERE id=?', (puzzle_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Problema non trovato')
        return row

    def board_at(row, step):
        board = chess.Board(row['fen'])
        for uci in row['moves'].split()[:step]:
            board.push_uci(uci)
        return board

    def view(row):
        moves = row['moves'].split()
        board = board_at(row, 1)
        return {'id': row['id'], 'fen': row['fen'], 'opponentMove': moves[0], 'turn': 'w' if board.turn else 'b',
                'length': len(moves) // 2}

    def details(row):
        return {'rating': row['rating'], 'ratingDeviation': row['rd'], 'plays': row['plays'], 'popularity': row['popularity'],
                'themes': row['themes'].split(), 'gameUrl': row['game_url'], 'opening': row['opening'].replace('_', ' ') or None,
                'solution': row['moves'].split()[1:]}

    def session_row(con, session_id):
        row = con.execute('SELECT * FROM problem_sessions WHERE id=?', (session_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Sessione non trovata')
        return row

    def rate(con, session, row, success):
        """Record the single rated outcome of a session: the first mistake, a reveal or a clean solution."""
        before, games = rating(con)
        after = round(before + k_factor(games) * ((1 if success else 0) - expected(before, row['rating'])))
        con.execute('INSERT INTO problem_attempts(session_id,puzzle_id,puzzle_rating,success,rating_before,rating_after,created_at) VALUES(?,?,?,?,?,?,?)',
                    (session['id'], row['id'], row['rating'], int(success), before, after, now()))
        return outcome(con, session['id'], row)

    def outcome(con, session_id, row):
        rated = con.execute('SELECT success, rating_before, rating_after FROM problem_attempts WHERE session_id=?', (session_id,)).fetchone()
        return {'success': bool(rated and rated['success']), 'ratingBefore': rated and rated['rating_before'],
                'ratingAfter': rated and rated['rating_after'], **details(row)}

    def diagnosis_position(con, puzzle_id, session_id):
        session = session_row(con, session_id)
        if session['puzzle_id'] != puzzle_id or session['status'] != 'active':
            raise HTTPException(409, 'Problema già concluso')
        with closing(require()) as store:
            row = puzzle(store, puzzle_id)
        solution = row['moves'].split()[session['step']]

        def accepts(board, move, evaluation, best):
            after = board.copy(stack=False)
            after.push(move)
            return move.uci() == solution or after.is_checkmate()
        tried = [move for step, move in json.loads(session['tried']) if step == session['step']]
        return {'board': board_at(row, session['step']), 'accepts': accepts, 'themes': row['themes'].split(), 'tried': tried}

    diagnosis.register('problem', diagnosis_position)

    @app.get('/api/problems')
    def overview():
        store = puzzles()
        with database() as con:
            value, games = rating(con)
            done = {r['puzzle_id']: r['success'] for r in con.execute('SELECT puzzle_id, MAX(success) success FROM problem_attempts GROUP BY puzzle_id')}
            history = con.execute('SELECT puzzle_rating, success FROM problem_attempts').fetchall()
        result = {'available': store is not None, 'source': SOURCE, 'rating': value, 'attempts': games,
                  'solved': sum(r['success'] for r in history), 'adaptiveRange': ADAPTIVE_RANGE}
        if store is None:
            return {**result, 'bands': [], 'themes': [], 'total': 0}
        with closing(store):
            counts = dict(store.execute('SELECT band, COUNT(*) FROM puzzles GROUP BY band').fetchall())
            themes = [{'id': r[0], 'count': r[1]} for r in store.execute('SELECT name, count FROM themes ORDER BY count DESC')]
            imported = dict(store.execute("SELECT key, value FROM meta WHERE key IN ('imported_at','source_rows')").fetchall())
        stats = [{'attempts': 0, 'solved': 0} for _ in BANDS]
        for r in history:
            band = band_of(r['puzzle_rating'])
            if band is not None:
                stats[band]['attempts'] += 1
                stats[band]['solved'] += r['success']
        return {**result, 'total': sum(counts.values()), 'themes': themes, 'importedAt': imported.get('imported_at'),
                'bands': [{'id': i, 'label': label, 'min': low, 'max': high, 'count': counts.get(i, 0), **stats[i]}
                          for i, (low, high, label) in enumerate(BANDS)], 'seen': len(done)}

    @app.post('/api/problems/next')
    def next_problem(body: NextBody):
        with closing(require()) as store, database() as con:
            seen = {r[0] for r in con.execute('SELECT puzzle_id FROM problem_attempts')}
            args: list[int | str]
            if body.band is None:
                value, _ = rating(con)
                where, args = 'rating BETWEEN ? AND ?', [value - ADAPTIVE_RANGE, value + ADAPTIVE_RANGE]
            else:
                where, args = 'band=?', [body.band]
            if body.theme:
                where += ' AND themes LIKE ?'
                args.append(f'% {body.theme} %')
            # Unseen problems first; repeat the oldest ones only when the selection is exhausted.
            candidates = [r['id'] for r in store.execute(f'SELECT id FROM puzzles WHERE {where}', args)]
            if not candidates:
                raise HTTPException(404, 'Nessun problema con questi filtri.')
            fresh = [c for c in candidates if c not in seen]
            chosen = random.choice(fresh or candidates)
            row = puzzle(store, chosen)
            session_id = str(uuid.uuid4())
            con.execute('INSERT INTO problem_sessions(id,puzzle_id,created_at) VALUES(?,?,?)', (session_id, chosen, now()))
            board = board_at(row, 1)
            return {'sessionId': session_id, 'step': 1, 'repeated': not fresh, 'puzzle': view(row),
                    'legalMoves': [m.uci() for m in board.legal_moves]}

    @app.post('/api/problems/sessions/{session_id}/moves')
    def play(session_id: str, body: MoveBody):
        with closing(require()) as store, database() as con:
            session = session_row(con, session_id)
            if session['status'] != 'active':
                raise HTTPException(409, 'Problema già concluso')
            if body.step != session['step']:
                raise HTTPException(409, 'La posizione è cambiata: ricarica il problema')
            row = puzzle(store, session['puzzle_id'])
            moves = row['moves'].split()
            board = board_at(row, session['step'])
            move = chess.Move.from_uci(body.move)
            if move not in board.legal_moves:
                raise HTTPException(422, 'Mossa illegale')
            board.push(move)
            # As on Lichess, any mate is accepted even when it differs from the stored solution.
            correct = body.move == moves[session['step']] or board.is_checkmate()
            if not correct:
                # The rating changes once, at the first mistake; the user may keep trying without effect.
                result = None
                con.execute('UPDATE problem_sessions SET tried=? WHERE id=?',
                            (json.dumps(json.loads(session['tried']) + [[session['step'], body.move]]), session_id))
                if not session['failed']:
                    con.execute('UPDATE problem_sessions SET failed=1 WHERE id=?', (session_id,))
                    rated = rate(con, session, row, False)
                    # Only the rating change: the solution stays hidden while the user keeps trying.
                    result = {key: rated[key] for key in ('success', 'ratingBefore', 'ratingAfter')}
                return {'correct': False, 'step': session['step'], 'result': result}
            step = session['step'] + 1
            reply = moves[step] if step < len(moves) and not board.is_checkmate() else None
            done = reply is None
            if reply:
                board.push_uci(reply)
                step += 1
            con.execute('UPDATE problem_sessions SET step=? WHERE id=?', (step, session_id))
            result = None
            if done:
                con.execute("UPDATE problem_sessions SET status='closed' WHERE id=?", (session_id,))
                result = outcome(con, session_id, row) if session['failed'] else rate(con, session, row, True)
            return {'correct': True, 'reply': reply, 'step': step, 'done': done, 'result': result,
                    'legalMoves': [] if done else [m.uci() for m in board.legal_moves]}

    @app.post('/api/problems/sessions/{session_id}/reveal')
    def reveal(session_id: str, body: StepBody):
        with closing(require()) as store, database() as con:
            session = session_row(con, session_id)
            if session['status'] != 'active':
                raise HTTPException(409, 'Problema già concluso')
            if body.step != session['step']:
                raise HTTPException(409, 'La posizione è cambiata: ricarica il problema')
            row = puzzle(store, session['puzzle_id'])
            con.execute("UPDATE problem_sessions SET status='closed', revealed=1 WHERE id=?", (session_id,))
            result = outcome(con, session_id, row) if session['failed'] else rate(con, session, row, False)
            return {'remaining': row['moves'].split()[session['step']:], 'result': result}

    @app.post('/api/problems/sessions/{session_id}/skip')
    def skip(session_id: str):
        with database() as con:
            session = session_row(con, session_id)
            # Skipping before the first move leaves no trace; afterwards the session is already rated or still running.
            if session['status'] == 'active' and session['step'] == 1 and not session['failed']:
                con.execute('DELETE FROM problem_sessions WHERE id=?', (session_id,))
                return {'skipped': True}
            return {'skipped': False}
