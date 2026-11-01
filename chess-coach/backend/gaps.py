"""Recurring gaps in Puzzle and Problemi, and a study path that works on one of them.

A gap is a group of positions the player solves on the first try, without help, clearly less often than expected:
a kind of solution (own puzzles, classified by Stockfish), a Lichess theme (problems) or, as a hypothesis, endgames
with little material (own puzzles). For problems the expectation is the Elo expected score against the puzzle
rating; for own puzzles it is the player's own average. Sessions played inside a study path do not count, and a
gap that a path closed counts again only from the closing date.

A study path is a short lesson with one of the player's own failures, a themed series of Lichess problems rising
in difficulty, a mixed series in which the theme is not announced, and a spaced review of the original failures.
The mixed series passes when the themed problems in it are solved about as often as their ratings predict;
otherwise the themed series starts again.
"""
import json
import random
import threading
import uuid
from contextlib import closing
from datetime import datetime, timedelta

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import problems

WINDOW = 300
WATCH_MIN, CONFIRM_MIN, CONFIRM_FAILURES = 3, 6, 3
# A gap: first-try success at least 20 points below the expectation.
GAP_DROP = 0.20
# The mixed series passes within 10 points of the expectation.
PASS_MARGIN = 0.10
THEMED_SIZE, MIXED_SIZE, MIXED_THEMED = 8, 8, 4
REVIEW_DAYS, REVIEW_SIZE = 2, 3
# The themed series starts below the player's rating and rises with each problem, up to slightly above it.
START_BELOW, STEP, TOP_ABOVE = 200, 50, 100
NEAREST = 12
# Endgame hypothesis: at most this many pieces besides kings and pawns.
ENDGAME_PIECES = 4
# Below this many themed problems the series repeats some of them, and the path says so.
FEW_PUZZLES = 20

ENDGAME_THEMES = {'endgame', 'rookEndgame', 'pawnEndgame', 'queenEndgame', 'bishopEndgame', 'knightEndgame', 'queenRookEndgame', 'zugzwang'}
METHOD_THEMES = {'quietMove', 'defensiveMove', 'long', 'veryLong'}
# Length, outcome and source tags say nothing about what had to be seen.
IGNORED_THEMES = {'short', 'oneMove', 'advantage', 'crushing', 'master', 'masterVsMaster', 'superGM', 'middlegame', 'opening', 'equality', 'mate'}
# The Lichess theme a path trains for a kind of solution of the player's own puzzles.
KIND_THEMES = {'quiet_threat': 'quietMove', 'prophylaxis': 'defensiveMove', 'forcing': 'long'}

LESSONS = {
    'quietMove': ('Mossa tranquilla', 'La mossa decisiva non dà scacco e non cattura: crea una minaccia che l’avversario non riesce a parare, oppure gli toglie l’ultima difesa.',
                  'Quando scacchi e catture non funzionano, chiediti: se potessi muovere due volte di fila, che cosa giocherei? Poi cerca la mossa che prepara quel colpo.'),
    'defensiveMove': ('Mossa difensiva e profilassi', 'La posizione chiede prima di tutto di fermare l’idea dell’avversario: un attacco, un matto, un pedone che corre.',
                      'Prima di cercare la tua mossa, chiediti che cosa giocherebbe l’avversario se toccasse a lui. Se è pericoloso, la soluzione parte da lì.'),
    'long': ('Calcolo di sequenze forzanti', 'La soluzione è una serie di scacchi, catture o minacce lunga tre mosse o più: il colpo funziona solo calcolato fino in fondo.',
             'Per ogni candidata forzante segui le risposte obbligate fino a una posizione calma, e solo lì valuta. Non fermarti alla prima risposta che sembra parare.'),
    'veryLong': ('Calcolo lungo', 'La sequenza vincente supera le quattro mosse: serve tenere a mente la posizione mentre cambia.',
                 'Scrivi mentalmente la variante principale mossa per mossa, e a ogni passo chiediti quale risposta dell’avversario cambia tutto.'),
    'fork': ('Attacco doppio', 'Un pezzo attacca due bersagli insieme: l’avversario può salvarne uno solo. Il cavallo è il pezzo tipico, ma lo fanno anche donna, pedoni e re.',
             'Cerca due pezzi avversari non difesi, o re e un pezzo, raggiungibili da una stessa casa. Spesso serve prima uno scacco o un sacrificio per portarli lì.'),
    'pin': ('Inchiodatura', 'Un pezzo non può muoversi senza esporre un pezzo più importante dietro di lui, sulla stessa linea: è come se non difendesse più nulla.',
            'Guarda le linee fra i tuoi pezzi a lungo raggio e il re o la donna avversari. Un pezzo inchiodato è un bersaglio: attaccalo di nuovo, magari con un pedone.'),
    'skewer': ('Infilata', 'Come l’inchiodatura, ma al contrario: il pezzo più importante sta davanti, si sposta, e quello dietro cade.',
               'Cerca re o donna sulla stessa linea di un altro pezzo, con una tua torre, alfiere o donna pronti a dare scacco o ad attaccare su quella linea.'),
    'discoveredAttack': ('Attacco di scoperta', 'Un pezzo si sposta e libera la linea di un altro pezzo che attacca: due minacce in una mossa sola.',
                         'Guarda i tuoi pezzi a lungo raggio coperti da un tuo pezzo. Dove può andare quel pezzo per creare una seconda minaccia, magari con scacco?'),
    'doubleCheck': ('Scacco doppio', 'Due pezzi danno scacco insieme: l’unica difesa è muovere il re, nessuna cattura o interposizione basta.',
                    'Quando un attacco di scoperta può dare scacco, chiediti se anche il pezzo che si sposta può dare scacco: il re resta senza difese.'),
    'deflection': ('Deviazione', 'Un pezzo avversario difende qualcosa di essenziale: lo costringi ad allontanarsi, con una cattura o uno scacco, e la difesa crolla.',
                   'Per ogni pezzo avversario chiediti: che cosa difende? Se difende due cose, o una sola cosa vitale, cerca la mossa che lo obbliga a spostarsi.'),
    'attraction': ('Adescamento', 'Un sacrificio attira un pezzo, spesso il re, su una casa dove subisce un colpo: scacco doppio, forchetta o matto.',
                   'Cerca le case dove un pezzo avversario sarebbe esposto a un tuo colpo, e chiediti con quale sacrificio puoi costringerlo ad andarci.'),
    'capturingDefender': ('Eliminare il difensore', 'Si cattura, anche cedendo materiale, il pezzo che tiene in piedi la difesa: dopo, il bersaglio vero cade.',
                          'Individua il bersaglio che vorresti attaccare e conta i suoi difensori. Se uno solo regge tutto, eliminalo prima.'),
    'clearance': ('Sgombero', 'Una mossa, spesso con tempo, libera una casa o una linea per un altro pezzo che darà il colpo decisivo.',
                  'Quando un colpo sarebbe decisivo ma un tuo pezzo ti è d’intralcio, cerca come spostarlo guadagnando tempo, con scacco o con una minaccia.'),
    'interference': ('Interferenza', 'Un pezzo si mette fra un difensore e ciò che difende, e taglia la linea di difesa.',
                     'Guarda le linee lungo cui l’avversario difende. C’è una casa su quella linea dove puoi mettere un pezzo, anche in presa?'),
    'intermezzo': ('Mossa intermedia', 'Invece della risposta attesa, ad esempio la ripresa di un pezzo, si gioca prima uno scacco o una minaccia più forte.',
                   'Prima di riprendere in automatico, chiediti se c’è uno scacco o una minaccia che l’avversario deve affrontare subito.'),
    'xRayAttack': ('Attacco a raggi X', 'Un pezzo agisce attraverso un altro pezzo sulla stessa linea: difende o attacca una casa anche se la vista sembra bloccata.',
                   'Quando conti attaccanti e difensori su una casa, includi i pezzi allineati dietro: dopo le catture entrano in gioco.'),
    'trappedPiece': ('Pezzo intrappolato', 'Un pezzo avversario non ha case sicure: basta attaccarlo per vincerlo.',
                     'Per i pezzi avversari avanzati o chiusi, conta le case di fuga. Se sono poche, cerca la mossa che le toglie e poi lo attacca.'),
    'hangingPiece': ('Pezzo indifeso', 'Un pezzo è in presa o difeso troppo poco: la soluzione è semplicemente prenderlo, o attaccarlo con tempo.',
                     'A ogni mossa fai l’inventario: quali pezzi avversari non sono difesi? Quali sono attaccati più volte di quante sono difesi?'),
    'sacrifice': ('Sacrificio', 'Si cede materiale per ottenere qualcosa di più grande: matto, recupero con interessi, attacco decisivo.',
                  'Non scartare una mossa solo perché perde materiale: seguila fino alla fine e conta il risultato, non il primo scambio.'),
    'backRankMate': ('Matto sulla traversa', 'Il re è chiuso dai propri pedoni sull’ultima traversa: una torre o una donna che arriva lì dà matto.',
                     'Guarda il re avversario: ha una casa di fuga? Se no, chi controlla la sua prima traversa, e puoi deviarlo o sovraccaricarlo?'),
    'exposedKing': ('Re esposto', 'Il re avversario ha poca protezione di pedoni: scacchi e attacchi diretti funzionano.',
                    'Conta i pezzi che possono raggiungere il re in due mosse, i tuoi e i suoi. Se sei in maggioranza, cerca la sequenza di scacchi.'),
    'kingsideAttack': ('Attacco sul lato di re', 'L’attacco contro l’arrocco richiede pezzi vicini al re e linee aperte; spesso un sacrificio apre la strada.',
                       'Prima di attaccare, conta attaccanti e difensori vicino al re. Cerca le case deboli davanti all’arrocco e come occuparle.'),
    'promotion': ('Promozione', 'Un pedone avanzato vale quanto un pezzo: la soluzione apre la strada alla promozione o la rende inevitabile.',
                  'Con un pedone vicino alla promozione chiediti chi controlla la casa di arrivo, e quale sacrificio la libera.'),
    'advancedPawn': ('Pedone avanzato', 'Un pedone sulla sesta o settima traversa lega l’avversario e crea minacce di promozione.',
                     'Conta i difensori della casa di promozione. Spesso basta deviarne uno, anche cedendo un pezzo.'),
    'zugzwang': ('Zugzwang', 'L’avversario starebbe bene se potesse passare, ma ogni sua mossa peggiora la posizione.',
                 'Nei finali chiediti che cosa succederebbe se fosse l’avversario a muovere. Se ogni mossa sua perde, cerca la mossa d’attesa che gli passa il tratto.'),
    'endgame': ('Tecnica dei finali', 'Nei finali contano il re attivo, l’opposizione, i pedoni passati e le posizioni teoriche: spesso la mossa giusta non è tattica ma tecnica.',
                'Attiva il re, conta i tempi per promuovere da entrambe le parti, e chiediti se la posizione assomiglia a un finale teorico che conosci (opposizione, Lucena, Philidor).'),
}
MATE_LESSON = ('Schemi di matto', 'Il matto nasce da schemi ricorrenti: re chiuso dai propri pezzi, case di fuga controllate, scacchi che lo spingono verso il bordo.',
               'Prima di tutto elenca le case di fuga del re avversario e chi le controlla. Poi cerca lo scacco che le toglie tutte, anche a costo di un sacrificio.')
GENERIC_LESSON = ('Schema tattico', 'Il tema si ripete nei problemi che non risolvi: rivederlo su molti esempi lo rende riconoscibile.',
                  'Dopo ogni problema della serie, chiediti quale dettaglio della posizione avrebbe dovuto farti pensare a questo tema.')


def lesson(theme):
    found = LESSONS.get(theme) or (LESSONS['endgame'] if theme in ENDGAME_THEMES else MATE_LESSON if 'Mate' in theme or theme.startswith('mate') else GENERIC_LESSON)
    return {'title': found[0], 'recognize': found[1], 'question': found[2]}


def endgame(board):
    return sum(1 for p in board.piece_map().values() if p.piece_type not in (chess.KING, chess.PAWN)) <= ENDGAME_PIECES


def motifs(themes):
    """The Lichess themes that name what had to be seen."""
    return [t for t in themes if t not in IGNORED_THEMES]


def family(key):
    kind, name = key.split(':', 1)
    if kind == 'phase' or name in ENDGAME_THEMES:
        return 'theory'
    return 'method' if kind == 'kind' or name in METHOD_THEMES else 'tactic'


def path_theme(key):
    kind, name = key.split(':', 1)
    return KIND_THEMES.get(name) if kind == 'kind' else 'endgame' if kind == 'phase' else name


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS study_paths(
      id TEXT PRIMARY KEY, gap TEXT NOT NULL, source TEXT NOT NULL, theme TEXT NOT NULL, stage TEXT NOT NULL,
      round INTEGER NOT NULL DEFAULT 1, examples TEXT NOT NULL DEFAULT '[]', review_at TEXT,
      created_at TEXT NOT NULL, closed_at TEXT, outcome TEXT);
    ''')
    if 'solution' not in {r[1] for r in con.execute('PRAGMA table_info(exercises)')}:
        con.execute('ALTER TABLE exercises ADD COLUMN solution TEXT')
    columns = {r[1] for r in con.execute('PRAGMA table_info(problem_sessions)')}
    # hint: {'step', 'level', 'solution'} of the current step; path_*: the study path stage the problem belongs to.
    for name, declaration in {'hint': 'TEXT', 'path_id': 'TEXT', 'path_stage': 'TEXT', 'path_themed': 'INTEGER'}.items():
        if name not in columns:
            con.execute(f'ALTER TABLE problem_sessions ADD COLUMN {name} {declaration}')


def parse(timestamp):
    return datetime.fromisoformat(timestamp)


FILLING = threading.Lock()


def fill(ids, solution_of):
    """Classify puzzles still without a kind of solution, one at a time, outside the request."""
    def run():
        with FILLING:
            for ident in ids:
                try:
                    solution_of(ident)
                except Exception:
                    pass
    if ids and not FILLING.locked():
        threading.Thread(target=run, daemon=True).start()


def own_records(con):
    """First-try outcomes of closed own puzzles with their kind of solution, and the puzzles not classified yet."""
    rows = [dict(r) for r in con.execute('''SELECT s.created_at, s.status, s.hints, s.guesses, e.id exercise, e.solution
        FROM puzzle_sessions s JOIN exercises e ON e.id=s.exercise_id WHERE s.status IN ('complete','revealed')
        ORDER BY s.created_at DESC LIMIT ?''', (WINDOW,))]
    missing = list(dict.fromkeys(r['exercise'] for r in rows if not r['solution']))
    records = []
    for r in rows:
        if not r['solution']:
            continue
        found = json.loads(r['solution'])
        keys = ['kind:' + found['kind']] + (['phase:endgame'] if found.get('endgame') else [])
        records.append({'keys': keys, 'success': r['status'] == 'complete' and not r['hints'] and r['guesses'] == 1,
                        'at': r['created_at'], 'example': r['exercise'], 'expected': None})
    base = sum(r['success'] for r in records) / len(records) if records else 0
    for r in records:
        r['expected'] = base
    return records, missing


def problem_records(con, store):
    rows = [dict(r) for r in con.execute('''SELECT a.puzzle_id, a.success, a.created_at, a.rating_before, a.puzzle_rating
        FROM problem_attempts a JOIN problem_sessions s ON s.id=a.session_id WHERE s.path_id IS NULL
        ORDER BY a.id DESC LIMIT ?''', (WINDOW,))]
    themes = {}
    if store is not None and rows:
        ids = list({r['puzzle_id'] for r in rows})
        themes = dict(store.execute(f"SELECT id, themes FROM puzzles WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall())
    return [{'keys': ['theme:' + t for t in motifs(themes.get(r['puzzle_id'], '').split())], 'success': bool(r['success']),
             'at': r['created_at'], 'example': r['puzzle_id'], 'expected': problems.expected(r['rating_before'], r['puzzle_rating'])}
            for r in rows]


def aggregate(source, records, closed):
    stats = {}
    for r in records:
        for key in r['keys']:
            if r['at'] <= closed.get(key, ''):
                continue
            s = stats.setdefault(key, {'n': 0, 'solved': 0, 'expected': 0.0, 'failed': []})
            s['n'] += 1
            s['solved'] += r['success']
            s['expected'] += r['expected']
            if not r['success']:
                s['failed'].append(r['example'])
    out = []
    for key, s in stats.items():
        rate, expected = s['solved'] / s['n'], s['expected'] / s['n']
        if s['n'] < WATCH_MIN or rate > expected - GAP_DROP:
            continue
        confirmed = s['n'] >= CONFIRM_MIN and s['n'] - s['solved'] >= CONFIRM_FAILURES
        out.append({'key': key, 'source': source, 'family': family(key), 'status': 'confirmed' if confirmed else 'watch',
                    'total': s['n'], 'solved': s['solved'], 'rate': round(rate, 3), 'expected': round(expected, 3),
                    'missing': 0 if confirmed else max(CONFIRM_MIN - s['n'], CONFIRM_FAILURES - (s['n'] - s['solved'])),
                    'theme': path_theme(key), 'examples': list(dict.fromkeys(s['failed']))[:REVIEW_SIZE]})
    return out


def find_gaps(con, store):
    """The gaps, confirmed first and then by distance from the expectation, and the puzzles not classified yet."""
    closed = {}
    for r in con.execute("SELECT gap, MAX(closed_at) FROM study_paths WHERE outcome='passed' GROUP BY gap"):
        closed[r[0]] = r[1]
    own, missing = own_records(con)
    found = aggregate('puzzle', own, closed) + aggregate('problem', problem_records(con, store), closed)
    return sorted(found, key=lambda g: (g['status'] != 'confirmed', g['rate'] - g['expected'])), missing


def theme_count(store, theme):
    return store.execute('SELECT COUNT(*) FROM puzzles WHERE themes LIKE ?', (f'% {theme} %',)).fetchone()[0]


def active_path(con):
    return con.execute("SELECT * FROM study_paths WHERE closed_at IS NULL ORDER BY created_at DESC LIMIT 1").fetchone()


def stage_key(path):
    return f"{path['stage']}:{path['round']}"


def stage_results(con, path):
    return [dict(r) for r in con.execute('''SELECT a.success, a.rating_before, a.puzzle_rating, s.path_themed themed, s.puzzle_id
        FROM problem_attempts a JOIN problem_sessions s ON s.id=a.session_id WHERE s.path_id=? AND s.path_stage=? ORDER BY a.id''',
        (path['id'], stage_key(path)))]


def install(app, database, open_store, solution_of, now):
    class PathBody(BaseModel):
        gap: str = Field(min_length=3, max_length=60, pattern=r'^(kind|theme|phase):[A-Za-z0-9_]+$')

    def store_or_409():
        store = open_store()
        if store is None:
            raise HTTPException(409, 'Il percorso usa i problemi Lichess: installali con make puzzles.')
        return store

    def example(con, store, path):
        examples = json.loads(path['examples'])
        if not examples:
            return None
        if path['source'] == 'problem':
            row = store.execute('SELECT * FROM puzzles WHERE id=?', (examples[0],)).fetchone() if store else None
            if row is None:
                return None
            board, moves = chess.Board(row['fen']), row['moves'].split()
            board.push_uci(moves[0])
            fen, sans = board.fen(), []
            for uci in moves[1:]:
                sans.append(board.san(chess.Move.from_uci(uci)))
                board.push_uci(uci)
            return {'fen': fen, 'turn': 'w' if chess.Board(fen).turn else 'b', 'solution': sans, 'label': f"Problema {row['id']}"}
        row = con.execute('SELECT e.*, g.number FROM exercises e JOIN games g ON g.id=e.game_id WHERE e.id=?', (examples[0],)).fetchone()
        if row is None:
            return None
        board = chess.Board(row['initial_fen'])
        for uci in json.loads(row['history']):
            board.push_uci(uci)
        return {'fen': board.fen(), 'turn': 'w' if board.turn else 'b', 'solution': [board.san(chess.Move.from_uci(row['best_move']))],
                'label': f"Dalla tua partita #{row['number']}"}

    def view(con, store, path):
        if path is None:
            return None
        path = dict(path)
        timestamp = now()
        if path['stage'] == 'waiting' and path['review_at'] <= timestamp:
            con.execute("UPDATE study_paths SET stage='review' WHERE id=?", (path['id'],))
            path['stage'] = 'review'
        results = stage_results(con, path)
        size = {'themed': THEMED_SIZE, 'mixed': MIXED_SIZE, 'review': len(json.loads(path['examples']))}.get(path['stage'], 0)
        return {'id': path['id'], 'gap': path['gap'], 'source': path['source'], 'theme': path['theme'], 'family': family(path['gap']),
                'stage': path['stage'], 'round': path['round'], 'reviewAt': path['review_at'], 'outcome': path['outcome'],
                'closedAt': path['closed_at'], 'lesson': lesson(path['theme']), 'example': example(con, store, path),
                # The mixed series never says which of its problems carry the theme.
                'progress': {'done': len(results), 'size': size, 'solved': sum(r['success'] for r in results) if path['stage'] != 'mixed' else None},
                'sizes': {'themed': THEMED_SIZE, 'mixed': MIXED_SIZE}, 'fewPuzzles': bool(store) and theme_count(store, path['theme']) < FEW_PUZZLES}

    @app.get('/api/gaps')
    def gaps_overview():
        store = open_store()
        with database() as con:
            found, missing = find_gaps(con, store)
            path = view(con, store, active_path(con))
            passed = [dict(r) for r in con.execute("SELECT gap, closed_at FROM study_paths WHERE outcome='passed' ORDER BY closed_at DESC LIMIT 10")]
        if store is not None:
            store.close()
        fill(missing, solution_of)
        return {'gaps': found, 'path': path, 'passed': passed, 'problemsAvailable': store is not None, 'unclassified': len(missing),
                'rules': {'watch': WATCH_MIN, 'confirm': CONFIRM_MIN, 'failures': CONFIRM_FAILURES, 'drop': GAP_DROP, 'window': WINDOW}}

    @app.get('/api/study-paths/active')
    def current():
        store = open_store()
        with database() as con:
            result = view(con, store, active_path(con))
            last = con.execute("SELECT gap, theme, source, outcome, review_at, closed_at FROM study_paths WHERE closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 1").fetchone()
        if store is not None:
            store.close()
        return {'path': result, 'last': last and {'gap': last['gap'], 'title': lesson(last['theme'])['title'], 'source': last['source'],
                                                  'outcome': last['outcome'], 'reviewAt': last['review_at'], 'closedAt': last['closed_at']}}

    @app.post('/api/study-paths')
    def create(body: PathBody):
        with closing(store_or_409()) as store, database() as con:
            if active_path(con):
                raise HTTPException(409, 'C’è già un percorso di studio in corso: concludilo o abbandonalo prima.')
            gap = next((g for g in find_gaps(con, store)[0] if g['key'] == body.gap), None)
            if gap is None or gap['status'] != 'confirmed':
                raise HTTPException(409, 'Lacuna non confermata: servono più casi prima di proporre un percorso.')
            if not gap['theme']:
                raise HTTPException(409, 'Per questo tipo di soluzione non ci sono problemi Lichess adatti.')
            if not theme_count(store, gap['theme']):
                raise HTTPException(409, 'Nessun problema Lichess con questo tema: importane altri con make puzzles.')
            ident = str(uuid.uuid4())
            con.execute('INSERT INTO study_paths(id,gap,source,theme,stage,examples,created_at) VALUES(?,?,?,?,?,?,?)',
                        (ident, gap['key'], gap['source'], gap['theme'], 'lesson', json.dumps(gap['examples']), now()))
            return {'path': view(con, store, active_path(con))}

    def owned(con, path_id):
        path = con.execute('SELECT * FROM study_paths WHERE id=?', (path_id,)).fetchone()
        if path is None:
            raise HTTPException(404, 'Percorso non trovato')
        if path['closed_at']:
            raise HTTPException(409, 'Percorso già concluso')
        return path

    @app.post('/api/study-paths/{path_id}/start')
    def begin(path_id: str):
        store = open_store()
        with database() as con:
            path = owned(con, path_id)
            if path['stage'] == 'lesson':
                con.execute("UPDATE study_paths SET stage='themed' WHERE id=?", (path_id,))
            result = view(con, store, owned(con, path_id))
        if store is not None:
            store.close()
        return {'path': result}

    @app.post('/api/study-paths/{path_id}/abandon')
    def abandon(path_id: str):
        with database() as con:
            owned(con, path_id)
            con.execute("UPDATE study_paths SET closed_at=?, outcome='abandoned' WHERE id=?", (now(), path_id))
        return {'path': None}


def pick(con, store, path_id, rating, timestamp):
    """The next problem of a path: (puzzle id, stage key, whether it carries the theme)."""
    path = con.execute('SELECT * FROM study_paths WHERE id=? AND closed_at IS NULL', (path_id,)).fetchone()
    if path is None:
        raise HTTPException(409, 'Percorso di studio non attivo')
    if path['stage'] == 'waiting' and path['review_at'] <= timestamp:
        con.execute("UPDATE study_paths SET stage='review' WHERE id=?", (path_id,))
        path = con.execute('SELECT * FROM study_paths WHERE id=?', (path_id,)).fetchone()
    if path['stage'] == 'lesson':
        raise HTTPException(409, 'Prima leggi la lezione del percorso.')
    if path['stage'] == 'waiting':
        raise HTTPException(409, 'Il ripasso del percorso non è ancora disponibile.')
    done = stage_results(con, path)
    if path['stage'] == 'review':
        tried = {r['puzzle_id'] for r in done}
        left = [p for p in json.loads(path['examples']) if p not in tried]
        if not left:
            raise HTTPException(409, 'Ripasso già completato')
        return left[0], stage_key(path), 1
    pattern = f"% {path['theme']} %"
    if path['stage'] == 'themed':
        themed, target = True, min(rating - START_BELOW + STEP * len(done), rating + TOP_ABOVE)
    else:
        # The same shuffled positions for the whole round: half the mixed series carries the theme.
        slots = random.Random(f"{path['id']}:{path['round']}").sample(range(MIXED_SIZE), MIXED_THEMED)
        themed, target = len(done) in slots, rating
    where = 'themes LIKE ?' if themed else 'themes NOT LIKE ?'
    seen = {r[0] for r in con.execute('SELECT puzzle_id FROM problem_attempts')}
    nearest = [r[0] for r in store.execute(f'SELECT id FROM puzzles WHERE {where} ORDER BY ABS(rating-?) LIMIT 200', (pattern, target))]
    if not nearest:
        raise HTTPException(404, 'Nessun problema disponibile per il percorso.')
    fresh = [p for p in nearest if p not in seen]
    return random.choice((fresh or nearest)[:NEAREST]), stage_key(path), int(themed)


def advance(con, session_id, timestamp):
    """After a problem of a path is rated, move the path on when its stage is complete."""
    session = con.execute('SELECT path_id, path_stage FROM problem_sessions WHERE id=?', (session_id,)).fetchone()
    if session is None or not session['path_id']:
        return
    path = con.execute('SELECT * FROM study_paths WHERE id=? AND closed_at IS NULL', (session['path_id'],)).fetchone()
    if path is None or stage_key(path) != session['path_stage']:
        return
    results = stage_results(con, path)
    if path['stage'] == 'themed' and len(results) >= THEMED_SIZE:
        con.execute("UPDATE study_paths SET stage='mixed' WHERE id=?", (path['id'],))
    elif path['stage'] == 'mixed' and len(results) >= MIXED_SIZE:
        themed = [r for r in results if r['themed']]
        expected = sum(problems.expected(r['rating_before'], r['puzzle_rating']) for r in themed)
        if sum(r['success'] for r in themed) >= expected - PASS_MARGIN * len(themed):
            review = (parse(timestamp) + timedelta(days=REVIEW_DAYS)).isoformat()
            if path['source'] == 'puzzle':
                # The original failures come back among the due puzzles; the path ends here.
                examples = json.loads(path['examples'])
                con.executemany('UPDATE exercises SET due_at=? WHERE id=?', [(review, e) for e in examples])
                con.execute("UPDATE study_paths SET stage='closed', review_at=?, closed_at=?, outcome='passed' WHERE id=?", (review, timestamp, path['id']))
            else:
                con.execute("UPDATE study_paths SET stage='waiting', review_at=? WHERE id=?", (review, path['id']))
        else:
            con.execute("UPDATE study_paths SET stage='themed', round=round+1 WHERE id=?", (path['id'],))
    elif path['stage'] == 'review' and len(results) >= len(json.loads(path['examples'])):
        con.execute("UPDATE study_paths SET stage='closed', closed_at=?, outcome='passed' WHERE id=?", (timestamp, path['id']))
