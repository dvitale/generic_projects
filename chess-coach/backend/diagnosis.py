"""Self-diagnosis before a revealed solution: compare the player's reading with concrete engine evidence.

The player states an assessment, the opponent threat they fear (played on the board) and the candidate they
rejected. Stockfish, never the LLM, classifies the failure on two axes: search (solution missed or seen and
rejected) and reading (pessimistic, optimistic, ignored threat, phantom threat or accurate). A third fact
describes the solution itself (forcing, quiet move with a threat, prophylaxis or positional improvement), for the
positions where every candidate looks inconclusive. Raw answers are stored with the rule version, so the history
can be reclassified when the rules change.
"""
import json
import uuid
from typing import Literal

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .engine import evaluator, expected
from .maia import maia
from . import explain, insights, points
from .learning import category, value

RULE_VERSION = 2
NODES = 150000
BANDS = ['much_worse', 'worse', 'equal', 'better', 'much_better']
# Ignoring the threat costs at least 2 pawns and leaves no real advantage.
THREAT_DROP_CP = 200
THREAT_CEILING_CP = 100
# A stated threat is concrete when it would cost at least 1.5 pawns if ignored.
CONCRETE_DROP_CP = 150
# A quiet solution threatens something when moving again would gain at least this much,
# and is prophylactic when it takes at least this much off the opponent's best threat.
QUIET_THREAT_CP = 150
PROPHYLAXIS_CP = 150
SOLUTIONS = ('forcing', 'quiet_threat', 'prophylaxis', 'improvement')
OBSTACLES = ('inconclusive', 'no_plan', 'calculation', 'danger')
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
    candidate_reason: Literal['material', 'mate', 'calculation', 'inconclusive', 'other'] | None = None
    # What stopped the search, in the player's words: needed when no candidate was forcing.
    obstacle: Literal['inconclusive', 'no_plan', 'calculation', 'danger'] | None = None
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


def gain(path):
    """First capture, check or promotion of the solver in the engine line: when the gain becomes concrete."""
    for index, step in enumerate(path['steps']):
        if index % 2 == 0 and (step['captured'] or step['check'] or step['promotion']):
            return {'ply': index + 1, 'san': [s['san'] for s in path['steps'][:index + 1]]}
    return None


def solution(board, best, threat):
    """What kind of move the engine's solution is, with the concrete evidence for it."""
    if not best['pv']:
        return None
    move = chess.Move.from_uci(best['pv'][0])
    path = insights.line(board, best)
    found = {'move': move.uci(), 'san': board.san(move), 'line': [s['san'] for s in path['steps'][:8]], 'gain': gain(path)}
    forcing = [name for name, hit in (('check', board.gives_check(move)), ('capture', board.is_capture(move)),
                                       ('promotion', bool(move.promotion))) if hit]
    if forcing:
        return {**found, 'kind': 'forcing', 'forcing': forcing}
    after = board.copy(stack=False)
    after.push(move)
    # Moving again after the solution shows what it threatens; the opponent must answer it.
    again = threat_board(after)
    if again is not None:
        follow = evaluator.evaluate(again, nodes=NODES)
        # A free tempo is worth something in any position: the threat must be a nameable forcing move.
        hit = chess.Move.from_uci(follow['pv'][0]) if follow['pv'] else None
        forcing_hit = hit is not None and (again.gives_check(hit) or again.is_capture(hit) or bool(hit.promotion))
        sooner = follow['mate'] is not None and best['mate'] is not None and 0 < follow['mate'] < best['mate']
        if forcing_hit and (sooner or value(follow) - value(best) >= QUIET_THREAT_CP):
            return {**found, 'kind': 'quiet_threat', 'threat': {'san': follow['san'][0], 'evaluation': follow}}
    # The opponent's best move with a free tempo, played after the solution: does it still work?
    if threat and threat['move'] and value(best) - value(threat['evaluation']) >= PROPHYLAXIS_CP:
        stopped = chess.Move.from_uci(threat['move'])
        if stopped in after.legal_moves:
            line = player_view(evaluator.evaluate(after, stopped, nodes=NODES))
            if value(line) - value(threat['evaluation']) >= PROPHYLAXIS_CP:
                return {**found, 'kind': 'prophylaxis', 'stopped': {'san': threat['san'], 'before': threat['evaluation'], 'after': line},
                        'blocked': blocked(board, move)}
    moved = board.piece_at(move.from_square)
    before, later = insights.features(board, board.turn), insights.features(after, board.turn)
    facts = {'piece': moved.symbol().upper(), 'reach': [before['pieceReach'], later['pieceReach']],
             'openRooks': later['openRooks'] if later['openRooks'] != before['openRooks'] else None,
             'center': later['center'] if len(later['center']) > len(before['center']) else None}
    return {**found, 'kind': 'improvement', 'facts': facts}


def blocked(board, move):
    """The opponent's line piece whose reach the solution cuts the most: the squares it no longer attacks, those next to
    the player's king or holding the player's pieces first. A board fact, so it names what the prophylaxis changes."""
    me, after = board.turn, board.copy(stack=False)
    after.push(move)
    king, best = board.king(me), None
    for square in chess.SquareSet(board.occupied_co[not me]):
        piece = board.piece_at(square)
        if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        lost = board.attacks(square) & ~after.attacks(square)
        if not lost:
            continue
        near = [s for s in lost if king is not None and chess.square_distance(s, king) <= 1 or board.color_at(s) == me]
        key = (len(near), len(lost))
        if best is None or key > best[0]:
            ordered = sorted(lost, key=lambda s: chess.square_distance(s, square))
            best = (key, {'piece': piece.symbol().upper(), 'square': chess.square_name(square),
                          'lost': [chess.square_name(s) for s in ordered], 'near': [chess.square_name(s) for s in near],
                          'king': king is not None and any(chess.square_distance(s, king) <= 1 for s in near)})
    return best[1] if best else None


def idea_line(board, stopped, plies=5):
    """The opponent's best idea with a free move, as numbered SAN from the position after the pass."""
    passed = threat_board(board)
    pv = (stopped.get('before') or {}).get('pv') or []
    if passed is None or not pv:
        return stopped['san']
    out, cursor = [], passed.copy(stack=False)
    for i, uci in enumerate(pv[:plies]):
        move = chess.Move.from_uci(uci)
        if move not in cursor.legal_moves:
            break
        out.append(explain.label(cursor, move) if i == 0 or cursor.turn else cursor.san(move))
        cursor.push(move)
    return ' '.join(out) or stopped['san']


def solution_of(board, move=None):
    """The engine's solution (or the given one, as in a Lichess problem) and its kind, with a diagnosis's evidence."""
    best = evaluator.evaluate(board, move, nodes=NODES)
    passed, threat = threat_board(board), None
    if passed is not None:
        e = player_view(evaluator.evaluate(passed, nodes=NODES))
        threat = {'move': e['pv'][0] if e['pv'] else None, 'san': e['san'][0] if e['san'] else None, 'evaluation': e}
    return solution(board, best, threat)


# Tactical motif of a puzzle from the player's own game, as a Lichess theme: the solution answers the opponent's last
# move, so explain.refutation reads the solution line from the opponent's side with its verified board checks. The
# line must win at least MOTIF_GAIN of material, as in the mistake explanations.
MOTIF_THEMES = {'fork': 'fork', 'pin': 'pin', 'skewer': 'skewer', 'discovered': 'discoveredAttack', 'trapped': 'trappedPiece',
                'hanging': 'hangingPiece', 'undefended': 'hangingPiece', 'ignored_threat': 'hangingPiece', 'opened_line': 'hangingPiece'}
MOTIF_GAIN = 2


def motif(board, found):
    """Lichess theme of the solution's tactic, or None: no previous move, no material won or no verified motif."""
    if not board.move_stack or not found.get('line'):
        return None
    before = board.copy()
    last = before.pop()
    cursor, pv = board.copy(stack=False), [last.uci()]
    for san in found['line']:
        try:
            move = cursor.parse_san(san)
        except ValueError:
            break
        pv.append(move.uci())
        cursor.push(move)
    positions, taken = explain.walk(before, pv)
    them = before.turn
    if len(positions) < 3 or explain.settled(positions, pv, them, taken) - insights.material(before, them) > -MOTIF_GAIN:
        return None
    hit = explain.refutation(before, last.uci(), positions, pv, taken[not them])
    return MOTIF_THEMES.get(hit[0]) if hit else None


# The tempting move: among Maia's TEMPT_CANDIDATES likeliest moves at the player's level, the first that is not the
# solution, is chosen at least TEMPT_SHARE of the time and loses at least TEMPT_DROP of expected score (Queen paper's
# mistake threshold, arXiv 2610.03695).
TEMPT_CANDIDATES, TEMPT_SHARE, TEMPT_DROP, TEMPT_NODES = 3, 0.10, 0.10, 60000
MAIA_ELO = (600, 2600)
STATES = {'much_worse': 'sei in forte svantaggio', 'worse': 'sei in svantaggio', 'equal': 'la posizione è in equilibrio',
          'better': 'sei in vantaggio', 'much_better': 'sei in forte vantaggio'}


def tempting(board, found, elo):
    """Maia's natural move instead of the solution, refuted by Stockfish without naming the solution; None if none fits."""
    if not maia.available():
        return None
    elo = min(max(int(elo), MAIA_ELO[0]), MAIA_ELO[1])
    try:
        moves = maia.predict(board.fen(), elo, elo)['moves']
    except Exception:
        return None
    best = None
    for candidate in moves[:TEMPT_CANDIDATES]:
        if candidate['probability'] < TEMPT_SHARE:
            break
        if candidate['uci'] == found['move']:
            continue
        best = best or evaluator.settle(board, evaluator.evaluate(board, chess.Move.from_uci(found['move']), nodes=TEMPT_NODES))
        move = chess.Move.from_uci(candidate['uci'])
        actual = evaluator.settle(board, evaluator.evaluate(board, move, nodes=TEMPT_NODES))
        if expected(best) - expected(actual) < TEMPT_DROP:
            continue
        san, share = board.san(move), round(candidate['probability'] * 100)
        sentence = explain.explain(board.fen(), move.uci(), best, actual)
        if sentence and sentence['motif'] in explain.SAFE_MOTIFS:
            why = f"Non funziona. {sentence['text']}"
        else:
            # No verified motif: compare the outcomes in words, never naming the solution, and leave the line to «Mostra».
            after = STATES[category(actual)]
            why = (f"Non funziona: dopo {san} {after}, ma la mossa giusta ottiene molto di più." if category(best) == category(actual)
                   else f"Non funziona: con la mossa giusta {STATES[category(best)]}, dopo {san} {after}.")
            if len(actual['pv']) > 1:
                after_move = board.copy(stack=False)
                after_move.push(move)
                why += f" La risposta più forte è {explain.label(after_move, chess.Move.from_uci(actual['pv'][1]))}."
        return {'move': move.uci(), 'san': san, 'share': share, 'elo': elo, 'line': actual['pv'],
                'text': f"La mossa che viene più naturale è {san}: al tuo livello la sceglierebbe circa un giocatore su "
                        f"{max(1, round(100 / share))}. {why}"}
    return None


# Candidate moves (Queen paper, arXiv 2610.03695): the solution among CHOICES moves that a player could consider,
# the tempting move first, then Stockfish's best other move, then Maia's likeliest; each wrong one loses at least
# TEMPT_DROP, so only one works. Maia's moves count from MAIA_FLOOR probability up, among Stockfish's POOL best.
CHOICES, MAIA_FLOOR, POOL = 3, 0.02, 4


def candidates(board, found, elo, tempt=None):
    """The solution hidden among wrong moves worth considering, in alphabetical order; None without any."""
    pool = [tempt['move']] if tempt else []
    pool += [e['pv'][0] for e in evaluator.candidates(board, nodes=TEMPT_NODES // POOL, count=POOL) if e['pv']]
    if maia.available():
        elo = min(max(int(elo), MAIA_ELO[0]), MAIA_ELO[1])
        try:
            pool += [m['uci'] for m in maia.predict(board.fen(), elo, elo)['moves'][:6] if m['probability'] >= MAIA_FLOOR]
        except Exception:
            pass
    pool = [u for u in dict.fromkeys(pool) if u != found['move']]
    if not pool:
        return None
    ranked = {e['pv'][0]: e for e in evaluator.rank(board, [chess.Move.from_uci(u) for u in pool + [found['move']]], nodes=TEMPT_NODES)}
    solution = ranked.get(found['move']) or evaluator.evaluate(board, chess.Move.from_uci(found['move']), nodes=TEMPT_NODES)
    wrong = [u for u in pool if u in ranked and expected(solution) - expected(ranked[u]) >= TEMPT_DROP][:CHOICES - 1]
    if not wrong:
        return None
    moves = sorted([found['move']] + wrong, key=lambda u: board.san(chess.Move.from_uci(u)))
    sans = [board.san(chess.Move.from_uci(u)) for u in moves]
    others = 'l’altra non regge' if len(wrong) == 1 else f'le altre {len(wrong)} non reggono'
    return {'moves': moves, 'sans': sans,
            'text': f"La soluzione è una di queste mosse: {', '.join(sans[:-1])} o {sans[-1]}. "
                    f"Per ognuna cerca la risposta più forte dell’avversario: {others}."}


HINT_LEVELS = 2
HINT_TITLES = {'forcing': 'Mossa forzante', 'quiet_threat': 'Mossa tranquilla con una minaccia',
               'prophylaxis': 'Profilassi', 'improvement': 'Miglioramento di un pezzo'}
FORCING_NAMES = {'check': 'uno scacco', 'capture': 'una cattura', 'promotion': 'una promozione'}


def hints(board, found, tempt=None, choices=None):
    """Graduated hints from the classified solution: what kind of move to look for, the tempting move to discard,
    the candidate moves, then which piece plays it."""
    kind = found['kind']
    if kind == 'forcing':
        first = (f"La soluzione è {' e '.join(FORCING_NAMES[f] for f in found['forcing'])}. Se l’avevi vista e scartata, "
                 'calcolala fino in fondo: cerca la risposta dell’avversario che ti era sembrata sufficiente e verifica se regge davvero.')
    elif kind == 'quiet_threat':
        first = ('Non è uno scacco né una cattura: è una mossa tranquilla che prepara una minaccia, e l’avversario dovrà occuparsene. '
                 'Chiediti: se potessi muovere due volte di fila, che cosa giocheresti?')
    elif kind == 'prophylaxis':
        # The opponent's idea is named at once: guessing it is the point of the method, not of the hint.
        side = 'il Nero' if board.turn else 'il Bianco'
        first = (f"Non è uno scacco né una cattura: la mossa giusta toglie forza all’idea migliore {explain.articled('del', side)}. "
                 f"Se toccasse {explain.articled('al', side)}, Stockfish giocherebbe {idea_line(board, found['stopped'])}. "
                 'Cerca la mossa che rende quell’idea meno efficace.')
    else:
        first = ('Non c’è un colpo tattico: la mossa giusta migliora un pezzo. '
                 'Cerca il tuo pezzo meno attivo e chiediti su quale casa lavorerebbe meglio.')
    move = chess.Move.from_uci(found['move'])
    square = chess.square_name(move.from_square)
    name, _, gender = explain.NAMES[board.piece_at(move.from_square).piece_type]
    second = f"Guarda {'la tua' if gender == 'f' else 'il tuo'} {name} in {square}: è il pezzo che muove."
    if kind == 'prophylaxis' and (cut := found.get('blocked') or blocked(board, move)):
        piece = chess.Piece.from_symbol(cut['piece'].lower() if board.turn else cut['piece'])
        second += f" Il pezzo avversario da frenare è {explain.the(piece)} in {cut['square']}."
    given = [{'level': 1, 'title': HINT_TITLES[kind], 'text': first}]
    if tempt:
        given.append({'level': 2, 'title': 'La mossa che tenta', 'text': tempt['text'], 'fen': board.fen(), 'line': tempt['line']})
    if choices:
        given.append({'level': len(given) + 1, 'title': 'Mosse candidate', 'text': choices['text'], 'moves': choices['moves']})
    given.append({'level': len(given) + 1, 'title': 'Dove guardare', 'text': second, 'squares': [square]})
    return given


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
    evidence['solution'] = solution(board, best, evidence['threat'])

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
    evidence = json.loads(row['evidence'])
    found = evidence.get('solution')
    # Diagnoses saved before `blocked` existed get it from the board, without a new search.
    if found and found.get('kind') == 'prophylaxis' and 'blocked' not in found:
        found['blocked'] = blocked(chess.Board(row['fen']), chess.Move.from_uci(found['move']))
    return {'id': row['id'], 'kind': row['kind'], 'createdAt': row['created_at'], 'answer': json.loads(row['answer']),
            'evidence': evidence, 'search': row['search'], 'reading': json.loads(row['reading']),
            'ruleVersion': row['rule_version'], 'points': points.breakdown(row['fen'], evidence['best']) if evidence.get('best') else None}


def summary(con):
    rows = con.execute('SELECT * FROM failure_diagnoses ORDER BY created_at DESC, id DESC').fetchall()

    def window(batch):
        counts = {'missed_solution': 0, 'rejected_solution': 0, 'pessimistic': 0, 'optimistic': 0,
                  'ignored_threat': 0, 'phantom_threat': 0, 'accurate': 0}
        # Solution kinds among missed solutions only: what the search keeps leaving out.
        solutions = dict.fromkeys(SOLUTIONS, 0)
        for r in batch:
            counts[r['search']] += 1
            for label in json.loads(r['reading']):
                counts[label] += 1
            found = json.loads(r['evidence']).get('solution')
            if found and r['search'] == 'missed_solution':
                solutions[found['kind']] += 1
        return {'total': len(batch), 'counts': counts, 'solutions': solutions}

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
                  'obstacle': body.obstacle, 'note': body.note.strip()}
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
