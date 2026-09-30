"""Persist failed training decisions and explain only their server-side evidence."""
import hashlib
import json
from typing import Literal

import chess
from fastapi import HTTPException

from . import tutor
from .engine import evaluator


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS training_mistakes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, target_id TEXT NOT NULL,
      attempt_id INTEGER NOT NULL, created_at TEXT NOT NULL, evidence TEXT NOT NULL,
      UNIQUE(kind,attempt_id));
    CREATE INDEX IF NOT EXISTS training_mistakes_target ON training_mistakes(kind,target_id,id);
    CREATE TABLE IF NOT EXISTS mistake_explanations(
      cache_key TEXT PRIMARY KEY, mistake_id INTEGER NOT NULL REFERENCES training_mistakes(id),
      response TEXT NOT NULL);
    ''')


def record(con, kind, target_id, attempt_id, board, move, best, actual, timestamp):
    # Mate scores are not pawn values: never turn engine mate sentinels into a loss.
    loss = max(0, best['cp'] - actual['cp']) if best['mate'] is None and actual['mate'] is None else None
    evidence = {'fen': board.fen(), 'turn': 'w' if board.turn else 'b',
                'move': move.uci(), 'san': board.san(move), 'best': best, 'actual': actual,
                'lossCp': loss, 'engine': evaluator.name,
                'criterion': 'Mantieni almeno −1,00, senza matto contro di te.' if kind == 'prevention'
                else 'Perdi al massimo 0,50 rispetto alla migliore mossa.'}
    con.execute('''INSERT INTO training_mistakes(kind,target_id,attempt_id,created_at,evidence)
                   VALUES(?,?,?,?,?)''', (kind, target_id, attempt_id, timestamp, json.dumps(evidence)))


def context_for(evidence):
    """Replay both engine lines, adding concrete captures and checks for the tutor."""
    context = dict(evidence)
    for name in ('best', 'actual'):
        board = chess.Board(evidence['fen'])
        steps = []
        for uci in evidence[name]['pv']:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise HTTPException(409, 'Variante salvata non valida: analizza nuovamente la posizione.')
            captured = board.piece_at(move.to_square)
            steps.append({'san': board.san(move), 'side': 'w' if board.turn else 'b',
                          'piece': board.piece_at(move.from_square).symbol(),
                          'from': chess.square_name(move.from_square), 'to': chess.square_name(move.to_square),
                          'captured': 'p' if board.is_en_passant(move) else captured.symbol() if captured else None,
                          'check': board.gives_check(move)})
            board.push(move)
        context[name] = {**evidence[name], 'steps': steps, 'finalFen': board.fen()}
    return context


def install(app, database, lock):
    @app.get('/api/training/{kind}/{target_id}/mistakes')
    def history(kind: Literal['prevention', 'puzzle'], target_id: str):
        with database() as con:
            rows = con.execute('SELECT * FROM training_mistakes WHERE kind=? AND target_id=? ORDER BY id',
                               (kind, target_id)).fetchall()
        # No best-move disclosure in the exercise list: it is used only on explicit explanation.
        return [{'id': r['id'], 'createdAt': r['created_at'],
                 'reference': {k: json.loads(r['evidence'])['best'][k] for k in ('cp', 'mate')},
                 **{k: v for k, v in json.loads(r['evidence']).items() if k != 'best'}} for r in rows]

    @app.post('/api/training/{kind}/{target_id}/mistakes/{mistake_id}/explain')
    def explain(kind: Literal['prevention', 'puzzle'], target_id: str, mistake_id: int):
        if not lock.acquire(blocking=False):
            raise HTTPException(429, 'Il tutor sta già preparando una spiegazione. Attendi e riprova.')
        try:
            with database() as con:
                row = con.execute('SELECT * FROM training_mistakes WHERE id=? AND kind=? AND target_id=?',
                                  (mistake_id, kind, target_id)).fetchone()
                if row is None:
                    raise HTTPException(404, 'Tentativo non trovato per questo esercizio.')
                _, model = tutor.configuration()
                key = hashlib.sha256(json.dumps([row['evidence'], model, tutor.MISTAKE_PROMPT_VERSION]).encode()).hexdigest()
                cached = con.execute('SELECT response FROM mistake_explanations WHERE cache_key=?', (key,)).fetchone()
                if cached:
                    return {**json.loads(cached['response']), 'cached': True}
            result = tutor.explain_mistake(context_for(json.loads(row['evidence'])), model)
            with database() as con:
                con.execute('INSERT OR REPLACE INTO mistake_explanations VALUES(?,?,?)', (key, mistake_id, json.dumps(result)))
            return {**result, 'cached': False}
        except tutor.TutorError as error:
            raise HTTPException(error.status, str(error)) from None
        finally:
            lock.release()
