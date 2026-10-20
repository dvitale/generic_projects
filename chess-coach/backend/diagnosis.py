"""Self-diagnosis before a revealed solution: compare the player's reading with concrete engine evidence.

The player states an assessment, the opponent threat they fear (played on the board) and the candidate they
rejected. Stockfish, never the LLM, classifies the failure on two axes: search (solution missed or seen and
rejected) and reading (pessimistic, optimistic, ignored threat, phantom threat or accurate). Raw answers are
stored with the rule version, so the history can be reclassified when the rules change.
"""
import json
import uuid
from typing import Literal

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import evaluator
from .learning import category, value

RULE_VERSION = 1
NODES = 150000
BANDS = ['much_worse', 'worse', 'equal', 'better', 'much_better']
# Ignoring the threat costs at least 2 pawns and leaves no real advantage.
THREAT_DROP_CP = 200
THREAT_CEILING_CP = 100
# A stated threat is concrete when it would cost at least 1.5 pawns if ignored.
CONCRETE_DROP_CP = 150
WINDOW = 30
UCI = r'^[a-h][1-8][a-h][1-8][qrbn]?$'

# kind -> resolver(con, target_id, session_id) returning {'board', 'accepts', 'themes', 'tried'}.
# 'accepts(board, move, evaluation, best)' applies the mode's own success criterion;
# 'tried' lists the moves already played and rejected in this session, in order.
RESOLVERS = {}


def register(kind, resolver):
    RESOLVERS[kind] = resolver


def init_schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS failure_diagnoses(
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, target_id TEXT NOT NULL, session_id TEXT NOT NULL,
        fen TEXT NOT NULL, created_at TEXT NOT NULL, answer TEXT NOT NULL, evidence TEXT NOT NULL,
        search TEXT NOT NULL, reading TEXT NOT NULL, themes TEXT NOT NULL DEFAULT '[]',
        rule_version INTEGER NOT NULL, UNIQUE(kind, session_id))''')


class ContextBody(BaseModel):
    kind: Literal['puzzle', 'problem', 'prevention']
    target_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)


class DiagnosisBody(ContextBody):
    assessment: Literal['much_worse', 'worse', 'equal', 'better', 'much_better']
    confidence: Literal['uncertain', 'moderate', 'confident']
    feared_lost: bool = False
    threat: str | None = Field(default=None, pattern=UCI)
    candidate: str | None = Field(default=None, pattern=UCI)
    candidate_reason: Literal['material', 'mate', 'calculation', 'other'] | None = None
    note: str = Field(default='', max_length=1000)


def threat_board(board):
    """The same position with the opponent to move, or None when the side to move is in check."""
    if board.is_check():
        return None
    flipped = board.copy(stack=False)
    flipped.push(chess.Move.null())
    # A fresh board: engines receive a plain FEN, never a null move in the move list.
    return chess.Board(flipped.fen())


def moves(board):
    return [{'uci': m.uci(), 'san': board.san(m)} for m in board.legal_moves] if board else []


def tried_moves(board, tried):
    """Failed attempts of the session, once each: the first candidates the player thought of."""
    legal = {m.uci() for m in board.legal_moves}
    return [{'uci': u, 'san': board.san(chess.Move.from_uci(u))} for u in dict.fromkeys(tried) if u in legal]


def player_view(evaluation):
    """Turn an evaluation made with the opponent to move into the player's perspective."""
    mate = evaluation['mate']
    return {**evaluation, 'cp': -evaluation['cp'], 'mate': -mate if mate is not None else None}


def classify(board, accepts, answer):
    best = evaluator.evaluate(board, nodes=NODES)
    engine_band = category(best)
    evidence = {'best': best, 'engineBand': engine_band, 'engine': evaluator.name, 'nodes': NODES}
    reading = []

    gap = BANDS.index(answer['assessment']) - BANDS.index(engine_band)
    evidence['bandGap'] = gap
    if gap <= -2 or (answer['fearedLost'] and value(best) >= -100):
        reading.append('pessimistic')
    elif gap >= 2:
        reading.append('optimistic')

    passed = threat_board(board)
    if passed is not None:
        engine_threat = player_view(evaluator.evaluate(passed, nodes=NODES))
        drop = value(best) - value(engine_threat)
        real = drop >= THREAT_DROP_CP and value(engine_threat) <= THREAT_CEILING_CP
        evidence['threat'] = {'real': real, 'evaluation': engine_threat,
                              'move': engine_threat['pv'][0] if engine_threat['pv'] else None,
                              'san': engine_threat['san'][0] if engine_threat['san'] else None}
        concrete = None
        if answer['threat']:
            stated = chess.Move.from_uci(answer['threat'])
            if stated not in passed.legal_moves:
                raise HTTPException(422, 'La minaccia indicata non è una mossa legale dell’avversario.')
            line = player_view(evaluator.evaluate(passed, stated, nodes=NODES))
            # The engine's favourite reply is a threat only when that threat is real.
            concrete = (real and stated.uci() == evidence['threat']['move']) or value(best) - value(line) >= CONCRETE_DROP_CP
            evidence['statedThreat'] = {'san': passed.san(stated), 'evaluation': line, 'concrete': concrete}
            if not concrete:
                reading.append('phantom_threat')
        if real and not concrete:
            reading.append('ignored_threat')
    else:
        evidence['threat'] = None

    search = 'missed_solution'
    if answer['candidate']:
        move = chess.Move.from_uci(answer['candidate'])
        if move not in board.legal_moves:
            raise HTTPException(422, 'La candidata indicata non è una mossa legale.')
        line = best if best['pv'] and best['pv'][0] == move.uci() else evaluator.evaluate(board, move, nodes=NODES)
        sound = accepts(board, move, line, best)
        evidence['candidate'] = {'san': board.san(move), 'evaluation': line, 'sound': sound}
        if sound:
            search = 'rejected_solution'
    return search, reading or ['accurate'], evidence


def public(row):
    return {'id': row['id'], 'kind': row['kind'], 'createdAt': row['created_at'], 'answer': json.loads(row['answer']),
            'evidence': json.loads(row['evidence']), 'search': row['search'], 'reading': json.loads(row['reading']),
            'ruleVersion': row['rule_version']}


def summary(con):
    rows = con.execute('SELECT * FROM failure_diagnoses ORDER BY created_at DESC, id DESC').fetchall()

    def window(batch):
        counts = {'missed_solution': 0, 'rejected_solution': 0, 'pessimistic': 0, 'optimistic': 0,
                  'ignored_threat': 0, 'phantom_threat': 0, 'accurate': 0}
        for r in batch:
            counts[r['search']] += 1
            for label in json.loads(r['reading']):
                counts[label] += 1
        return {'total': len(batch), 'counts': counts}

    calibration = {level: {'total': 0, 'matched': 0} for level in ('uncertain', 'moderate', 'confident')}
    themes = {}
    for r in rows:
        answer, evidence = json.loads(r['answer']), json.loads(r['evidence'])
        bucket = calibration[answer['confidence']]
        bucket['total'] += 1
        bucket['matched'] += evidence['bandGap'] == 0
        for theme in json.loads(r['themes']):
            item = themes.setdefault(theme, {'theme': theme, 'total': 0, 'missed': 0, 'rejected': 0, 'misread': 0})
            item['total'] += 1
            item['missed' if r['search'] == 'missed_solution' else 'rejected'] += 1
            item['misread'] += json.loads(r['reading']) != ['accurate']
    return {'total': len(rows), 'window': WINDOW, 'recent': window(rows[:WINDOW]), 'previous': window(rows[WINDOW:2 * WINDOW]),
            'byKind': {k: sum(r['kind'] == k for r in rows) for k in ('puzzle', 'problem', 'prevention')},
            'calibration': calibration,
            # Few cases per theme say little: list only themes seen at least three times.
            'themes': sorted((t for t in themes.values() if t['total'] >= 3), key=lambda t: -t['total'])[:8],
            'recentItems': [public(r) for r in rows[:5]]}


def install(app, database, now):
    def resolve(con, body):
        resolver = RESOLVERS.get(body.kind)
        if resolver is None:
            raise HTTPException(404, 'Modalità non disponibile')
        return resolver(con, body.target_id, body.session_id)

    def existing(con, body):
        row = con.execute('SELECT * FROM failure_diagnoses WHERE kind=? AND session_id=?', (body.kind, body.session_id)).fetchone()
        return public(row) if row else None

    @app.post('/api/diagnoses/context')
    def context(body: ContextBody):
        with database() as con:
            saved = existing(con, body)
            if saved:
                return {'existing': saved}
            position = resolve(con, body)
        board = position['board']
        passed = threat_board(board)
        return {'existing': None, 'fen': board.fen(), 'color': 'w' if board.turn else 'b',
                'playerMoves': moves(board), 'tried': tried_moves(board, position.get('tried', [])), 'threatFen': passed.fen() if passed else None, 'threatMoves': moves(passed)}

    @app.post('/api/diagnoses')
    def diagnose(body: DiagnosisBody):
        with database() as con:
            saved = existing(con, body)
            if saved:
                return saved
            position = resolve(con, body)
        board = position['board']
        answer = {'assessment': body.assessment, 'confidence': body.confidence, 'fearedLost': body.feared_lost,
                  'threat': body.threat, 'candidate': body.candidate, 'candidateReason': body.candidate_reason,
                  'note': body.note.strip()}
        search, reading, evidence = classify(board, position['accepts'], answer)
        # Played and rejected by the mode itself: they never turn a miss into a rejected solution.
        evidence['tried'] = [m['san'] for m in tried_moves(board, position.get('tried', []))]
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            # The session must still be open: the diagnosis precedes the solution.
            resolve(con, body)
            con.execute('''INSERT OR IGNORE INTO failure_diagnoses
                (id,kind,target_id,session_id,fen,created_at,answer,evidence,search,reading,themes,rule_version)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (str(uuid.uuid4()), body.kind, body.target_id, body.session_id, board.fen(), now(),
                         json.dumps(answer), json.dumps(evidence), search, json.dumps(reading),
                         json.dumps(position.get('themes', [])), RULE_VERSION))
            return existing(con, body)

    @app.get('/api/diagnoses/summary')
    def diagnoses_summary():
        with database() as con:
            return summary(con)
