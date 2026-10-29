"""Persist failed training decisions and explain only their server-side evidence."""
import hashlib
import json
from typing import Literal

import chess
from fastapi import HTTPException

from . import tutor
from . import insights
from .engine import evaluator

COMPARISON_VERSION = 'contrast-3'


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


# A puzzle move is rejected when it gives up 0.70 or more against Stockfish's best move.
PUZZLE_TOLERANCE_CP = 70


def record(con, kind, target_id, attempt_id, board, move, best, actual, timestamp):
    # Mate scores are not pawn values: never turn engine mate sentinels into a loss.
    loss = max(0, best['cp'] - actual['cp']) if best['mate'] is None and actual['mate'] is None else None
    evidence = {'fen': board.fen(), 'turn': 'w' if board.turn else 'b',
                'move': move.uci(), 'san': board.san(move), 'best': best, 'actual': actual,
                'lossCp': loss, 'engine': evaluator.name,
                'criterion': 'Mantieni almeno −1,00 o perdi meno di 1,00 rispetto alla migliore, senza matto contro di te.' if kind == 'prevention'
                else 'Perdi meno di 0,70 rispetto alla migliore mossa di Stockfish.'}
    con.execute('''INSERT INTO training_mistakes(kind,target_id,attempt_id,created_at,evidence)
                   VALUES(?,?,?,?,?)''', (kind, target_id, attempt_id, timestamp, json.dumps(evidence)))


def replay(fen, evaluation):
    board = chess.Board(fen)
    steps = []
    for uci in evaluation['pv']:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise HTTPException(409, 'Variante salvata non valida: analizza nuovamente la posizione.')
        captured = board.piece_at(move.to_square)
        step = {'uci': uci, 'san': board.san(move), 'side': 'w' if board.turn else 'b',
                'number': board.fullmove_number, 'piece': board.piece_at(move.from_square).symbol(),
                'from': chess.square_name(move.from_square), 'to': chess.square_name(move.to_square),
                'captured': 'p' if board.is_en_passant(move) else captured.symbol() if captured else None,
                'check': board.gives_check(move)}
        board.push(move)
        if board.is_check():
            pieces = lambda squares: [{'square': chess.square_name(square), 'piece': board.piece_at(square).symbol()} for square in sorted(squares)]
            step['checkFacts'] = {
                'kingSquare': chess.square_name(board.king(board.turn)),
                'legalReplies': [board.san(reply) for reply in board.legal_moves],
                'checkingPieces': pieces(board.checkers()),
                'movedPieceDefenders': pieces(board.attackers(not board.turn, move.to_square))}
        steps.append({**step, 'fen': board.fen(), 'checkmate': board.is_checkmate()})
    return {**evaluation, 'steps': steps, 'finalFen': board.fen()}


def context_for(evidence):
    """Replay both engine lines, adding concrete captures and checks for the tutor."""
    context = dict(evidence)
    context['insight'] = insights.compare(evidence['fen'],evidence['move'],evidence['best'],evidence['actual'])
    for name in ('best', 'actual'):
        context[name] = replay(evidence['fen'], evidence[name])
    return context


def verified_context(evidence, kind):
    board = chess.Board(evidence['fen'])
    move = chess.Move.from_uci(evidence['move'])
    if move not in board.legal_moves:
        raise HTTPException(409, 'Tentativo salvato non legale per questa posizione.')
    best, actual, loss = evaluator.compare(board, move, nodes=320000)
    accepted = loss < PUZZLE_TOLERANCE_CP if kind == 'puzzle' else (
        actual['mate'] > 0 if actual['mate'] is not None else actual['cp'] >= -100)
    context = context_for({**evidence, 'best': best, 'actual': actual,
                          'lossCp': loss if best['mate'] is None and actual['mate'] is None else None})
    context['verification'] = {
        'acceptedNow': accepted, 'requestedNodesPerLine': 320000,
        'original': {k: evidence[k] for k in ('best', 'actual', 'lossCp')},
        'note': 'Ricerca più approfondita, non una certezza assoluta. Il tentativo storico non viene riscritto.'}
    # Test the same opponent response after the alternative. It may have a
    # different SAN/check status, or be illegal; never copy a line between boards.
    if len(actual['pv']) > 1 and best['pv']:
        reply = chess.Move.from_uci(actual['pv'][1])
        alternative = board.copy(); alternative.push_uci(best['pv'][0])
        legal = reply in alternative.legal_moves
        comparison = {'attemptReply': context['actual']['steps'][1]['san'],
                      'legalAfterAlternative': legal}
        if legal:
            forced = evaluator.evaluate(alternative, reply, nodes=160000)
            # All scores sent to the tutor/UI keep the original player's viewpoint.
            forced = {**forced, 'cp': -forced['cp'],
                      'mate': -forced['mate'] if forced['mate'] is not None else None,
                      'perspective': evidence['turn'], 'pv': [best['pv'][0], *forced['pv']]}
            line = replay(evidence['fen'], forced)
            line['san'] = [step['san'] for step in line['steps']]
            comparison.update({'alternativeReply': alternative.san(reply), 'line': line})
        context['sameReply'] = comparison
    return context


def verified_mate_explanation(context):
    """Explain this concrete contrast from legal moves, without an LLM inference."""
    actual = context['actual']['steps']
    same = context.get('sameReply', {}).get('line', {}).get('steps', [])
    if len(actual) < 2 or not actual[1]['checkmate'] or len(same) < 2:
        return None
    replies = same[1].get('checkFacts', {}).get('legalReplies', [])
    if not replies:
        return None
    attempted, refutation = actual[0]['san'], actual[1]['san']
    alternative, check = same[0]['san'], same[1]['san']
    board = chess.Board(context['fen'])
    after = chess.Board(same[1]['fen'])
    escape = []
    for reply in after.legal_moves:
        occupant = board.piece_at(reply.to_square)
        if (after.piece_type_at(reply.from_square) == chess.KING and occupant
                and occupant.color == board.turn
                and chess.square_name(reply.to_square) == same[0]['from']):
            escape.append(chess.square_name(reply.to_square))
    difference = (f"{alternative} libera la casa {', '.join(escape)}: il re può usarla dopo {check}. "
                  f"Con {attempted} quella casa resta occupata da un tuo pezzo.") if escape else (
                      f"Dopo {attempted} {refutation} non hai risposte legali. "
                      f"Dopo {alternative} {check} esistono invece queste risposte: {', '.join(replies)}.")
    best = context['best']
    if best['mate'] is not None:
        assessment = ('Stockfish trova un matto a favore.' if best['mate'] > 0 else
                      'Stockfish trova ancora un matto contro: evitare quello immediato non basta a salvare la partita.')
    else:
        number = f"{best['cp']/100:+.2f}".replace('.', ',')
        assessment = f"La valutazione di {alternative}, con le risposte migliori trovate da Stockfish, è {number} dal tuo punto di vista."
        if abs(best['cp']) <= 100:
            assessment += ' È una valutazione vicina alla parità, non un grande vantaggio.'
    explanation = {
        'reason': f"{attempted} permette {refutation}: è matto, verificato controllando tutte le risposte legali. {alternative} evita questo matto immediato.",
        'sharedIdea': 'Sono due scelte legali dalla stessa posizione. La differenza qui si vede provando la stessa risposta avversaria in entrambi i casi.',
        'difference': difference,
        'alternative': f"Dopo {alternative} {check} puoi rispondere con {', '.join(replies)}. {assessment}",
        'continuation': f"Confronta {attempted} {refutation} con {alternative} {check}. Nel secondo caso le risposte legali sono: {', '.join(replies)}. La stessa risposta imposta per confronto non è necessariamente la migliore difesa avversaria.",
        'lesson': 'Prima di scegliere una mossa, verifica la minaccia di matto avversaria e cerca una risposta legale concreta.',
        'tactical': f"Il fatto decisivo è il passaggio da {refutation}, matto, a {check}, scacco con risposte legali. {difference}",
        'positional': 'Il confronto dimostra una differenza nella sicurezza immediata del re. Non occorre attribuire un guadagno di materiale o un vantaggio posizionale non dimostrato.',
        'strategicPlan': 'Affronta prima la minaccia immediata al re; poi rivaluta la posizione prima di scegliere un piano a lungo termine.',
        'uncertainty': 'Il matto nel ramo del tentativo e le risposte legali nell’altro ramo sono verificati con le regole degli scacchi. Le valutazioni successive dipendono dalla ricerca limitata di Stockfish.'}
    return {'explanation': explanation, 'usage': 0, 'model': None,
            'provider': 'Regole degli scacchi e Stockfish', 'explanationSource': 'verified-mate-contrast'}


def install(app, database, lock):
    @app.get('/api/training/{kind}/{target_id}/mistakes')
    def history(kind: Literal['prevention', 'puzzle'], target_id: str):
        with database() as con:
            rows = con.execute('SELECT * FROM training_mistakes WHERE kind=? AND target_id=? ORDER BY id',
                               (kind, target_id)).fetchall()
        # No best-move disclosure in the exercise list: it is used only on explicit explanation.
        return [{'id': r['id'], 'createdAt': r['created_at'],
                 'insight': insights.public(insights.compare(**{k:json.loads(r['evidence'])[v] for k,v in [('fen','fen'),('played','move'),('best','best'),('actual','actual')]})),
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
                key = hashlib.sha256(json.dumps([row['evidence'], model, tutor.MISTAKE_PROMPT_VERSION, insights.VERSION, COMPARISON_VERSION]).encode()).hexdigest()
                cached = con.execute('SELECT response FROM mistake_explanations WHERE cache_key=?', (key,)).fetchone()
                if cached:
                    return {**json.loads(cached['response']), 'cached': True}
            context = verified_context(json.loads(row['evidence']), kind)
            result = verified_mate_explanation(context) or tutor.explain_mistake(context, model)
            result['comparison'] = {k: context[k] for k in ('fen', 'turn', 'best', 'actual', 'lossCp', 'criterion', 'verification')}
            if 'sameReply' in context:
                result['comparison']['sameReply'] = context['sameReply']
            with database() as con:
                con.execute('INSERT OR REPLACE INTO mistake_explanations VALUES(?,?,?)', (key, mistake_id, json.dumps(result)))
            return {**result, 'cached': False}
        except tutor.TutorError as error:
            raise HTTPException(error.status, str(error)) from None
        finally:
            lock.release()
