"""Decision quality and recorded position judgments; never an Elo estimator."""
import hashlib
import json
import random
import uuid

import chess
from fastapi import HTTPException


def init_schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS position_judgments(
        id TEXT PRIMARY KEY, position_key TEXT NOT NULL UNIQUE,
        game_id TEXT NOT NULL REFERENCES games(id), ply INTEGER NOT NULL,
        fen TEXT NOT NULL, evidence TEXT NOT NULL, created_at TEXT NOT NULL,
        answer TEXT, answered_at TEXT)''')


def decisions(row, start=0):
    if not row['analysis'] or row['analysis_version'] != len(json.loads(row['moves'])):
        return []
    # Recheck perspective and scope, including legacy analyses and black-to-move FENs.
    return [d for d in json.loads(row['analysis']).get('decisions', [])
            if d['ply'] >= start and not d.get('forced')
            and chess.Board(d['fen']).turn == (row['player_color'] == 'w')
            and chess.Board(d['fen']).legal_moves.count() > 1]


def value(e):
    mate = e.get('mate')
    return (100000 if mate > 0 else -100000) if mate is not None else e['cp']


def quality(items):
    opportunities = [d for d in items if value(d['best']) >= 150]
    return {'decisions': len(items), 'sound': sum(d['loss'] < 80 for d in items),
            'inaccuracies': sum(80 <= d['loss'] < 180 for d in items),
            'errors': sum(d['loss'] >= 180 for d in items),
            'advantages': len(opportunities),
            'maintained': sum(value(d['actual']) >= 150 for d in opportunities)}


def game_quality(con, row):
    drill = con.execute('SELECT start_ply FROM drill_sessions WHERE game_id=?', (row['id'],)).fetchone()
    items = decisions(row, drill['start_ply'] if drill else 0)
    return {**quality(items), 'ready': bool(row['analysis']) and row['analysis_version'] == len(json.loads(row['moves'])),
            'moments': [{'ply':d['ply'],'san':d['playedSan'],'loss':d['loss']} for d in sorted(items,key=lambda d:-d['loss'])[:3] if d['loss']>=80]}


def records(con):
    for row in con.execute('''SELECT g.*, COALESCE(d.start_ply,0) AS start_ply FROM games g
        LEFT JOIN drill_sessions d ON d.game_id=g.id WHERE g.analysis IS NOT NULL AND g.source!='snapshot'
        ORDER BY g.created_at DESC,g.id DESC'''):
        items = decisions(row, row['start_ply'])
        if items:
            yield row, items


def progress(con):
    groups = []
    all_records = list(records(con))
    for kind in ('games','drills'):
        selected = [(r, ds) for r, ds in all_records if (r['source']=='drill') == (kind=='drills')]
        windows = []
        for offset in (0,10):
            batch = selected[offset:offset+10]
            windows.append({'games':len(batch), **quality([d for _,ds in batch for d in ds])})
        groups.append({'kind':kind,'recent':windows[0],'previous':windows[1]})
    judgments = [json.loads(r['answer']) | {'evidence':json.loads(r['evidence'])}
                 for r in con.execute('SELECT answer,evidence FROM position_judgments WHERE answer IS NOT NULL')]
    # Familiar positions stay as practice, not first-exposure evidence.
    fresh = [j for j in judgments if not j['familiar']]
    return {'groups':groups, 'judgments':{'total':len(judgments),'fresh':len(fresh),
        'matched':sum(j['assessment']==category(j['evidence']) for j in fresh),
        'fearedLost':sum(j['fearedLost'] for j in fresh),
        'falseAlarms':sum(j['fearedLost'] and value(j['evidence'])>=-100 for j in fresh)}}


def category(e):
    cp = value(e)
    return 'much_worse' if cp<=-300 else 'worse' if cp < -100 else 'equal' if cp<=100 else 'better' if cp<300 else 'much_better'


def public_judgment(row):
    data = {k:row[k] for k in ('id','fen','ply')}
    data['color'] = 'w' if chess.Board(row['fen']).turn else 'b'
    if row['answer']:
        evidence=json.loads(row['evidence'])
        answer=json.loads(row['answer'])
        data.update(answer=answer, evidence=evidence, expected=category(evidence), gameId=row['game_id'],
                    falseAlarm=answer['fearedLost'] and value(evidence)>=-100)
    return data


def next_judgment(con, timestamp):
    pending = con.execute('SELECT * FROM position_judgments WHERE answer IS NULL LIMIT 1').fetchone()
    if pending:
        return public_judgment(pending)
    used={r[0] for r in con.execute('SELECT position_key FROM position_judgments')}
    buckets={}
    for row, items in records(con):
        # Do not expose engine feedback for an ongoing local sparring session.
        if row['source'] in ('maia','drill') and not row['termination']:
            board=chess.Board(row['initial_fen'])
            for move in json.loads(row['moves']): board.push_uci(move)
            session=con.execute('SELECT target,start_ply FROM drill_sessions WHERE game_id=?',(row['id'],)).fetchone()
            if not board.is_game_over() and not (session and len(items)>=session['target']):
                continue
        for d in items:
            if d['best'].get('perspective') != row['player_color']:
                continue
            # Exclude already used positions even if imported twice or at another move number.
            key=hashlib.sha256(' '.join(d['fen'].split()[:4]).encode()).hexdigest()
            if key not in used:
                buckets.setdefault(category(d['best']),[]).append((row,d,key))
    if not buckets:
        return None
    # Sample categories, not mistakes: a position can be good, equal, or bad.
    row,d,key=random.choice(buckets[random.choice(list(buckets))])
    identity=str(uuid.uuid4())
    con.execute('INSERT INTO position_judgments(id,position_key,game_id,ply,fen,evidence,created_at) VALUES(?,?,?,?,?,?,?)',
                (identity,key,row['id'],d['ply'],d['fen'],json.dumps(d['best']),timestamp))
    return public_judgment(con.execute('SELECT * FROM position_judgments WHERE id=?',(identity,)).fetchone())


def answer_judgment(con, identity, answer, timestamp):
    row=con.execute('SELECT * FROM position_judgments WHERE id=?',(identity,)).fetchone()
    if row is None:
        raise HTTPException(404,'Posizione non trovata')
    if row['answer']:
        if json.loads(row['answer']) != answer:
            raise HTTPException(409,'La prima valutazione è già stata salvata: passa alla prossima posizione.')
        return public_judgment(row)
    con.execute('UPDATE position_judgments SET answer=?,answered_at=? WHERE id=?', (json.dumps(answer),timestamp,identity))
    return public_judgment(con.execute('SELECT * FROM position_judgments WHERE id=?',(identity,)).fetchone())
