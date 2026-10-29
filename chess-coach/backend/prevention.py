"""Personal blunder avoidance: absolute safety, independent of best-move matching."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import SHORT_MATE, evaluator
from .maia import maia
from . import mistakes
from . import insights
from . import training_schedule
from . import diagnosis

SAFE_CP = -100
BLUNDER_CP = -200
# The exercise asks to avoid the game's blunder, not to find a good move: below SAFE_CP a move is still accepted
# unless it gives up this much against the best one, the same gap that made the game move a blunder.
AVOID_CP = 200
RULE_VERSION = 1
RULE = ('Basta evitare il blunder della partita: è accettata ogni mossa diversa da quella giocata allora che non è a sua '
        'volta un blunder, cioè resta almeno a −1,00 dalla tua parte oppure perde meno di 2,00 rispetto alla migliore, '
        'senza matto forzato contro di te. Non è richiesta la migliore: anche una mossa a −1,10 da quella va bene.')


# «Alla portata»: a blunder is a lapse (abbaglio), not a skill gap, when humans of the game's level rarely play it
# and the refutation is elementary or easy for the opponent to find. Maia gives the human side, Stockfish the line.
REACH_VERSION = 1
TYPICAL_PROBABILITY = 0.25  # Maia plays the blunder at least this often: an error typical of the level.
OBVIOUS_REPLY = 0.20  # Maia, for the opponent at the same level, finds the refutation at least this often.
ELEMENTARY_PLIES = 4  # Plies after the blunder in which the loss must become concrete.
ELEMENTARY_MATERIAL = 2  # Net material, in pawns, lost within those plies.
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
REACH_RULE = ('Sono un abbaglio i blunder che Maia, al livello della partita, gioca meno del 25% delle volte e la cui '
              'confutazione è elementare (matto in 1–2 o almeno 2 pedoni di materiale persi entro 4 semimosse) '
              'oppure viene trovata da Maia per l’avversario almeno il 20% delle volte.')


def balance(board, color):
    return sum(VALUES.get(p.piece_type, 0) * (1 if p.color == color else -1) for p in board.piece_map().values())


def elementary(board, actual):
    """The refutation needs no deep calculation: a short mate, or material gone within a few plies of the line."""
    if actual['mate'] is not None and actual['mate'] < 0 and -actual['mate'] <= SHORT_MATE:
        return True
    line, after, color = actual.get('pv') or [], board.copy(stack=False), board.turn
    start = balance(after, color)
    for uci in line[:1 + ELEMENTARY_PLIES]:
        move = chess.Move.from_uci(uci)
        if move not in after.legal_moves:
            break
        after.push(move)
    return after.is_checkmate() or balance(after, color) <= start - ELEMENTARY_MATERIAL


def assess_reach(items):
    """items: (board before the blunder, blunder uci, Stockfish line after it, level). One verdict per item, None without evidence."""
    if not maia.available():
        return [None] * len(items)
    requests, plan = [], []
    for board, move, actual, level in items:
        line = actual.get('pv') or []
        if len(line) < 2 or line[0] != move:
            plan.append(None)
            continue
        after = board.copy(stack=False)
        after.push_uci(move)
        plan.append(len(requests))
        requests += [(board.fen(), level, level), (after.fen(), level, level)]
    predictions = maia.predict_many(requests)
    verdicts = []
    for (board, move, actual, level), index in zip(items, plan):
        if index is None:
            verdicts.append(None)
            continue
        probability = lambda prediction, uci: next((m['probability'] for m in prediction['moves'] if m['uci'] == uci), 0.0)
        typical = probability(predictions[index], move)
        reply = actual['pv'][1]
        found = probability(predictions[index + 1], reply)
        simple = elementary(board, actual)
        status = 'typical' if typical >= TYPICAL_PROBABILITY else 'lapse' if simple or found >= OBVIOUS_REPLY else 'complex'
        verdicts.append({'version': REACH_VERSION, 'status': status, 'level': level, 'blunderProbability': round(typical, 4),
                         'reply': reply, 'replyProbability': round(found, 4), 'elementary': simple})
    return verdicts


def safe(value):
    return value['mate'] > 0 if value['mate'] is not None else value['cp'] >= SAFE_CP


def accepted(best, actual, original=False):
    """The answer avoids the game's blunder: it is not the game move and is not a blunder itself."""
    if original:
        return False
    if safe(actual):
        return True
    if actual['mate'] is not None or best['mate'] is not None:
        return False
    return best['cp'] - actual['cp'] < AVOID_CP


def eligible(best, actual):
    if not safe(best) or safe(actual):
        return False
    if actual['mate'] is not None:
        return actual['mate'] < 0
    return actual['cp'] <= BLUNDER_CP and (best['mate'] is not None or best['cp'] - actual['cp'] >= AVOID_CP)


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS prevention_positions(
      id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id), ply INTEGER NOT NULL,
      initial_fen TEXT NOT NULL, history TEXT NOT NULL, original_move TEXT NOT NULL,
      due_at TEXT NOT NULL, streak INTEGER NOT NULL DEFAULT 0,
      enabled INTEGER NOT NULL DEFAULT 1, verification TEXT);
    CREATE TABLE IF NOT EXISTS prevention_sessions(
      id TEXT PRIMARY KEY, position_id TEXT NOT NULL REFERENCES prevention_positions(id),
      created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', guesses INTEGER NOT NULL DEFAULT 0,
      exposure TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS prevention_attempts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES prevention_sessions(id),
      move TEXT NOT NULL, success INTEGER NOT NULL, assisted INTEGER NOT NULL,
      is_first INTEGER NOT NULL, created_at TEXT NOT NULL);
    ''')
    columns = {r[1] for r in con.execute('PRAGMA table_info(prevention_positions)')}
    for name in ('last_shown_at', 'reach', 'reach_status'):
        if name not in columns:
            con.execute(f'ALTER TABLE prevention_positions ADD COLUMN {name} TEXT')


def seed_game(con, row, analysis, timestamp, reach=True):
    """Index the player's blunders; with reach, also judge new or outdated ones (see assess_reach)."""
    moves = json.loads(row['moves'])
    board = chess.Board(row['initial_fen'])
    decisions = {d['ply']: d for d in analysis.get('decisions', [])}
    pending = []
    for ply, uci in enumerate(moves):
        d = decisions.get(ply)
        # Derive ownership and position from the saved line, not from stale analysis flags.
        if (d and d.get('played') == uci and d.get('fen') == board.fen()
                and board.turn == (row['player_color'] == 'w') and board.legal_moves.count() > 1
                and eligible(d['best'], d['actual'])):
            history = json.dumps(moves[:ply])
            identity = json.dumps([row['initial_fen'], moves[:ply], uci])
            position_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
            con.execute('''INSERT OR IGNORE INTO prevention_positions
              (id,game_id,ply,initial_fen,history,original_move,due_at) VALUES(?,?,?,?,?,?,?)''',
                        (position_id, row['id'], ply, row['initial_fen'], history, uci, timestamp))
            stored = con.execute('SELECT reach FROM prevention_positions WHERE id=?', (position_id,)).fetchone()[0]
            if reach and (stored is None or json.loads(stored).get('version') != REACH_VERSION):
                pending.append((position_id, (board.copy(stack=False), uci, d['actual'], row['elo'] or 1500)))
        board.push_uci(uci)
    for (position_id, _), verdict in zip(pending, assess_reach([item for _, item in pending])):
        if verdict:
            con.execute('UPDATE prevention_positions SET reach=?,reach_status=? WHERE id=?', (json.dumps(verdict), verdict['status'], position_id))


def backfill_reach(database, load_analysis):
    """Judge positions indexed before the reach rule (or by an older version), one game at a time."""
    with database() as con:
        ids = [r[0] for r in con.execute('''SELECT DISTINCT g.id FROM prevention_positions p JOIN games g ON g.id=p.game_id
            WHERE g.analysis IS NOT NULL AND (p.reach IS NULL OR json_extract(p.reach,'$.version')!=?)''', (REACH_VERSION,))]
    for game_id in ids:
        with database() as con:
            row = con.execute('SELECT * FROM games WHERE id=?', (game_id,)).fetchone()
            if row and row['analysis'] and row['analysis_version'] == len(json.loads(row['moves'])):
                seed_game(con, row, load_analysis(row['analysis']), row['created_at'])


class SessionBody(BaseModel):
    session_id: str = Field(min_length=1, max_length=50)
    version: int = Field(ge=0)


class AttemptBody(SessionBody):
    move: str = Field(pattern=r'^[a-h][1-8][a-h][1-8][qrbn]?$')


class PracticeBody(BaseModel):
    session_id: str = Field(min_length=1, max_length=50)
    move: str = Field(pattern=r'^[a-h][1-8][a-h][1-8][qrbn]?$')


def install(app, database, reconstruct, now):
    def find(con, position_id):
        row = con.execute('SELECT * FROM prevention_positions WHERE id=?', (position_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Posizione non trovata')
        if not row['enabled']:
            raise HTTPException(409, 'Posizione esclusa dalla verifica: scegli la prossima.')
        return row

    def active(con, position_id, session_id, version=None):
        s = con.execute('SELECT * FROM prevention_sessions WHERE id=? AND position_id=?', (session_id, position_id)).fetchone()
        if s is None:
            raise HTTPException(404, 'Sessione non trovata')
        if s['status'] != 'active' or (version is not None and s['guesses'] != version):
            raise HTTPException(409, 'Tentativo già registrato. Riapri la posizione per continuare.')
        return s

    def board_for(row):
        return reconstruct(row['initial_fen'], json.loads(row['history']))

    def check(board, move):
        best, actual, _ = evaluator.compare(board, move, nodes=300000)
        near_loss = best['mate'] is None and actual['mate'] is None and abs(best['cp'] - actual['cp'] - AVOID_CP) <= 50
        if near_loss or any(v['mate'] is None and abs(v['cp'] - SAFE_CP) <= 50 for v in (best, actual)):
            best, actual, _ = evaluator.compare(board, move, nodes=1200000)
        return best, actual

    def explanation(row, verification):
        board = board_for(row)
        return {'move': row['original_move'], 'san': board.san(chess.Move.from_uci(row['original_move'])),
                'evaluation': verification['actual']}

    def diagnosis_position(con, position_id, session_id):
        row = find(con, position_id)
        active(con, position_id, session_id)
        tried = [r[0] for r in con.execute('SELECT move FROM prevention_attempts WHERE session_id=? AND success=0 AND assisted=0 ORDER BY id', (session_id,))]
        return {'board': board_for(row), 'accepts': lambda board, move, evaluation, best: accepted(best, evaluation, move.uci() == row['original_move']), 'tried': tried}

    diagnosis.register('prevention', diagnosis_position)

    @app.get('/api/prevention')
    def catalog():
        with database() as con:
            rows = con.execute('''SELECT p.*,g.title,g.number AS game_number,g.created_at AS game_created_at FROM prevention_positions p JOIN games g ON g.id=p.game_id
                WHERE '''+training_schedule.PREVENTION_LISTED.format('p.')+'''
                ORDER BY p.due_at<=? DESC, p.last_shown_at IS NOT NULL, p.last_shown_at, p.due_at, p.id''', (now(),)).fetchall()
            items = []
            for row in rows:
                board = board_for(row)
                items.append({'id': row['id'], 'gameId': row['game_id'], 'title': row['title'], 'ply': row['ply'],
                              'gameCreatedAt': row['game_created_at'], 'gameNumber': row['game_number'],
                              'fen': board.fen(), 'turn': 'w' if board.turn else 'b', 'moveNumber': board.fullmove_number,
                              'legalMoves': [m.uci() for m in board.legal_moves], 'dueAt': row['due_at'], 'streak': row['streak']})
            stats = con.execute('''SELECT count(*) AS firstAttempts,coalesce(sum(a.success),0) AS firstSuccesses
                FROM prevention_attempts a JOIN prevention_sessions s ON s.id=a.session_id
                WHERE a.is_first=1 AND a.assisted=0 AND s.exposure IN ('new','review')''').fetchone()
            analyzed = con.execute('SELECT count(*) FROM games WHERE analysis IS NOT NULL').fetchone()[0]
            counts = dict(con.execute("SELECT coalesce(reach_status,'pending'),count(*) FROM prevention_positions WHERE enabled=1 GROUP BY 1").fetchall())
        return {'positions': items, 'stats': dict(stats), 'analyzedGames': analyzed,
                'reach': {'lapse': counts.get('lapse', 0), 'typical': counts.get('typical', 0), 'complex': counts.get('complex', 0),
                          'pending': counts.get('pending', 0), 'available': maia.available(), 'description': REACH_RULE},
                'rule': {'safeCp': SAFE_CP, 'avoidCp': AVOID_CP, 'description': RULE}}

    @app.post('/api/prevention/{position_id}/sessions')
    def session(position_id: str):
        with database() as con:
            row = dict(find(con, position_id))
        verification = json.loads(row['verification']) if row['verification'] else None
        if not verification or verification.get('ruleVersion') != RULE_VERSION:
            best, actual = check(board_for(row), chess.Move.from_uci(row['original_move']))
            verification = {'best': best, 'actual': actual, 'ruleVersion': RULE_VERSION, 'engine': evaluator.name}
            valid = eligible(best, actual)
            with database() as con:
                con.execute('UPDATE prevention_positions SET verification=?,enabled=? WHERE id=?',
                            (json.dumps(verification), int(valid), position_id))
            if not valid:
                return {'excluded': True, 'message': 'Il controllo approfondito non conferma un blunder evitabile: questa posizione è stata esclusa.'}
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            row = find(con, position_id)
            # Due positions rotate in the catalog: opening one sends it behind those not yet shown.
            con.execute('UPDATE prevention_positions SET last_shown_at=? WHERE id=?', (now(), position_id))
            previous = con.execute("SELECT * FROM prevention_sessions WHERE position_id=? AND status='active'", (position_id,)).fetchone()
            if previous:
                return {'id': previous['id'], 'version': previous['guesses'], 'exposure': previous['exposure']}
            seen = con.execute('SELECT 1 FROM prevention_sessions WHERE position_id=? LIMIT 1', (position_id,)).fetchone()
            exposure = 'practice' if not training_schedule.eligible(con,'prevention',position_id,now()) else 'new' if not seen else 'review' if row['due_at'] <= now() else 'practice'
            sid = str(uuid.uuid4())
            con.execute('INSERT INTO prevention_sessions(id,position_id,created_at,exposure) VALUES(?,?,?,?)', (sid, position_id, now(), exposure))
        return {'id': sid, 'version': 0, 'exposure': exposure}

    def finish(con, row, body, move, success, assisted):
        s = active(con, row['id'], body.session_id, body.version)
        first = s['guesses'] == 0
        promoted=training_schedule.record(con,'prevention',row,s,success,assisted,now())
        inserted = con.execute('INSERT INTO prevention_attempts(session_id,move,success,assisted,is_first,created_at) VALUES(?,?,?,?,?,?)',
                    (body.session_id, move, int(success), int(assisted), int(first), now()))
        closed = success or assisted
        con.execute('UPDATE prevention_sessions SET guesses=guesses+1,status=? WHERE id=?',
                    ('revealed' if assisted else 'complete' if success else 'active', body.session_id))
        return {'scheduled':promoted,'dueAt':find(con,row['id'])['due_at'],'attemptId': inserted.lastrowid, 'closed': closed, 'version': s['guesses'] + 1, 'firstTry': first and s['exposure'] != 'practice' and not assisted}

    @app.post('/api/prevention/{position_id}/practice')
    def practice(position_id: str, body: PracticeBody):
        """Free retry from the start once the session is closed: same criterion as an attempt, nothing is recorded."""
        with database() as con:
            row = dict(find(con, position_id))
            s = con.execute('SELECT status FROM prevention_sessions WHERE id=? AND position_id=?', (body.session_id, position_id)).fetchone()
        if s is None or s['status'] == 'active':
            raise HTTPException(409, 'La pratica libera si apre dopo aver chiuso la posizione')
        board = board_for(row)
        move = chess.Move.from_uci(body.move)
        if move not in board.legal_moves:
            raise HTTPException(422, 'Mossa non legale')
        best, actual = check(board, move)
        return {'success': accepted(best, actual, body.move == row['original_move']), 'san': board.san(move), 'actual': actual}

    @app.post('/api/prevention/{position_id}/attempts')
    def attempt(position_id: str, body: AttemptBody):
        with database() as con:
            row = dict(find(con, position_id))
            active(con, position_id, body.session_id, body.version)
        board = board_for(row)
        move = chess.Move.from_uci(body.move)
        if move not in board.legal_moves:
            raise HTTPException(422, 'Mossa non legale')
        best, actual = check(board, move)
        original = body.move == row['original_move']
        success = accepted(best, actual, original)
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            current = find(con, position_id)
            result = finish(con, current, body, body.move, success, False)
            if not success:
                mistakes.record(con, 'prevention', position_id, result['attemptId'], board, move, best, actual, now())
        return {**result, 'success': success, 'assisted': False, 'move': body.move, 'san': board.san(move), 'actual': actual,
                'insight': insights.public(insights.compare(board.fen(),body.move,best,actual)),
                'example': best if success else None,
                'original': explanation(row, json.loads(row['verification'])) if success else None,
                'message': ('Blunder evitato: non serve che sia la migliore.' if success else
                            'È la stessa mossa della partita: cerca dove sta l’abbaglio.' if original else
                            'Anche questa mossa è un blunder: secondo Stockfish scende sotto −1,00 e perde almeno 2,00 rispetto alla migliore. Riprova.')}

    @app.post('/api/prevention/{position_id}/reveal')
    def reveal(position_id: str, body: SessionBody):
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            row = find(con, position_id)
            active(con, position_id, body.session_id, body.version)
            verification = json.loads(row['verification'])
            best = verification['best']
            result = finish(con, row, body, 'reveal', False, True)
        return {**result, 'success': False, 'assisted': True, 'move': best['pv'][0], 'san': best['san'][0],
                'actual': best, 'example': best, 'original': explanation(row, verification),
                'message': 'Ecco una mossa sicura. Non è l’unica necessariamente accettata. Questo tentativo è con aiuto.'}
