"""Transparent spaced review, shared by puzzles and blunder prevention."""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from pydantic import BaseModel, Field

INTERVAL_HOURS = [4, 24, 72, 168, 336, 720, 2160, 4320]
TABLES = {'puzzle': 'exercises', 'prevention': 'prevention_positions'}


def init_schema(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS training_settings(id INTEGER PRIMARY KEY CHECK(id=1), minutes INTEGER NOT NULL,
      new_limit INTEGER NOT NULL, weekdays TEXT NOT NULL, timezone TEXT NOT NULL);
    INSERT OR IGNORE INTO training_settings VALUES(1,15,3,'[0,1,2,3,4,5,6]','Europe/Rome');
    CREATE TABLE IF NOT EXISTS training_reviews(kind TEXT NOT NULL,target_id TEXT NOT NULL,session_id TEXT NOT NULL,
      created_at TEXT NOT NULL,success INTEGER NOT NULL,independent INTEGER NOT NULL,
      PRIMARY KEY(kind,session_id));
    CREATE TABLE IF NOT EXISTS training_memory(kind TEXT NOT NULL,target_id TEXT NOT NULL,
      review_after TEXT NOT NULL,PRIMARY KEY(kind,target_id));
    ''')


def eligible(con, kind, target_id, timestamp):
    row = con.execute('SELECT review_after FROM training_memory WHERE kind=? AND target_id=?', (kind,target_id)).fetchone()
    return not row or row['review_after'] <= timestamp


def record(con, kind, row, session, success, assisted, timestamp):
    """Record the first answer once. Retries never promote a review stage."""
    first = session['guesses'] == 0
    independent = first and session['exposure'] != 'practice' and eligible(con,kind,row['id'],timestamp)
    if not first:
        return False
    inserted = con.execute('INSERT OR IGNORE INTO training_reviews VALUES(?,?,?,?,?,?)',
        (kind,row['id'],session['id'],timestamp,int(success and not assisted),int(independent)))
    if not inserted.rowcount or not independent:
        return False
    promoted = success and not assisted
    stage = min(row['streak']+1,len(INTERVAL_HOURS)) if promoted else 0
    delay = INTERVAL_HOURS[stage-1] if promoted else 4
    next_review = (datetime.fromisoformat(timestamp)+timedelta(hours=delay)).isoformat()
    # Failed exercises remain in the user's due list; only their independent retest waits.
    due = next_review if promoted else min(row['due_at'],timestamp)
    con.execute(f'UPDATE {TABLES[kind]} SET streak=?,due_at=? WHERE id=?',(stage,due,row['id']))
    con.execute('INSERT OR REPLACE INTO training_memory VALUES(?,?,?)',(kind,row['id'],next_review))
    return promoted


class Settings(BaseModel):
    minutes: int = Field(ge=5,le=60)
    newLimit: int = Field(ge=0,le=10)
    weekdays: list[int] = Field(min_length=1,max_length=7)
    timezone: str = Field(default='Europe/Rome',max_length=80)


def settings_view(row):
    return {'minutes':row['minutes'],'newLimit':row['new_limit'],'weekdays':json.loads(row['weekdays']),'timezone':row['timezone']}


def plan(con, timestamp):
    settings = settings_view(con.execute('SELECT * FROM training_settings WHERE id=1').fetchone())
    zone = ZoneInfo(settings['timezone']);current = datetime.fromisoformat(timestamp);today = current.astimezone(zone).date()
    start = datetime.combine(today,datetime.min.time(),zone).astimezone(timezone.utc).isoformat()
    end = datetime.combine(today+timedelta(days=1),datetime.min.time(),zone).astimezone(timezone.utc).isoformat()
    today_rows = con.execute('SELECT * FROM training_reviews WHERE created_at>=? AND created_at<?',(start,end)).fetchall()
    independent = [r for r in today_rows if r['independent']]
    seen_today = {(r['kind'],r['target_id']) for r in independent}
    rows=[]
    for kind,table in TABLES.items():
        where='WHERE e.enabled=1' if kind=='prevention' else ''
        for r in con.execute(f'''SELECT e.*,g.title AS game_title,g.pgn_headers AS headers,
          m.review_after,(SELECT count(*) FROM training_reviews v WHERE v.kind=? AND v.target_id=e.id AND v.independent=1) AS reviews
          FROM {table} e JOIN games g ON g.id=e.game_id
          LEFT JOIN training_memory m ON m.kind=? AND m.target_id=e.id {where}''',(kind,kind)):
            ready_at=max(r['due_at'],r['review_after'] or r['due_at'])
            rows.append({'kind':kind,'id':r['id'],'gameId':r['game_id'],'ply':r['ply'],
              'title':r['game_title'],'theme':r['theme'] if kind=='puzzle' else 'Evita il blunder',
              'stage':r['streak'],'dueAt':r['due_at'],'readyAt':ready_at,'new':not r['reviews'] and r['streak']==0})
    rows.sort(key=lambda r:(r['new'],r['readyAt'],r['id']))
    ready=[r for r in rows if r['readyAt']<=timestamp]
    # Do not prescribe the same decision twice through puzzle and prevention.
    queue=[];positions=set();new_count=0
    total_target=max(1,settings['minutes']//2)
    new_done=0
    for r in independent:
        older=con.execute('SELECT 1 FROM training_reviews WHERE kind=? AND target_id=? AND independent=1 AND created_at<?',
                          (r['kind'],r['target_id'],r['created_at'])).fetchone()
        if not older:new_done+=1
        item=next((x for x in rows if x['kind']==r['kind'] and x['id']==r['target_id']),None)
        if item:positions.add((item['gameId'],item['ply']))
    active=today.weekday() in settings['weekdays']
    for r in ready:
        identity=(r['gameId'],r['ply'])
        if not active or len(queue)>=max(0,total_target-len(independent)):break
        if identity in positions or (r['kind'],r['id']) in seen_today:continue
        if r['new'] and new_count+new_done>=settings['newLimit']:continue
        queue.append(r);positions.add(identity);new_count+=int(r['new'])
    calendar=[]
    for offset in range(7):
        day=today+timedelta(days=offset)
        due=sum(datetime.fromisoformat(r['readyAt']).astimezone(zone).date()==day or
                (offset==0 and datetime.fromisoformat(r['readyAt']).astimezone(zone).date()<day) for r in rows)
        calendar.append({'date':day.isoformat(),'planned':day.weekday() in settings['weekdays'],'due':due})
    return {'settings':settings,'today':today.isoformat(),'activeDay':active,'target':total_target,
      'completed':len(independent),'successful':sum(r['success'] for r in independent),
      'practice':len(today_rows)-len(independent),'ready':len(ready),'waiting':sum(r['dueAt']<=timestamp<r['readyAt'] for r in rows),
      'queue':queue,'calendar':calendar,'nextDue':min((r['readyAt'] for r in rows if r['readyAt']>timestamp),default=None),
      'intervalHours':INTERVAL_HOURS,'total':len(rows)}


def install(app,database,now):
    @app.get('/api/training-plan')
    def get_plan():
        with database() as con:return plan(con,now())

    @app.post('/api/training-plan/settings')
    def save_settings(body:Settings):
        if any(d<0 or d>6 for d in body.weekdays) or len(set(body.weekdays))!=len(body.weekdays):
            raise HTTPException(422,'Seleziona giorni della settimana validi.')
        try:ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError,ValueError):raise HTTPException(422,'Fuso orario non valido.')
        with database() as con:
            con.execute('UPDATE training_settings SET minutes=?,new_limit=?,weekdays=?,timezone=? WHERE id=1',
                        (body.minutes,body.newLimit,json.dumps(sorted(body.weekdays)),body.timezone))
            return plan(con,now())
