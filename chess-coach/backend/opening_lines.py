"""Opening lines of the player's repertoire: drills against Maia from the end of a line, and line review, where the
player plays the book moves of one side and the opponent picks among the lines of the family."""
import json
import random
import uuid
from datetime import datetime, timedelta

import chess
from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import openings
from . import training_schedule

# Lines as SAN from the standard start. The name is Lichess's (lichess-org/chess-openings, CC0) when the final position
# has one; otherwise the fallback given here. The selection follows the Maia Chess drill catalogue for these families,
# plus the lines that come back in the player's games (Damiano, Paris Defense, Valencian, ...).
FAMILIES = [
    {'id': 'italiana', 'name': 'Partita italiana', 'prefix': 'Italian Game: ', 'root': 'e4 e5 Nf3 Nc6 Bc4',
     'description': 'Il Bianco sviluppa l’alfiere in c4 contro f7 e arrocca presto: gioco aperto, dove contano tempi e sicurezza del re.',
     'lines': [
         ('giuoco-piano', 'e4 e5 Nf3 Nc6 Bc4 Bc5', None),
         ('pianissimo', 'e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3', None),
         ('center-attack', 'e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d4', None),
         ('evans', 'e4 e5 Nf3 Nc6 Bc4 Bc5 b4', None),
         ('two-knights', 'e4 e5 Nf3 Nc6 Bc4 Nf6', None),
         ('modern-bishop', 'e4 e5 Nf3 Nc6 Bc4 Nf6 d3', None),
         ('knight-attack', 'e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5', None),
         ('fried-liver', 'e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5 d5 exd5 Nxd5 Nxf7', None),
         ('polerio', 'e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5 d5 exd5 Na5', None),
         ('traxler', 'e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5 Bc5', None),
         ('hungarian', 'e4 e5 Nf3 Nc6 Bc4 Be7', None),
         ('paris', 'e4 e5 Nf3 Nc6 Bc4 d6', None),
         ('anti-fried-liver', 'e4 e5 Nf3 Nc6 Bc4 h6', None)]},
    {'id': 'scandinava', 'name': 'Difesa scandinava', 'prefix': 'Scandinavian Defense: ', 'root': 'e4 d5',
     'description': 'Il Nero attacca subito e4: dopo 2.exd5 riprende di donna o di cavallo, e il Bianco guadagna tempi attaccando la donna.',
     'lines': [
         ('main-line', 'e4 d5 exd5 Qxd5 Nc3 Qa5', None),
         ('main-line-nf6', 'e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6 Nf3', 'Main Line, 4.d4 Nf6 5.Nf3'),
         ('valencian', 'e4 d5 exd5 Qxd5 Nc3 Qd8', None),
         ('gubinsky-melts', 'e4 d5 exd5 Qxd5 Nc3 Qd6', None),
         ('modern', 'e4 d5 exd5 Nf6', None),
         ('marshall', 'e4 d5 exd5 Nf6 d4 Nxd5', None),
         ('portuguese', 'e4 d5 exd5 Nf6 d4 Bg4', None),
         ('icelandic', 'e4 d5 exd5 Nf6 c4 e6', None)]},
    {'id': 'russa', 'name': 'Difesa russa (Petroff)', 'prefix': "Petrov's Defense: ", 'root': 'e4 e5 Nf3 Nf6',
     'description': 'Il Nero contrattacca e4 invece di difendere e5: attento alla copia simmetrica 3…Cxe4, che perde materiale dopo 4.De2.',
     'lines': [
         ('classical-attack', 'e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4', None),
         ('damiano', 'e4 e5 Nf3 Nf6 Nxe5 Nxe4', None),
         ('damiano-qe2', 'e4 e5 Nf3 Nf6 Nxe5 Nxe4 Qe2 Qe7 Qxe4 d6 d4', 'Damiano Variation, 4.Qe2'),
         ('stafford', 'e4 e5 Nf3 Nf6 Nxe5 Nc6', None),
         ('stafford-accepted', 'e4 e5 Nf3 Nf6 Nxe5 Nc6 Nxc6 dxc6 d3', 'Stafford Gambit Accepted, 5.d3'),
         ('cochrane', 'e4 e5 Nf3 Nf6 Nxe5 d6 Nxf7', None),
         ('three-knights', 'e4 e5 Nf3 Nf6 Nc3', None)]},
    {'id': 'london', 'name': 'Sistema London', 'prefix': '', 'root': 'd4',
     'description': 'Il Bianco porta presto l’alfiere in f4 e costruisce e3, c3 e Cf3: uno schema che si gioca quasi contro ogni difesa.',
     'lines': [
         ('accelerated', 'd4 d5 Bf4', None),
         ('main-line', 'd4 d5 Bf4 Nf6 e3', 'London System, 3.e3'),
         ('nf3', 'd4 d5 Bf4 Nf6 Nf3', None),
         ('steinitz', 'd4 d5 Bf4 c5', None),
         ('jobava', 'd4 d5 Nc3 Nf6 Bf4', None),
         ('indian-accelerated', 'd4 Nf6 Bf4', None),
         ('indian-e6', 'd4 Nf6 Nf3 e6 Bf4', None),
         ('indian-g6', 'd4 Nf6 Nf3 g6 Bf4', None)]},
    {'id': 'siciliana', 'name': 'Difesa siciliana', 'prefix': 'Sicilian Defense: ', 'root': 'e4 c5',
     'description': 'Il Nero lotta per il centro dal lato di donna: gioco asimmetrico, in cui il Bianco sceglie fra la Siciliana aperta e i sistemi anti-siciliani.',
     'lines': [
         ('open', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4', 'Open Sicilian'),
         ('najdorf', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6', None),
         ('dragon', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6', None),
         ('classical', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 Nc6', None),
         ('scheveningen', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 e6', None),
         ('moscow', 'e4 c5 Nf3 d6 Bb5+', None),
         ('accelerated-dragon', 'e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 g6', None),
         ('sveshnikov', 'e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 e5', 'Sveshnikov (Lasker-Pelikan) Variation'),
         ('rossolimo', 'e4 c5 Nf3 Nc6 Bb5', None),
         ('taimanov', 'e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6', None),
         ('kan', 'e4 c5 Nf3 e6 d4 cxd4 Nxd4 a6', None),
         ('alapin', 'e4 c5 c3', None),
         ('closed', 'e4 c5 Nc3', 'Closed Sicilian'),
         ('grand-prix', 'e4 c5 Nc3 Nc6 f4', None),
         ('smith-morra', 'e4 c5 d4 cxd4 c3', None),
         ('wing-gambit', 'e4 c5 b4', None)]},
    {'id': 'caro-kann', 'name': 'Difesa Caro-Kann', 'prefix': 'Caro-Kann Defense: ', 'root': 'e4 c6',
     'description': 'Il Nero prepara …d5 con il pedone c6 a sostegno: struttura solida, in cui spesso l’alfiere campochiaro esce prima di …e6.',
     'lines': [
         ('classical', 'e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5', None),
         ('tartakower', 'e4 c6 d4 d5 Nc3 dxe4 Nxe4 Nf6 Nxf6+ exf6', None),
         ('advance', 'e4 c6 d4 d5 e5', None),
         ('advance-bf5', 'e4 c6 d4 d5 e5 Bf5', 'Advance Variation, 3…Bf5'),
         ('exchange', 'e4 c6 d4 d5 exd5', None),
         ('panov', 'e4 c6 d4 d5 exd5 cxd5 c4', None),
         ('fantasy', 'e4 c6 d4 d5 f3', 'Fantasy (Maróczy) Variation'),
         ('two-knights', 'e4 c6 Nc3 d5 Nf3', None)]},
    {'id': 'gambetto-donna', 'name': 'Gambetto di donna', 'prefix': '', 'root': 'd4 d5 c4',
     'description': 'Il Bianco offre il pedone c4 per allontanare d5 dal centro; il Nero può prenderlo, rifiutarlo con …e6 o sostenerlo con …c6.',
     'lines': [
         ('declined', 'd4 d5 c4 e6 Nc3 Nf6', None),
         ('accepted', 'd4 d5 c4 dxc4', None),
         ('slav', 'd4 d5 c4 c6', None)]},
]

ROOT = chess.STARTING_FEN


def _build():
    names, lines, families = openings.catalogue(), {}, {}
    for family in FAMILIES:
        board, root = chess.Board(), []
        for san in family['root'].split():
            root.append(board.push_san(san).uci())
        entries = []
        for slug, san, fallback in family['lines']:
            board, moves = chess.Board(), []
            for move in san.split():
                moves.append(board.push_san(move).uci())
            assert moves[:len(root)] == root, (family['id'], slug)
            named = names.get(board.epd(), ('', ''))[1]
            name = named.removeprefix(family['prefix']) if named and not fallback else fallback
            assert name, (family['id'], slug)
            line = {'id': f"{family['id']}:{slug}", 'family': family['id'], 'name': name, 'moves': moves, 'fen': board.fen()}
            lines[line['id']] = line
            entries.append(line)
        families[family['id']] = {**{k: family[k] for k in ('id', 'name', 'description')}, 'rootMoves': root, 'lines': entries}
    return families, lines


FAMILY, LINE = _build()


def sans(moves, fen=ROOT):
    board, out = chess.Board(fen), []
    for uci in moves:
        move = chess.Move.from_uci(uci)
        out.append(board.san(move))
        board.push(move)
    return out


def tree(line_ids):
    """Book tree of the chosen lines, by position: EPD -> {uci: child EPD}, and the lines through each position."""
    children, through = {}, {}
    for ident in line_ids:
        board = chess.Board()
        through.setdefault(board.epd(), set()).add(ident)
        for uci in LINE[ident]['moves']:
            before = board.epd()
            board.push_uci(uci)
            children.setdefault(before, {})[uci] = board.epd()
            through.setdefault(board.epd(), set()).add(ident)
    return children, through


def terminal(family_id):
    """Lines of a family that no other line extends: the ends a review can reach."""
    lines = FAMILY[family_id]['lines']
    return [l['id'] for l in lines if not any(o is not l and o['moves'][:len(l['moves'])] == l['moves'] for o in lines)]


def met(con, color):
    """How many of the player's games with this colour reached the final position of each line."""
    counts = dict.fromkeys(list(LINE) + ['family:' + f for f in FAMILY], 0)
    ends = {}
    for ident, line in LINE.items():
        ends.setdefault(chess.Board(line['fen']).epd(), []).append(ident)
    for ident, family in FAMILY.items():
        board = chess.Board()
        for uci in family['rootMoves']:
            board.push_uci(uci)
        ends.setdefault(board.epd(), []).append('family:' + ident)
    for (moves,) in con.execute("""SELECT moves FROM games WHERE source NOT IN ('snapshot','drill','stockfish') AND initial_fen=?
                                   AND player_color=?""", (ROOT, color)):
        board, seen = chess.Board(), set()
        for uci in json.loads(moves)[:40]:
            board.push_uci(uci)
            seen.update(ends.get(board.epd(), ()))
        for ident in seen:
            counts[ident] += 1
    return counts


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS opening_line_sessions(
      id TEXT PRIMARY KEY, family TEXT NOT NULL, color TEXT NOT NULL, lines TEXT NOT NULL, target TEXT,
      moves TEXT NOT NULL, errors TEXT NOT NULL, hints TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
      line_id TEXT, created_at TEXT NOT NULL, finished_at TEXT);
    CREATE TABLE IF NOT EXISTS opening_line_reviews(
      id TEXT PRIMARY KEY, line_id TEXT NOT NULL, color TEXT NOT NULL, streak INTEGER NOT NULL DEFAULT 0,
      due_at TEXT NOT NULL, last_at TEXT NOT NULL, reviews INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0);
    ''')


def reviews(con, color=None):
    rows = con.execute('SELECT * FROM opening_line_reviews' + (' WHERE color=?' if color else ''), (color,) if color else ())
    return {r['line_id'] if color else r['id']: dict(r) for r in rows}


def plan_rows(con):
    """Lines already reviewed come back in the daily plan when due; lines never reviewed are not prescribed."""
    rows = []
    for r in con.execute('SELECT * FROM opening_line_reviews WHERE reviews>0'):
        line = LINE.get(r['line_id'])
        if line:
            rows.append({'kind': 'line', 'id': r['id'], 'gameId': 'line:' + r['id'], 'ply': 0,
                         'title': FAMILY[line['family']]['name'] + (' col Bianco' if r['color'] == 'w' else ' col Nero'),
                         'theme': 'Ripassa la linea · ' + line['name'], 'stage': r['streak'], 'dueAt': r['due_at'],
                         'readyAt': r['due_at'], 'new': False})
    return rows


def weights(children, through, epd, due, counts, target):
    """Opponent choice among the book moves: towards the target line if possible, else weighted by the lines below each
    move, with more weight to lines met in the player's games and to lines due or failed."""
    options = children.get(epd, {})
    if target:
        towards = [uci for uci, child in options.items() if target in through[child]]
        if towards:
            return {towards[0]: 1.0}
    return {uci: sum(1 + 2 * counts.get(l, 0) + (3 if l in due else 0) for l in through[child]) for uci, child in options.items()}


class LineStart(BaseModel):
    family: str = Field(default='', max_length=40)
    color: str = Field(default='w', pattern='^[wb]$')
    lines: list[str] | None = Field(default=None, max_length=40)
    target: str | None = Field(default=None, max_length=80)


class LineMove(BaseModel):
    move: str = Field(pattern=r'^[a-h][1-8][a-h][1-8][qrbn]?$')
    version: int = Field(ge=0)


class LineVersion(BaseModel):
    version: int = Field(ge=0)


def install(app, database, now):
    def load(con, session_id):
        row = con.execute('SELECT * FROM opening_line_sessions WHERE id=?', (session_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Sessione non trovata')
        return {**dict(row), 'moves': json.loads(row['moves']), 'errors': json.loads(row['errors']),
                'hints': json.loads(row['hints']), 'lines': json.loads(row['lines'])}

    def save(con, s):
        con.execute('''UPDATE opening_line_sessions SET moves=?,errors=?,hints=?,status=?,line_id=?,finished_at=? WHERE id=?''',
                    (json.dumps(s['moves']), json.dumps(s['errors']), json.dumps(s['hints']), s['status'], s['line_id'],
                     s['finished_at'], s['id']))

    def board_of(s):
        board = chess.Board()
        for uci in s['moves']:
            board.push_uci(uci)
        return board

    def mine(s, board):
        return board.turn == (s['color'] == 'w')

    def expected(s, board):
        children, _ = tree(s['lines'])
        return [board.san(chess.Move.from_uci(uci)) for uci in children.get(board.epd(), {})]

    def advance(con, s):
        """Opponent book moves until the player's turn; the session ends where the chosen lines end."""
        children, through = tree(s['lines'])
        board = board_of(s)
        due = {l for l, r in reviews(con, s['color']).items() if r['due_at'] <= now() or r['streak'] == 0}
        counts = met(con, s['color'])
        while children.get(board.epd()) and not mine(s, board):
            options = weights(children, through, board.epd(), due, counts, s['target'])
            uci = random.choices(list(options), weights=list(options.values()))[0]
            board.push_uci(uci)
            s['moves'].append(uci)
        if not children.get(board.epd()):
            finish(con, s, board, through)
        return board

    def finish(con, s, board, through):
        ends = sorted(through.get(board.epd(), ()), key=lambda l: (len(LINE[l]['moves']) != len(s['moves']), l))
        s['status'], s['finished_at'] = 'complete', now()
        s['line_id'] = ends[0] if ends else None
        if not s['line_id']:
            return
        success = not s['errors'] and not s['hints']
        key = f"{s['line_id']}:{s['color']}"
        row = con.execute('SELECT * FROM opening_line_reviews WHERE id=?', (key,)).fetchone()
        # Only a review that is due (or the first one) moves the schedule; earlier repetitions are practice.
        independent = row is None or row['due_at'] <= now()
        if independent:
            stage = min((row['streak'] if row else 0) + 1, len(training_schedule.INTERVAL_HOURS)) if success else 0
            hours = training_schedule.INTERVAL_HOURS[stage - 1] if success else 4
            due_at = (datetime.fromisoformat(now()) + timedelta(hours=hours)).isoformat()
            con.execute('''INSERT INTO opening_line_reviews(id,line_id,color,streak,due_at,last_at,reviews,failures) VALUES(?,?,?,?,?,?,1,?)
                ON CONFLICT(id) DO UPDATE SET streak=excluded.streak,due_at=excluded.due_at,last_at=excluded.last_at,
                reviews=reviews+1,failures=failures+excluded.failures''', (key, s['line_id'], s['color'], stage, due_at, now(), int(not success)))
        con.execute('INSERT OR IGNORE INTO training_reviews VALUES(?,?,?,?,?,?)', ('line', key, s['id'], now(), int(success), int(independent)))
        s['independent'] = independent

    def view(con, s, board, wrong=None, reply=None):
        line = LINE.get(s['line_id']) if s['line_id'] else None
        review = con.execute('SELECT * FROM opening_line_reviews WHERE id=?', (f"{s['line_id']}:{s['color']}",)).fetchone() if line else None
        ply = len(s['moves'])
        shown = s['status'] == 'active' and (str(ply) in s['hints'] or str(ply) in s['errors'])
        return {'id': s['id'], 'family': s['family'], 'familyName': FAMILY[s['family']]['name'], 'color': s['color'],
                'status': s['status'], 'version': ply, 'fen': board.fen(), 'moves': s['moves'], 'sans': sans(s['moves']),
                'turn': 'w' if board.turn else 'b', 'legalMoves': [m.uci() for m in board.legal_moves] if s['status'] == 'active' else [],
                'errors': [{'ply': int(p), 'played': v['played'], 'expected': v['expected']} for p, v in sorted(s['errors'].items(), key=lambda x: int(x[0]))],
                'hints': len(s['hints']), 'expected': expected(s, board) if shown else None, 'wrong': wrong, 'reply': reply,
                'target': LINE[s['target']]['name'] if s['target'] in LINE else None,
                'line': {'id': line['id'], 'name': line['name']} if line else None,
                'review': {'streak': review['streak'], 'dueAt': review['due_at']} if review else None,
                'independent': s.get('independent')}

    @app.get('/api/opening-lines')
    def catalog(color: str = 'w'):
        if color not in ('w', 'b'):
            raise HTTPException(422, 'Colore non valido')
        with database() as con:
            counts, done = met(con, color), reviews(con, color)
        out = []
        for family in FAMILY.values():
            ends = set(terminal(family['id']))
            board = chess.Board()
            for uci in family['rootMoves']:
                board.push_uci(uci)
            lines = [{'id': l['id'], 'name': l['name'], 'sans': sans(l['moves']), 'fen': l['fen'], 'met': counts[l['id']],
                      'terminal': l['id'] in ends,
                      'review': {k: done[l['id']][k] for k in ('streak', 'reviews', 'failures')} | {'dueAt': done[l['id']]['due_at'], 'due': done[l['id']]['due_at'] <= now()} if l['id'] in done else None}
                     for l in family['lines']]
            out.append({'id': family['id'], 'name': family['name'], 'description': family['description'], 'fen': board.fen(),
                        'games': counts['family:' + family['id']], 'lines': lines})
        return out

    @app.post('/api/opening-lines/sessions')
    def start(body: LineStart):
        target = body.target if body.target in LINE else None
        family = LINE[target]['family'] if target else body.family
        if family not in FAMILY:
            raise HTTPException(404, 'Apertura non trovata')
        ends = terminal(family)
        chosen = [l for l in (body.lines or ends) if l in ends] or ends
        if target:
            # A line opened from the plan is always included, with the lines it passes through.
            chosen = sorted(set(chosen) | {l for l in ends if LINE[l]['moves'][:len(LINE[target]['moves'])] == LINE[target]['moves']})
        s = {'id': str(uuid.uuid4()), 'family': family, 'color': body.color, 'lines': chosen, 'target': target, 'moves': [],
             'errors': {}, 'hints': {}, 'status': 'active', 'line_id': None, 'finished_at': None}
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('''INSERT INTO opening_line_sessions(id,family,color,lines,target,moves,errors,hints,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?)''', (s['id'], family, body.color, json.dumps(chosen), target, '[]', '{}', '{}', now()))
            board = advance(con, s)
            save(con, s)
            return view(con, s, board)

    @app.get('/api/opening-lines/sessions/{session_id}')
    def read(session_id: str):
        with database() as con:
            s = load(con, session_id)
            return view(con, s, board_of(s))

    def active(con, session_id, version):
        s = load(con, session_id)
        if s['status'] != 'active' or version != len(s['moves']):
            raise HTTPException(409, 'La sessione è cambiata: riaprila per continuare.')
        return s

    @app.post('/api/opening-lines/sessions/{session_id}/move')
    def move(session_id: str, body: LineMove):
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            s = active(con, session_id, body.version)
            board = board_of(s)
            chosen = chess.Move.from_uci(body.move)
            if chosen not in board.legal_moves:
                raise HTTPException(422, 'Mossa non legale')
            children, _ = tree(s['lines'])
            book = children.get(board.epd(), {})
            board.push(chosen)
            after = board.epd()
            board.pop()
            if after not in book.values():
                # Out of book: the move is not played; the error counts once per position, with every move tried.
                played, entry = board.san(chosen), s['errors'].setdefault(str(len(s['moves'])), {'played': [], 'expected': expected(s, board)})
                if played not in entry['played']:
                    entry['played'].append(played)
                save(con, s)
                return view(con, s, board, wrong={'san': played, 'expected': entry['expected']})
            s['moves'].append(next(uci for uci, epd in book.items() if epd == after))
            mark = len(s['moves'])
            board = advance(con, s)
            save(con, s)
            reply = s['moves'][mark] if len(s['moves']) > mark else None
            return view(con, s, board, reply=reply)

    @app.post('/api/opening-lines/sessions/{session_id}/hint')
    def hint(session_id: str, body: LineVersion):
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            s = active(con, session_id, body.version)
            s['hints'][str(len(s['moves']))] = True
            save(con, s)
            return view(con, s, board_of(s))
