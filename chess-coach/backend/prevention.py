"""Personal blunder avoidance: absolute safety, independent of best-move matching."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import evaluator
from . import mistakes
from . import insights

SAFE_CP = -100
BLUNDER_CP = -200
RULE_VERSION = 1


def safe(value):
    return value['mate'] > 0 if value['mate'] is not None else value['cp'] >= SAFE_CP


def eligible(best, actual):
    if not safe(best) or safe(actual):
        return False
    if actual['mate'] is not None:
        return actual['mate'] < 0
    return actual['cp'] <= BLUNDER_CP and (best['mate'] is not None or best['cp'] - actual['cp'] >= 200)


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


def seed_game(con, row, analysis, timestamp):
    moves = json.loads(row['moves'])
    board = chess.Board(row['initial_fen'])
    decisions = {d['ply']: d for d in analysis.get('decisions', [])}
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
        board.push_uci(uci)


class SessionBody(BaseModel):
    session_id: str = Field(min_length=1, max_length=50)
    version: int = Field(ge=0)


class AttemptBody(SessionBody):
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
        if any(v['mate'] is None and abs(v['cp'] - SAFE_CP) <= 50 for v in (best, actual)):
            best, actual, _ = evaluator.compare(board, move, nodes=1200000)
        return best, actual

    def explanation(row, verification):
        board = board_for(row)
        return {'move': row['original_move'], 'san': board.san(chess.Move.from_uci(row['original_move'])),
                'evaluation': verification['actual']}

    @app.get('/api/prevention')
    def catalog():
        with database() as con:
            rows = con.execute('''SELECT p.*,g.title FROM prevention_positions p JOIN games g ON g.id=p.game_id
                WHERE p.enabled=1 ORDER BY p.due_at,p.id''').fetchall()
            items = []
            for row in rows:
                board = board_for(row)
                items.append({'id': row['id'], 'gameId': row['game_id'], 'title': row['title'], 'ply': row['ply'],
                              'fen': board.fen(), 'turn': 'w' if board.turn else 'b', 'moveNumber': board.fullmove_number,
                              'legalMoves': [m.uci() for m in board.legal_moves], 'dueAt': row['due_at'], 'streak': row['streak']})
            stats = con.execute('''SELECT count(*) AS firstAttempts,coalesce(sum(a.success),0) AS firstSuccesses
                FROM prevention_attempts a JOIN prevention_sessions s ON s.id=a.session_id
                WHERE a.is_first=1 AND a.assisted=0 AND s.exposure IN ('new','review')''').fetchone()
            analyzed = con.execute('SELECT count(*) FROM games WHERE analysis IS NOT NULL').fetchone()[0]
        return {'positions': items, 'stats': dict(stats), 'analyzedGames': analyzed,
                'rule': {'safeCp': SAFE_CP, 'description': 'È accettata ogni mossa valutata almeno −1,00 dalla tua parte, senza matto forzato contro di te. Non è richiesta la migliore.'}}

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
            previous = con.execute("SELECT * FROM prevention_sessions WHERE position_id=? AND status='active'", (position_id,)).fetchone()
            if previous:
                return {'id': previous['id'], 'version': previous['guesses'], 'exposure': previous['exposure']}
            seen = con.execute('SELECT 1 FROM prevention_sessions WHERE position_id=? LIMIT 1', (position_id,)).fetchone()
            exposure = 'new' if not seen else 'review' if row['due_at'] <= now() else 'practice'
            sid = str(uuid.uuid4())
            con.execute('INSERT INTO prevention_sessions(id,position_id,created_at,exposure) VALUES(?,?,?,?)', (sid, position_id, now(), exposure))
        return {'id': sid, 'version': 0, 'exposure': exposure}

    def finish(con, row, body, move, success, assisted):
        s = active(con, row['id'], body.session_id, body.version)
        first = s['guesses'] == 0
        if first and s['exposure'] != 'practice':
            streak = row['streak'] + 1 if success and not assisted else 0
            interval = [1, 3, 7, 14, 30][min(max(streak - 1, 0), 4)]
            due = (datetime.now(timezone.utc) + timedelta(days=interval)).isoformat()
            con.execute('UPDATE prevention_positions SET streak=?,due_at=? WHERE id=?', (streak, due, row['id']))
        inserted = con.execute('INSERT INTO prevention_attempts(session_id,move,success,assisted,is_first,created_at) VALUES(?,?,?,?,?,?)',
                    (body.session_id, move, int(success), int(assisted), int(first), now()))
        closed = success or assisted
        con.execute('UPDATE prevention_sessions SET guesses=guesses+1,status=? WHERE id=?',
                    ('revealed' if assisted else 'complete' if success else 'active', body.session_id))
        return {'attemptId': inserted.lastrowid, 'closed': closed, 'version': s['guesses'] + 1, 'firstTry': first and s['exposure'] != 'practice' and not assisted}

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
        success = safe(actual)
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
                'message': 'Blunder evitato: questa mossa mantiene la posizione difendibile.' if success else 'Questa mossa scende sotto la soglia di sicurezza secondo Stockfish. Riprova: non serve trovare la migliore.'}

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
