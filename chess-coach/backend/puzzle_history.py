"""What the attempts of own puzzles say beyond the first try: which hint did not suffice, which wrong idea comes back."""
import chess

# Stable keys of the graduated hints, in the order they are given.
HINT_ORDER = ['kind', 'motif', 'tempting', 'candidates', 'square']
HINT_KEYS = {'Motivo': 'motif', 'La mossa che tenta': 'tempting', 'Mosse candidate': 'candidates', 'Dove guardare': 'square'}
# A puzzle stays persistent while a wrong move repeated from an earlier session is among its last sessions.
PERSISTENT_SESSIONS = 3
# Highest review stage of a persistent puzzle: back within a day instead of three days or more.
PERSISTENT_STAGE = 2
WINDOW = 300


def hint_key(title):
    return HINT_KEYS.get(title, 'kind')


def migrate(con):
    columns = {r[1] for r in con.execute('PRAGMA table_info(attempts)')}
    for name, declaration in {'hint_level': 'INTEGER NOT NULL DEFAULT 0', 'hint': 'TEXT'}.items():
        if name not in columns:
            con.execute(f'ALTER TABLE attempts ADD COLUMN {name} {declaration}')
    if 'last_hint' not in {r[1] for r in con.execute('PRAGMA table_info(puzzle_sessions)')}:
        con.execute('ALTER TABLE puzzle_sessions ADD COLUMN last_hint TEXT')


def wrong_moves(con, exercise_id):
    """(session id, move, time) of the wrong guesses on the same position, oldest first, duplicates of the position included."""
    return [tuple(r) for r in con.execute('''SELECT a.session_id, a.move, a.created_at FROM attempts a JOIN exercises e ON e.id=a.exercise_id
        WHERE e.position_key=(SELECT position_key FROM exercises WHERE id=?) AND a.success=0 AND a.move!='reveal' AND a.session_id IS NOT NULL
        ORDER BY a.id''', (exercise_id,))]


def repeated(con, exercise_id, session_id, move):
    """The earlier sessions in which the same wrong move was played on this position: count and last time, or None."""
    earlier = [(s, at) for s, m, at in wrong_moves(con, exercise_id) if m == move and s != session_id]
    return {'sessions': len({s for s, _ in earlier}), 'at': earlier[-1][1]} if earlier else None


def repeating_sessions(con, exercise_id):
    """Sessions that replayed a wrong move already played on the position in an earlier session."""
    seen, found = {}, set()
    for s, m, _ in wrong_moves(con, exercise_id):
        if any(other != s for other in seen.get(m, ())):
            found.add(s)
        seen.setdefault(m, set()).add(s)
    return found


def persistent(con, exercise_id):
    last = [r[0] for r in con.execute('''SELECT s.id FROM puzzle_sessions s JOIN exercises e ON e.id=s.exercise_id
        WHERE e.position_key=(SELECT position_key FROM exercises WHERE id=?) AND s.guesses>0 ORDER BY s.created_at DESC LIMIT ?''',
        (exercise_id, PERSISTENT_SESSIONS))]
    return bool(repeating_sessions(con, exercise_id) & set(last))


def hint_outcomes(con):
    """For each kind of hint, in the sessions where it was the last one seen: the next guess solved, the next guess still
    wrong, or the solution asked without another guess. Sessions before hints were recorded per guess are left out."""
    rows = con.execute('''SELECT s.id, s.status, s.last_hint, a.hint, a.success FROM puzzle_sessions s LEFT JOIN attempts a
        ON a.session_id=s.id AND a.hint IS NOT NULL AND a.move!='reveal' WHERE s.id IN (SELECT id FROM puzzle_sessions
        WHERE last_hint IS NOT NULL ORDER BY created_at DESC LIMIT ?) ORDER BY a.id''', (WINDOW,)).fetchall()
    first, sessions = {}, {}
    for r in rows:
        sessions[r['id']] = (r['status'], r['last_hint'])
        if r['hint'] is not None:
            first.setdefault((r['id'], r['hint']), bool(r['success']))
    out = {k: {'key': k, 'solved': 0, 'wrong': 0, 'revealed': 0} for k in HINT_ORDER}
    for (_, key), success in first.items():
        out[key]['solved' if success else 'wrong'] += 1
    for ident, (status, last) in sessions.items():
        if status == 'revealed' and (ident, last) not in first:
            out[last]['revealed'] += 1
    return [o for o in out.values() if o['solved'] + o['wrong'] + o['revealed']]


def repeated_errors(con):
    """Positions where a wrong move came back in two or more sessions, still persistent first."""
    groups = {}
    for r in con.execute('''SELECT e.id, e.position_key, e.retired, e.theme, a.move, a.session_id, a.created_at FROM attempts a
        JOIN exercises e ON e.id=a.exercise_id WHERE a.success=0 AND a.move!='reveal' AND a.session_id IS NOT NULL ORDER BY a.id'''):
        g = groups.setdefault((r['position_key'], r['move']), {'sessions': set(), 'last': '', 'ids': {}, 'theme': r['theme']})
        g['sessions'].add(r['session_id'])
        g['last'] = r['created_at']
        g['ids'][r['id']] = r['retired']
    out, flags = [], {}
    for (key, move), g in groups.items():
        if len(g['sessions']) < 2 or not key:
            continue
        # Open the live puzzle of the position: duplicates and retired copies keep their old attempts.
        ident = next((i for i, retired in g['ids'].items() if retired is None), next(iter(g['ids'])))
        if ident not in flags:
            flags[ident] = persistent(con, ident)
        board = chess.Board(key + ' 0 1')
        out.append({'exercise': ident, 'move': move, 'san': board.san(chess.Move.from_uci(move)), 'sessions': len(g['sessions']),
                    'last': g['last'], 'theme': g['theme'], 'persistent': flags[ident], 'retired': g['ids'][ident]})
    out.sort(key=lambda x: x['last'], reverse=True)
    return sorted(out, key=lambda x: not x['persistent'])[:20]
