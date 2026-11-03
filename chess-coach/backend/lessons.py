"""Guided lessons from a chess book, kept apart from the exercises built from the player's games.

The positions, questions, hints and accepted moves live in backend/data/logical_chess.json; the book is only cited
(game and page). Each lesson keeps two judgements side by side: the idea the book explains, chosen by hand, and
Stockfish's evaluation, computed offline by scripts/build_lessons.py. A move outside the lesson's list is judged
live by the engine, never counted as the lesson's answer.

Review: the same intervals as the training plan (training_schedule.INTERVAL_HOURS). Only an answer given when the
lesson is new or due counts; a right answer without hints moves it one step on, anything else brings it back in
RETRY_HOURS."""
import json
import uuid
from datetime import datetime, timedelta
from functools import lru_cache

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import ROOT, evaluator, missed_mate, review_label, review_loss
from .training_schedule import INTERVAL_HOURS

DATA = ROOT / 'backend/data/logical_chess.json'
VERDICTS = {'game': 'La mossa della partita', 'good': 'Alternativa valida', 'partial': 'Sensata, ma non è l’idea della lezione',
            'weak': 'Non risponde bene alla domanda', 'other': 'Non è fra le mosse previste'}
SUCCESS = {'game', 'good'}
HINTS = 3
RETRY_HOURS = 4
LIVE_NODES = 400000


@lru_cache(maxsize=1)
def load():
    return json.loads(DATA.read_text(encoding='utf-8'))


def replay(history):
    board = chess.Board()
    for san in history:
        board.push_san(san)
    return board


def validate(data, engine=True):
    """Every problem in the lesson file: positions that do not replay, illegal or unlisted moves, missing analysis."""
    errors, seen = [], set()
    for lesson in data['lessons']:
        name = lesson['id']
        if name in seen:
            errors.append(f'{name}: id ripetuto')
        seen.add(name)
        try:
            board = replay(lesson['history'])
        except ValueError as e:
            errors.append(f'{name}: la partita non si rigioca ({e})')
            continue
        if board.fen() != lesson['fen']:
            errors.append(f'{name}: FEN {lesson["fen"]} diversa da quella rigiocata {board.fen()}')
        if lesson['game'] not in data['games']:
            errors.append(f'{name}: partita {lesson["game"]} non descritta')
        if len(lesson['hints']) != HINTS:
            errors.append(f'{name}: servono {HINTS} indizi')
        for san, entry in lesson['moves'].items():
            try:
                if board.san(board.parse_san(san)) != san:
                    errors.append(f'{name}: {san} non è in SAN canonica')
            except ValueError:
                errors.append(f'{name}: {san} non è legale')
            if entry['verdict'] not in VERDICTS or entry['verdict'] == 'other':
                errors.append(f'{name}: giudizio {entry["verdict"]} sconosciuto per {san}')
        if lesson['moves'].get(lesson['played'], {}).get('verdict') != 'game':
            errors.append(f'{name}: la mossa della partita {lesson["played"]} deve avere il giudizio «game»')
        if sum(e['verdict'] == 'game' for e in lesson['moves'].values()) != 1:
            errors.append(f'{name}: una sola mossa della partita')
        if engine:
            analysis = lesson.get('engine')
            if not analysis:
                errors.append(f'{name}: manca l’analisi di Stockfish (scripts/build_lessons.py)')
            elif set(lesson['moves']) - set(analysis['moves']):
                errors.append(f'{name}: Stockfish non ha valutato {sorted(set(lesson["moves"]) - set(analysis["moves"]))}')
    return errors


def lesson_by_id(lesson_id):
    lesson = next((l for l in load()['lessons'] if l['id'] == lesson_id), None)
    if lesson is None:
        raise HTTPException(404, 'Lezione non trovata')
    return lesson


def line_text(history):
    board, parts = chess.Board(), []
    for san in history:
        parts.append(f"{board.fullmove_number}.{san}" if board.turn else san)
        board.push_san(san)
    return ' '.join(parts)


def game_view(lesson):
    data = load()
    game = data['games'][lesson['game']]
    return {**game, 'number': int(lesson['game']), 'page': lesson['page'],
            'citation': f"{data['source']['author']}, «{data['source']['title']}», partita {lesson['game']} "
                        f"({game['white']}–{game['black']}, {game['event']}), p. {lesson['page']}"}


def title(lesson):
    game = load()['games'][lesson['game']]
    board = replay(lesson['history'])
    return f"{game['white']}–{game['black']} · {board.fullmove_number}{'.' if board.turn else '…'}"


def state(row, timestamp):
    if row is None:
        return {'status': 'new', 'stage': 0, 'dueAt': None, 'attempts': 0, 'successes': 0, 'lastSuccess': None}
    return {'status': 'due' if row['due_at'] <= timestamp else 'waiting', 'stage': row['stage'], 'dueAt': row['due_at'],
            'attempts': row['attempts'], 'successes': row['successes'], 'lastSuccess': bool(row['last_success'])}


def schedule(row, success, hints, timestamp):
    """(stage, due_at) after a counted answer."""
    if success and hints == 0:
        stage = min((row['stage'] if row else 0) + 1, len(INTERVAL_HOURS))
        delay = INTERVAL_HOURS[stage - 1]
    else:
        stage, delay = 0, RETRY_HOURS
    return stage, (datetime.fromisoformat(timestamp) + timedelta(hours=delay)).isoformat()


def judged(board, lesson, move):
    """Stockfish's view of the move: stored analysis when the lesson lists it, a live search otherwise."""
    analysis, san = lesson['engine'], board.san(move)
    best = analysis['lines'][0]
    if san in analysis['moves']:
        actual = analysis['moves'][san]
    else:
        info = evaluator.evaluate(board, move, nodes=LIVE_NODES)
        actual = {'cp': info['cp'], 'mate': info['mate']}
    loss = review_loss(best, actual)
    return {'san': san, 'cp': actual['cp'], 'mate': actual['mate'], 'loss': loss,
            'label': review_label({'loss': loss, 'missedMate': missed_mate(best, actual)}), 'live': san not in analysis['moves']}


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS lesson_progress(
      lesson_id TEXT PRIMARY KEY, stage INTEGER NOT NULL, due_at TEXT NOT NULL, attempts INTEGER NOT NULL,
      successes INTEGER NOT NULL, last_success INTEGER NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS lesson_attempts(
      id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL, created_at TEXT NOT NULL, move TEXT NOT NULL, verdict TEXT NOT NULL,
      hints INTEGER NOT NULL, success INTEGER NOT NULL, counted INTEGER NOT NULL);
    ''')


def install(app, database, now):
    class AnswerBody(BaseModel):
        move: str = Field(min_length=4, max_length=5)
        hints: int = Field(ge=0, le=HINTS)

    def progress(con):
        return {r['lesson_id']: r for r in con.execute('SELECT * FROM lesson_progress')}

    def overview(con, timestamp):
        data, rows = load(), progress(con)
        items = [{'id': l['id'], 'title': title(l), 'theme': l['theme'], 'page': l['page'], 'game': int(l['game']),
                  **state(rows.get(l['id']), timestamp)} for l in data['lessons']]
        # Due reviews first, then new lessons in the book's order: the sample starts from the simplest ideas.
        due = [i for i in items if i['status'] == 'due'] + [i for i in items if i['status'] == 'new']
        waiting = [i['dueAt'] for i in items if i['status'] == 'waiting']
        return {'path': data['path'], 'source': data['source'], 'lessons': items, 'next': due[0]['id'] if due else None,
                'due': sum(i['status'] == 'due' for i in items), 'new': sum(i['status'] == 'new' for i in items),
                'nextDue': min(waiting, default=None), 'intervalHours': INTERVAL_HOURS}

    @app.get('/api/lessons')
    def lessons_overview():
        with database() as con:
            return overview(con, now())

    @app.get('/api/lessons/{lesson_id}')
    def lesson_detail(lesson_id: str):
        lesson = lesson_by_id(lesson_id)
        board = replay(lesson['history'])
        last = board.peek().uci() if board.move_stack else None
        with database() as con:
            current = state(progress(con).get(lesson_id), now())
        return {'id': lesson['id'], 'title': title(lesson), 'theme': lesson['theme'], 'question': lesson['question'],
                'hints': lesson['hints'], 'fen': board.fen(), 'turn': 'w' if board.turn else 'b', 'lastMove': last,
                'line': line_text(lesson['history']), 'legalMoves': [m.uci() for m in board.legal_moves],
                'game': game_view(lesson), 'counts': current['status'] != 'waiting', **current}

    @app.post('/api/lessons/{lesson_id}/answer')
    def lesson_answer(lesson_id: str, body: AnswerBody):
        lesson = lesson_by_id(lesson_id)
        board = replay(lesson['history'])
        try:
            move = chess.Move.from_uci(body.move)
        except ValueError:
            raise HTTPException(422, 'Mossa non valida')
        if move not in board.legal_moves:
            raise HTTPException(422, 'Mossa illegale in questa posizione')
        san = board.san(move)
        entry = lesson['moves'].get(san)
        verdict = entry['verdict'] if entry else 'other'
        success = verdict in SUCCESS
        engine = judged(board, lesson, move)
        timestamp = now()
        with database() as con:
            row = progress(con).get(lesson_id)
            counted = row is None or row['due_at'] <= timestamp
            con.execute('INSERT INTO lesson_attempts VALUES(?,?,?,?,?,?,?,?)',
                        (str(uuid.uuid4()), lesson_id, timestamp, san, verdict, body.hints, int(success), int(counted)))
            if counted:
                stage, due = schedule(row, success, body.hints, timestamp)
                con.execute('''INSERT INTO lesson_progress VALUES(?,?,?,1,?,?,?) ON CONFLICT(lesson_id) DO UPDATE SET
                  stage=excluded.stage, due_at=excluded.due_at, attempts=attempts+1, successes=successes+excluded.successes,
                  last_success=excluded.last_success, updated_at=excluded.updated_at''',
                            (lesson_id, stage, due, int(success), int(success), timestamp))
            current = state(progress(con).get(lesson_id), timestamp)
        analysis = lesson['engine']
        # After the answer the board shows the game move played, and the lesson says where its game can be followed on.
        after = board.copy()
        after.push_san(lesson['played'])
        return {'fenAfter': after.fen(), 'playedUci': after.peek().uci(), 'walk': walk_from_lesson(lesson),
                'success': success, 'verdict': verdict, 'verdictLabel': VERDICTS[verdict], 'move': san,
                'note': entry['note'] if entry else None, 'uci': move.uci(), 'played': lesson['played'], 'explanation': lesson['explanation'],
                'bookIdea': lesson['bookIdea'], 'engineNote': lesson.get('engineNote'), 'counted': counted, 'hints': body.hints,
                'moves': [{'san': s, 'uci': board.parse_san(s).uci(), 'verdict': e['verdict'], 'note': e['note'], **analysis['moves'][s]} for s, e in
                          sorted(lesson['moves'].items(), key=lambda kv: list(VERDICTS).index(kv[1]['verdict']))],
                'engine': {'depth': analysis['depth'], 'lines': analysis['lines'], 'move': engine},
                'game': game_view(lesson), **current}


# «Segui la partita»: a whole game from the book, move by move. The player guesses every move of one side; the
# other side's moves are played for them, each with a short note. Lesson moves reuse the lesson's question, hints
# and accepted moves. Only the first answer to each move in a run counts towards its score; runs never touch the
# lessons' review schedule.
WALK_HINTS = 2


def walk_by_id(walk_id):
    walk = next((w for w in load().get('walks', []) if w['id'] == walk_id), None)
    if walk is None:
        raise HTTPException(404, 'Partita non trovata')
    return walk


def walk_plies(walk):
    """Indexes of the moves the player guesses."""
    first = 0 if walk['side'] == 'w' else 1
    return list(range(first, len(walk['moves']), 2))


def walk_step(walk, ply):
    """What the player sees before guessing move `ply`: the guessed side's question, hints and accepted moves come
    from the linked lesson when there is one."""
    entry = walk['moves'][ply]
    lesson = lesson_by_id(entry['lesson']) if entry.get('lesson') else None
    question = lesson['question'] if lesson else entry['question']
    hints = lesson['hints'] if lesson else entry['hints']
    accepted = lesson['moves'] if lesson else entry.get('moves', {})
    return entry, lesson, question, hints, {**accepted, entry['san']: {'verdict': 'game', 'note': (accepted.get(entry['san']) or {}).get('note') or 'La mossa giocata nella partita.'}}


def walk_from_lesson(lesson):
    """The followed game that goes through the lesson's position, and the first move to guess after the lesson move."""
    history = lesson['history'] + [lesson['played']]
    for walk in load().get('walks', []):
        if walk['game'] == lesson['game'] and [m['san'] for m in walk['moves'][:len(history)]] == history:
            later = [p for p in walk_plies(walk) if p >= len(history)]
            if later:
                return {'id': walk['id'], 'ply': later[0], 'number': walk_plies(walk).index(later[0]) + 1}
    return None


def walk_step_moves(walk, ply, lessons):
    """The moves Stockfish evaluates for a walk move: the game move, and for the guessed side the accepted ones."""
    entry = walk['moves'][ply]
    accepted = lessons[entry['lesson']]['moves'] if entry.get('lesson') in lessons else entry.get('moves') or {}
    return [entry['san'], *[s for s in accepted if s != entry['san']]]


def validate_walks(data, engine=True):
    errors, lessons = [], {l['id']: l for l in data['lessons']}
    for walk in data.get('walks', []):
        name, board = walk['id'], chess.Board()
        if walk['game'] not in data['games']:
            errors.append(f'{name}: partita {walk["game"]} non descritta')
        if walk['side'] not in ('w', 'b'):
            errors.append(f'{name}: colore {walk["side"]} sconosciuto')
        for ply, entry in enumerate(walk['moves']):
            label = f"{name} {board.fullmove_number}{'.' if board.turn else '…'}{entry['san']}"
            try:
                move = board.parse_san(entry['san'])
            except ValueError:
                errors.append(f'{label}: mossa illegale')
                break
            if board.san(move) != entry['san']:
                errors.append(f'{label}: non è in SAN canonica')
            if not entry.get('note') or not entry.get('page'):
                errors.append(f'{label}: mancano nota o pagina')
            guessed = (ply % 2 == 0) == (walk['side'] == 'w')
            if guessed:
                lesson = lessons.get(entry.get('lesson'))
                if entry.get('lesson') and not lesson:
                    errors.append(f'{label}: lezione {entry["lesson"]} inesistente')
                elif lesson and (lesson['history'] != [m['san'] for m in walk['moves'][:ply]] or lesson['played'] != entry['san']):
                    errors.append(f'{label}: la lezione {lesson["id"]} non è questa posizione')
                elif not lesson and (not entry.get('question') or len(entry.get('hints', [])) != WALK_HINTS):
                    errors.append(f'{label}: servono una domanda e {WALK_HINTS} indizi')
                for san, alt in (entry.get('moves') or {}).items():
                    try:
                        if board.san(board.parse_san(san)) != san:
                            errors.append(f'{label}: {san} non è in SAN canonica')
                    except ValueError:
                        errors.append(f'{label}: {san} non è legale')
                    if alt['verdict'] not in VERDICTS or alt['verdict'] in ('game', 'other'):
                        errors.append(f'{label}: giudizio {alt["verdict"]} non ammesso per {san}')
            if engine:
                analysis = entry.get('engine')
                missing = set(walk_step_moves(walk, ply, lessons))
                if not analysis:
                    errors.append(f'{label}: manca l’analisi di Stockfish (scripts/build_lessons.py)')
                elif missing - set(analysis['moves']):
                    errors.append(f'{label}: Stockfish non ha valutato {sorted(missing - set(analysis["moves"]))}')
            board.push(move)
        if not board.is_game_over() and not walk.get('ending'):
            errors.append(f'{name}: la partita non finisce sulla scacchiera, serve una nota finale')
    return errors


def engine_view(analysis, san):
    best, actual = analysis['lines'][0], analysis['moves'][san]
    loss = review_loss(best, actual)
    return {'san': san, **actual, 'loss': loss, 'label': review_label({'loss': loss, 'missedMate': missed_mate(best, actual)}),
            'best': best['san'], 'bestScore': {'cp': best['cp'], 'mate': best['mate']}}


def walk_reply(walk, ply, board):
    """A move played for the player, with its note and Stockfish's judgement of it."""
    entry = walk['moves'][ply]
    move = board.parse_san(entry['san'])
    return {'ply': ply, 'san': entry['san'], 'uci': move.uci(), 'number': board.fullmove_number, 'white': board.turn == chess.WHITE,
            'note': entry['note'], 'page': entry['page'], 'engine': engine_view(entry['engine'], entry['san'])}


def walk_title(walk):
    game = load()['games'][walk['game']]
    return f"{game['white']}–{game['black']}"


def init_walk_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS lesson_walk_runs(
      id TEXT PRIMARY KEY, walk_id TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, next_ply INTEGER NOT NULL,
      answered INTEGER NOT NULL, found INTEGER NOT NULL, clean INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS lesson_walk_answers(
      id TEXT PRIMARY KEY, run_id TEXT NOT NULL, ply INTEGER NOT NULL, created_at TEXT NOT NULL, move TEXT NOT NULL,
      verdict TEXT NOT NULL, hints INTEGER NOT NULL, success INTEGER NOT NULL, counted INTEGER NOT NULL);
    ''')
    # first_ply: a run can start from a lesson, in the middle of the game; only the moves from there on are scored.
    if 'first_ply' not in {r[1] for r in con.execute('PRAGMA table_info(lesson_walk_runs)')}:
        con.execute('ALTER TABLE lesson_walk_runs ADD COLUMN first_ply INTEGER NOT NULL DEFAULT 0')


def install_walks(app, database, now):
    class WalkAnswer(BaseModel):
        run: str = Field(min_length=1, max_length=64)
        ply: int = Field(ge=0, le=1000)
        move: str = Field(min_length=4, max_length=5)
        hints: int = Field(ge=0, le=HINTS)

    def run_view(row, walk):
        if row is None:
            return None
        plies = walk_plies(walk)
        return {'id': row['id'], 'startedAt': row['started_at'], 'finishedAt': row['finished_at'], 'nextPly': row['next_ply'],
                'answered': row['answered'], 'found': row['found'], 'clean': row['clean'], 'firstPly': row['first_ply'],
                'fromNumber': plies.index(row['first_ply']) + 1 if row['first_ply'] in plies else 1,
                'total': len([p for p in plies if p >= row['first_ply']])}

    def runs(con, walk):
        return [run_view(r, walk) for r in con.execute('SELECT * FROM lesson_walk_runs WHERE walk_id=? ORDER BY started_at DESC', (walk['id'],))]

    def run_row(con, walk, run_id):
        row = con.execute('SELECT * FROM lesson_walk_runs WHERE id=? AND walk_id=?', (run_id, walk['id'])).fetchone()
        if row is None:
            raise HTTPException(404, 'Percorso non trovato')
        return row

    def step(walk, ply, run):
        plies = walk_plies(walk)
        if ply not in plies:
            raise HTTPException(422, 'Questa mossa non tocca a te')
        board, replies = chess.Board(), []
        previous = max([p for p in plies if p < ply], default=-1)
        for index, entry in enumerate(walk['moves'][:ply]):
            if index > previous:
                replies.append(walk_reply(walk, index, board))
            board.push_san(entry['san'])
        _, lesson, question, hints, _ = walk_step(walk, ply)
        return {'walk': walk['id'], 'ply': ply, 'number': plies.index(ply) + 1, 'total': len(plies), 'fen': board.fen(),
                'turn': 'w' if board.turn else 'b', 'line': line_text([m['san'] for m in walk['moves'][:ply]]),
                'lastMove': board.peek().uci() if board.move_stack else None, 'replies': replies, 'question': question,
                'hints': hints, 'lesson': lesson['id'] if lesson else None, 'legalMoves': [m.uci() for m in board.legal_moves],
                'run': run}

    @app.get('/api/lesson-walks')
    def walks_overview():
        data = load()
        with database() as con:
            items = []
            for walk in data.get('walks', []):
                game, done = data['games'][walk['game']], runs(con, walk)
                # The best score only compares runs played from the first move.
                finished = [r for r in done if r['finishedAt']]
                whole = [r for r in finished if r['fromNumber'] == 1]
                items.append({'id': walk['id'], 'title': walk_title(walk), 'game': int(walk['game']), 'side': walk['side'],
                              'event': game['event'], 'opening': game['opening'], 'result': walk.get('result'),
                              'summary': walk['summary'], 'total': len(walk_plies(walk)),
                              'current': next((r for r in done if not r['finishedAt']), None),
                              'last': finished[0] if finished else None, 'best': max(whole, key=lambda r: r['found'], default=None)})
        return {'walks': items}

    class StartBody(BaseModel):
        ply: int | None = Field(default=None, ge=0, le=1000)

    @app.post('/api/lesson-walks/{walk_id}/start')
    def walk_start(walk_id: str, body: StartBody | None = None):
        walk = walk_by_id(walk_id)
        run_id, first = str(uuid.uuid4()), walk_plies(walk)[0] if body is None or body.ply is None else body.ply
        if first not in walk_plies(walk):
            raise HTTPException(422, 'Questa mossa non tocca a te')
        with database() as con:
            con.execute('''INSERT INTO lesson_walk_runs(id, walk_id, started_at, finished_at, next_ply, answered, found, clean, first_ply)
              VALUES(?,?,?,NULL,?,0,0,0,?)''', (run_id, walk_id, now(), first, first))
            run = run_view(run_row(con, walk, run_id), walk)
        return step(walk, first, run)

    @app.get('/api/lesson-walks/{walk_id}/runs/{run_id}')
    def walk_resume(walk_id: str, run_id: str, ply: int | None = None):
        walk = walk_by_id(walk_id)
        with database() as con:
            run = run_view(run_row(con, walk, run_id), walk)
        if run['finishedAt'] and ply is None:
            raise HTTPException(409, 'Percorso già concluso')
        return step(walk, run['nextPly'] if ply is None else ply, run)

    @app.post('/api/lesson-walks/{walk_id}/answer')
    def walk_answer(walk_id: str, body: WalkAnswer):
        walk = walk_by_id(walk_id)
        plies = walk_plies(walk)
        if body.ply not in plies:
            raise HTTPException(422, 'Questa mossa non tocca a te')
        board = replay([m['san'] for m in walk['moves'][:body.ply]])
        try:
            move = chess.Move.from_uci(body.move)
        except ValueError:
            raise HTTPException(422, 'Mossa non valida')
        if move not in board.legal_moves:
            raise HTTPException(422, 'Mossa illegale in questa posizione')
        entry, lesson, _, _, accepted = walk_step(walk, body.ply)
        san = board.san(move)
        verdict = accepted[san]['verdict'] if san in accepted else 'other'
        success = verdict in SUCCESS
        analysis = entry['engine']
        if san in analysis['moves']:
            mine = engine_view(analysis, san)
        else:
            info = evaluator.evaluate(board, move, nodes=LIVE_NODES)
            mine = engine_view({**analysis, 'moves': {san: {'cp': info['cp'], 'mate': info['mate']}}}, san)
        mine['live'] = san not in analysis['moves']
        timestamp, after = now(), [p for p in plies if p > body.ply]
        with database() as con:
            row = run_row(con, walk, body.run)
            counted = not con.execute('SELECT 1 FROM lesson_walk_answers WHERE run_id=? AND ply=?', (body.run, body.ply)).fetchone()
            con.execute('INSERT INTO lesson_walk_answers VALUES(?,?,?,?,?,?,?,?,?)',
                        (str(uuid.uuid4()), body.run, body.ply, timestamp, san, verdict, body.hints, int(success), int(counted)))
            if counted:
                following = after[0] if after else row['next_ply']
                con.execute('''UPDATE lesson_walk_runs SET answered=answered+1, found=found+?, clean=clean+?, next_ply=MAX(next_ply,?),
                  finished_at=? WHERE id=?''', (int(success), int(success and body.hints == 0), following,
                                                 timestamp if not after else row['finished_at'], body.run))
            run = run_view(run_row(con, walk, body.run), walk)
        board.push(board.parse_san(entry['san']))
        # The opponent's answer comes with the next step; at the end of the game, the last moves come here.
        tail = []
        if not after:
            for index in range(body.ply + 1, len(walk['moves'])):
                tail.append(walk_reply(walk, index, board))
                board.push_san(walk['moves'][index]['san'])
        game = load()['games'][walk['game']]
        return {'success': success, 'verdict': verdict, 'verdictLabel': VERDICTS[verdict], 'move': san, 'uci': move.uci(),
                'note': accepted[san]['note'] if san in accepted and verdict != 'game' else None, 'counted': counted, 'hints': body.hints,
                'played': entry['san'], 'playedUci': board.move_stack[body.ply].uci(), 'explanation': lesson['explanation'] if lesson else entry['note'],
                'bookIdea': lesson['bookIdea'] if lesson else entry.get('book'), 'engineNote': (lesson or {}).get('engineNote') or entry.get('engineNote'),
                'page': entry['page'], 'lesson': lesson['id'] if lesson else None,
                'engine': {'depth': analysis['depth'], 'lines': analysis['lines'], 'move': mine, 'played': engine_view(analysis, entry['san'])},
                'moves': [{'san': s, 'uci': replay([m['san'] for m in walk['moves'][:body.ply]]).parse_san(s).uci(), 'verdict': e['verdict'],
                           'note': e['note'], **analysis['moves'][s]} for s, e in sorted(accepted.items(), key=lambda kv: list(VERDICTS).index(kv[1]['verdict']))],
                'nextPly': after[0] if after else None, 'finished': not after, 'tail': tail, 'result': walk.get('result') if not after else None,
                'ending': walk.get('ending') if not after else None,
                # After the answer the board shows the game move (and the last moves at the end): the game always goes on.
                'fenAfter': board.fen(), 'lastMove': board.peek().uci(),
                'citation': f"{load()['source']['author']}, «{load()['source']['title']}», partita {walk['game']} "
                            f"({game['white']}–{game['black']}, {game['event']}), p. {entry['page']}", 'run': run}
