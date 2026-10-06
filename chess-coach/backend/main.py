"""Local single-user training, with an optional, explicitly invoked DeepSeek tutor."""
import hashlib
import io
import json
import os
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import chess
import chess.pgn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, FiniteFloat

from .engine import ROOT, evaluator
from .drills import CATALOG, materialize, decisions_played
from . import tutor
from . import prevention
from . import mistakes
from . import insights
from .rating import rating_plan, summarize_rating, RATING_LEVELS, RATING_METHOD

DB_PATH = Path(os.environ.get("CHESS_COACH_DATA", str(ROOT / "data"))) / "coach.sqlite3"
jobs = {}
jobs_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
tutor_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS games(
          id TEXT PRIMARY KEY, initial_fen TEXT NOT NULL, moves TEXT NOT NULL,
          player_color TEXT NOT NULL, elo INTEGER NOT NULL, title TEXT NOT NULL,
          created_at TEXT NOT NULL, analysis TEXT, analysis_version INTEGER, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS exercises(
          id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id), ply INTEGER NOT NULL,
          initial_fen TEXT NOT NULL, history TEXT NOT NULL, theme TEXT NOT NULL,
          best_move TEXT NOT NULL, loss INTEGER NOT NULL, due_at TEXT NOT NULL,
          streak INTEGER NOT NULL DEFAULT 0, hints INTEGER NOT NULL DEFAULT 0,
          UNIQUE(game_id, ply));
        CREATE TABLE IF NOT EXISTS attempts(
          id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_id TEXT NOT NULL REFERENCES exercises(id),
          move TEXT NOT NULL, success INTEGER NOT NULL, assisted INTEGER NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drill_sessions(
          game_id TEXT PRIMARY KEY REFERENCES games(id), template_id TEXT NOT NULL,
          template_name TEXT NOT NULL, theme TEXT NOT NULL, goal TEXT NOT NULL,
          start_ply INTEGER NOT NULL, target INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS puzzle_sessions(
          id TEXT PRIMARY KEY, exercise_id TEXT NOT NULL REFERENCES exercises(id),
          created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
          guesses INTEGER NOT NULL DEFAULT 0, hints INTEGER NOT NULL DEFAULT 0,
          exposure TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tutor_reviews(
          cache_key TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id),
          analysis_hash TEXT NOT NULL, created_at TEXT NOT NULL, response TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS game_ratings(
          game_id TEXT PRIMARY KEY REFERENCES games(id), version INTEGER NOT NULL,
          revision INTEGER NOT NULL, response TEXT NOT NULL);
        """)
        if 'revision' not in {r[1] for r in con.execute('PRAGMA table_info(games)')}:
            con.execute('ALTER TABLE games ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
        columns = {r[1] for r in con.execute('PRAGMA table_info(games)')}
        for name, declaration in {'move_times': "TEXT NOT NULL DEFAULT '[]'", 'pgn_headers': "TEXT NOT NULL DEFAULT '{}'", 'termination': 'TEXT'}.items():
            if name not in columns:
                con.execute(f'ALTER TABLE games ADD COLUMN {name} {declaration}')
        columns = {r[1] for r in con.execute("PRAGMA table_info(attempts)")}
        for name, declaration in {"session_id": "TEXT", "is_first": "INTEGER NOT NULL DEFAULT 0", "exposure": "TEXT NOT NULL DEFAULT 'legacy'"}.items():
            if name not in columns:
                con.execute(f"ALTER TABLE attempts ADD COLUMN {name} {declaration}")
        prevention.init_schema(con)
        mistakes.init_schema(con)
        for row in con.execute('SELECT * FROM games WHERE analysis IS NOT NULL').fetchall():
            if row['analysis_version'] == len(json.loads(row['moves'])):
                prevention.seed_game(con, row, json.loads(row['analysis']), now())


@asynccontextmanager
async def lifespan(app):
    global executor
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
    init_db()
    evaluator.start()
    try:
        yield
    finally:
        executor.shutdown(wait=True)
        evaluator.close()


app = FastAPI(title="SparringMate locale", lifespan=lifespan)


@app.middleware("http")
async def local_headers(request, call_next):
    # Reject cross-site writes to the unauthenticated loopback application.
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        from urllib.parse import urlsplit
        parsed = urlsplit(origin)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Origine non consentita"}, status_code=403)
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


class NewGame(BaseModel):
    color: Literal["w", "b"] = "w"
    elo: int = Field(default=1500, ge=600, le=2600)
    fen: str = Field(default=chess.STARTING_FEN, max_length=120)


class MoveInput(BaseModel):
    move: str = Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$")
    version: int = Field(ge=0, le=1000)
    actor: Literal["human", "maia"]
    revision: int = Field(default=0, ge=0)
    elapsed_seconds: FiniteFloat | None = Field(default=None, ge=0, le=604800)


class UndoInput(BaseModel):
    version: int = Field(ge=0, le=600)
    revision: int = Field(ge=0)


class RatingInput(UndoInput):
    method: Literal['maia3-drill-match-v2']
    log_scores: list[FiniteFloat] = Field(min_length=21, max_length=21)


class ImportInput(BaseModel):
    pgn: str = Field(min_length=1, max_length=100000)
    color: Literal["w", "b"] = "w"


class AttemptInput(BaseModel):
    move: str = Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$")
    session_id: str = Field(min_length=1, max_length=50)
    version: int = Field(ge=0)


class SessionInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=50)


class DrillInput(BaseModel):
    color: Literal["w", "b"] = "w"
    elo: int = Field(default=1500, ge=600, le=2600)
    target: int = Field(default=5, ge=3, le=12)


class TutorInput(BaseModel):
    version: int = Field(ge=0, le=600)
    reflection: str = Field(default='', max_length=2000)


def reconstruct(initial_fen, moves):
    try:
        board = chess.Board(initial_fen)
        if not board.is_valid():
            raise ValueError("Posizione non valida")
        for move in moves:
            board.push_uci(move)
        return board
    except ValueError as exc:
        raise HTTPException(422, "Posizione o sequenza di mosse non valida") from exc


def find_game(con, game_id):
    row = con.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Partita non trovata")
    return row


def game_pgn(row, include_times=True):
    moves = json.loads(row["moves"])
    board = reconstruct(row["initial_fen"], moves)
    pgn = chess.pgn.Game.from_board(board)
    stored_headers = json.loads(row['pgn_headers'])
    pgn.headers.update(stored_headers)
    if not stored_headers:
        pgn.headers['Event'] = row['title']
        pgn.headers['Site'] = 'SparringMate locale'
        pgn.headers['Date'] = row['created_at'][:10].replace('-', '.')
        pgn.headers['White'] = 'Tu' if row['player_color'] == 'w' else f"Maia {row['elo']}"
        pgn.headers['Black'] = f"Maia {row['elo']}" if row['player_color'] == 'w' else 'Tu'
        pgn.headers['TimeControl'] = '-'  # Free play, without a countdown clock.
    pgn.headers['GameId'] = row['id']
    outcome = board.outcome(claim_draw=True)
    pgn.headers['Result'] = outcome.result() if outcome else stored_headers.get('Result', '*')
    if row['termination'] == 'resign':
        pgn.headers['Result'] = '0-1' if row['player_color'] == 'w' else '1-0'
        pgn.headers['Termination'] = 'normal'
        pgn.headers['Resignation'] = 'White' if row['player_color'] == 'w' else 'Black'
    if include_times:
        for node, timing in zip(pgn.mainline(), json.loads(row['move_times'])):
            if timing:
                if timing.get('emt') is not None:
                    node.set_emt(timing['emt'])
                if timing.get('clk') is not None:
                    node.set_clock(timing['clk'])
    return pgn


def game_view(row):
    moves = json.loads(row['moves'])
    board = reconstruct(row['initial_fen'], moves)
    pgn = game_pgn(row)
    outcome = board.outcome(claim_draw=True)
    with jobs_lock:
        analysis_job = next((key for key, job in reversed(list(jobs.items()))
                             if job['gameId'] == row['id'] and job.get('version') == len(moves)
                             and job.get('revision') == row['revision']
                             and (job['status'] == 'running' or row['analysis_version'] != len(moves))), None)
    with database() as con:
        session = con.execute("SELECT * FROM drill_sessions WHERE game_id=?", (row["id"],)).fetchone()
        rating = con.execute('SELECT response FROM game_ratings WHERE game_id=? AND version=? AND revision=?',
                             (row['id'], len(moves), row['revision'])).fetchone()
    drill = None
    if session:
        count = decisions_played(row["initial_fen"], moves, session["start_ply"], row["player_color"])
        drill = {"name": session["template_name"], "goal": session["goal"], "theme": session["theme"],
                 "target": session["target"], "decisions": count, "startPly": session["start_ply"],
                 "complete": count >= session["target"] or outcome is not None}
    return {"id": row["id"], "fen": board.fen(), "initialFen": row["initial_fen"],
            "moves": moves, "version": len(moves), "revision": row['revision'], "playerColor": row["player_color"],
            "canUndo": not row['termination'] and row['source'] in {'maia', 'drill'} and undo_ply(row, session) is not None,
            "termination": row['termination'],
            "rating": json.loads(rating['response']) if rating else None, "analysisJobId": analysis_job,
            "elo": row["elo"], "title": row["title"], "pgn": str(pgn),
            "timedMoves": sum(bool(t) for t in json.loads(row['move_times'])),
            "turn": "w" if board.turn else "b", "legalMoves": [m.uci() for m in board.legal_moves],
            "result": pgn.headers['Result'] if pgn.headers['Result'] != '*' else None, "source": row["source"], "drill": drill,
            "analysis": insights.enrich(json.loads(row["analysis"])) if row["analysis"] and row["analysis_version"] == len(moves) else None}


@app.get("/api/health")
def health():
    return {"status": "ok", "stockfish": evaluator.name, "storage": "SQLite locale",
            "maia": "maia3_simplified.onnx · browser"}


@app.post("/api/games")
def new_game(body: NewGame):
    reconstruct(body.fen, [])
    game_id = str(uuid.uuid4())
    with database() as con:
        con.execute("INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (game_id, body.fen, "[]", body.color, body.elo, f"Allenamento con Maia {body.elo}", now(), None, None, "maia"))
        return game_view(find_game(con, game_id))


@app.get("/api/games")
def games():
    with database() as con:
        rows = con.execute("SELECT * FROM games ORDER BY created_at DESC LIMIT 50").fetchall()
        return [{"id": r["id"], "title": r["title"], "createdAt": r["created_at"],
                 "plies": len(json.loads(r["moves"])), "source": r["source"]} for r in rows]


@app.get("/api/games/{game_id}")
def get_game(game_id: str):
    with database() as con:
        return game_view(find_game(con, game_id))


@app.post("/api/games/{game_id}/moves")
def make_move(game_id: str, body: MoveInput):
    with database() as con:
        con.execute("BEGIN IMMEDIATE")
        row = find_game(con, game_id)
        if row["source"] not in {"maia", "drill"}:
            raise HTTPException(409, "La partita importata è disponibile in revisione")
        moves = json.loads(row["moves"])
        if len(moves) != body.version or row['revision'] != body.revision:
            raise HTTPException(409, "La posizione è cambiata: ricarica la partita")
        board = reconstruct(row["initial_fen"], moves)
        session = con.execute("SELECT * FROM drill_sessions WHERE game_id=?", (game_id,)).fetchone()
        if session and decisions_played(row["initial_fen"], moves, session["start_ply"], row["player_color"]) >= session["target"]:
            raise HTTPException(409, "Drill completato: apri la revisione")
        if row['termination'] or board.is_game_over(claim_draw=True) or len(moves) >= 600:
            raise HTTPException(409, "Partita conclusa")
        player_turn = board.turn == (row["player_color"] == "w")
        if player_turn != (body.actor == "human"):
            raise HTTPException(409, "Attendi il tuo turno")
        move = chess.Move.from_uci(body.move)
        if move not in board.legal_moves:
            raise HTTPException(422, "Mossa non legale")
        moves.append(body.move)
        times = json.loads(row['move_times'])
        times = (times + [None] * body.version)[:body.version]
        times.append({'emt': round(body.elapsed_seconds, 3)} if body.elapsed_seconds is not None else None)
        con.execute("UPDATE games SET moves=?,move_times=? WHERE id=?", (json.dumps(moves), json.dumps(times), game_id))
        snapshot = dict(find_game(con, game_id))
    # Commit the final move before the worker reads it; analysis survives closing the browser.
    board.push(move)
    if board.is_game_over(claim_draw=True):
        queue_analysis(snapshot, automatic=True)
    return get_game(game_id)


@app.post('/api/games/{game_id}/resign')
def resign_game(game_id: str, body: UndoInput):
    with database() as con:
        con.execute('BEGIN IMMEDIATE')
        row = find_game(con, game_id)
        moves = json.loads(row['moves'])
        board = reconstruct(row['initial_fen'], moves)
        if row['source'] != 'maia' or row['termination'] or board.is_game_over(claim_draw=True):
            raise HTTPException(409, 'Questa partita non può essere abbandonata: è già conclusa o disponibile solo in revisione')
        # A Maia reply may have committed while the player confirmed resignation.
        bot_reply = len(moves) == body.version + 1 and reconstruct(row['initial_fen'], moves[:body.version]).turn != (row['player_color'] == 'w')
        if row['revision'] != body.revision or not (len(moves) == body.version or bot_reply):
            raise HTTPException(409, 'La partita è cambiata: ricaricala prima di abbandonare')
        con.execute("UPDATE games SET termination='resign',revision=revision+1 WHERE id=?", (game_id,))
        snapshot = dict(find_game(con, game_id))
    if moves:
        queue_analysis(snapshot, automatic=True)
    return get_game(game_id)


@app.get('/api/games/{game_id}/pgn')
def export_pgn(game_id: str, include_times: bool = True):
    with database() as con:
        row = find_game(con, game_id)
        pgn = game_pgn(row, include_times)
    return Response(str(pgn) + '\n', media_type='application/x-chess-pgn',
                    headers={'Content-Disposition': f'attachment; filename="sparringmate-{row["id"]}.pgn"'})


def undo_ply(row, session=None):
    moves = json.loads(row['moves'])
    start = session['start_ply'] if session else 0
    initial_turn = chess.Board(row['initial_fen']).turn
    return next((ply for ply in range(len(moves) - 1, start - 1, -1)
                 if (initial_turn if ply % 2 == 0 else not initial_turn) == (row['player_color'] == 'w')), None)


def preserve_review(con, row, session):
    # Keep previously reviewed evidence and puzzle attempts attached to their original line.
    if not row['analysis'] and not con.execute('SELECT 1 FROM exercises WHERE game_id=?', (row['id'],)).fetchone():
        return
    archive_id = str(uuid.uuid4())
    con.execute('''INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source,revision)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        (archive_id, row['initial_fen'], row['moves'], row['player_color'], row['elo'],
         row['title'] + ' · prima dell’annullamento', now(), row['analysis'], row['analysis_version'], 'snapshot', row['revision']))
    con.execute('UPDATE games SET move_times=?,pgn_headers=? WHERE id=?', (row['move_times'], row['pgn_headers'], archive_id))
    if session:
        con.execute('INSERT INTO drill_sessions VALUES(?,?,?,?,?,?,?)',
                    (archive_id, session['template_id'], session['template_name'], session['theme'], session['goal'], session['start_ply'], session['target']))
    con.execute('UPDATE exercises SET game_id=? WHERE game_id=?', (archive_id, row['id']))
    con.execute('UPDATE tutor_reviews SET game_id=? WHERE game_id=?', (archive_id, row['id']))
    con.execute('UPDATE game_ratings SET game_id=? WHERE game_id=?', (archive_id, row['id']))
    con.execute('UPDATE prevention_positions SET game_id=? WHERE game_id=?', (archive_id, row['id']))


@app.post('/api/games/{game_id}/undo')
def undo_move(game_id: str, body: UndoInput):
    with database() as con:
        con.execute('BEGIN IMMEDIATE')
        row = find_game(con, game_id)
        if row['termination'] or row['source'] not in {'maia', 'drill'}:
            raise HTTPException(409, 'Questa partita è disponibile solo in revisione')
        moves = json.loads(row['moves'])
        session = con.execute('SELECT * FROM drill_sessions WHERE game_id=?', (game_id,)).fetchone()
        ply = undo_ply(row, session)
        # A bot reply may have arrived after the click. Accept only that one extra reply.
        if row['revision'] != body.revision or len(moves) not in {body.version, body.version + 1} or ply is None or ply >= body.version:
            raise HTTPException(409, 'Nessuna mossa da annullare in questa posizione: ricarica la partita')
        preserve_review(con, row, session)
        con.execute('UPDATE games SET moves=?,move_times=?,revision=revision+1,analysis=NULL,analysis_version=NULL WHERE id=?',
                    (json.dumps(moves[:ply]), json.dumps(json.loads(row['move_times'])[:ply]), game_id))
        con.execute('DELETE FROM game_ratings WHERE game_id=?', (game_id,))
    return get_game(game_id)


@app.get('/api/games/{game_id}/rating-positions')
def prepare_rating(game_id: str):
    with database() as con:
        row = find_game(con, game_id)
        session = con.execute('SELECT * FROM drill_sessions WHERE game_id=?', (game_id,)).fetchone()
        return rating_plan(row, session)


@app.post('/api/games/{game_id}/rating')
def save_rating(game_id: str, body: RatingInput):
    with database() as con:
        con.execute('BEGIN IMMEDIATE')
        row = find_game(con, game_id)
        if row['revision'] != body.revision or len(json.loads(row['moves'])) != body.version:
            raise HTTPException(409, 'La partita è cambiata: ricalcola la stima Elo')
        session = con.execute('SELECT * FROM drill_sessions WHERE game_id=?', (game_id,)).fetchone()
        plan = rating_plan(row, session)
        if len(plan['positions']) < 10 or any(s > 0 or s < -2100 for s in body.log_scores):
            raise HTTPException(422, 'Servono almeno 10 tue decisioni e probabilità Maia valide')
        result = {**summarize_rating(body.log_scores, len(plan['positions'])), 'createdAt': now(), 'version': body.version,
                  'revision': body.revision, 'positions': len(plan['positions']), 'totalPositions': plan['totalPositions'],
                  'opponentMode': plan['opponentMode'], 'probabilityFloor': plan['probabilityFloor'],
                  'method': RATING_METHOD, 'levels': RATING_LEVELS, 'logScores': body.log_scores}
        con.execute('INSERT OR REPLACE INTO game_ratings VALUES(?,?,?,?)',
                    (game_id, body.version, body.revision, json.dumps(result)))
    return result


@app.post("/api/import")
def import_game(body: ImportInput):
    stream = io.StringIO(body.pgn)
    try:
        pgn = chess.pgn.read_game(stream)
        if pgn is None or pgn.errors:
            raise ValueError("PGN incompleto o mosse non valide")
        board = pgn.board()
        initial = board.fen()
        moves = [m.uci() for m in pgn.mainline_moves()]
        if not moves or len(moves) > 600:
            raise ValueError("Importa una partita con 1–600 semimosse")
        reconstruct(initial, moves)
        if chess.pgn.read_game(stream) is not None:
            raise ValueError("Importa una sola partita alla volta")
    except (ValueError, IndexError) as exc:
        raise HTTPException(422, str(exc)) from exc
    game_id = hashlib.sha256((initial + json.dumps(moves) + body.color).encode()).hexdigest()[:32]
    with database() as con:
        title = f"{pgn.headers.get('White', 'Bianco')} – {pgn.headers.get('Black', 'Nero')}"[:120]
        con.execute("INSERT OR IGNORE INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (game_id, initial, json.dumps(moves), body.color, 1500, title, now(), None, None, "pgn"))
        times = [{k: v for k, v in {'emt': n.emt(), 'clk': n.clock()}.items() if v is not None} or None for n in pgn.mainline()]
        # Reimporting the same line can enrich its metadata without replacing analysis.
        existing = find_game(con, game_id)
        old_times = json.loads(existing['move_times'])
        merged_times = [{**((old_times[i] or {}) if i < len(old_times) else {}), **(t or {})} or None for i, t in enumerate(times)]
        headers = {**json.loads(existing['pgn_headers']), **dict(pgn.headers)}
        con.execute('UPDATE games SET move_times=?,pgn_headers=? WHERE id=?', (json.dumps(merged_times), json.dumps(headers), game_id))
        return game_view(find_game(con, game_id))


def update_job(job_id, **changes):
    with jobs_lock:
        jobs[job_id].update(changes)


def analyze_game(job_id, snapshot):
    try:
        moves = json.loads(snapshot["moves"])
        board = reconstruct(snapshot["initial_fen"], [])
        with database() as con:
            drill = con.execute("SELECT * FROM drill_sessions WHERE game_id=?", (snapshot["id"],)).fetchone()
        start_ply = drill["start_ply"] if drill else 0
        decisions = []
        reviewed_moves = []
        for ply, uci in enumerate(moves):
            move = chess.Move.from_uci(uci)
            if ply >= start_ply:
                is_player = board.turn == (snapshot['player_color'] == 'w')
                forced = board.legal_moves.count() == 1
                best, actual, loss, choices = evaluator.compare_candidates(board, move, nodes=10000)
                if loss >= 80:
                    best, actual, loss, choices = evaluator.compare_candidates(board, move, nodes=60000)
                theme = "Calcolo e mosse candidate"
                if best["mate"] is not None and best["mate"] > 0 and (actual["mate"] is None or actual["mate"] < 0):
                    theme = "Riconoscere il matto"
                elif actual["mate"] is not None and actual["mate"] < 0 and (best["mate"] is None or best["mate"] > 0):
                    theme = "Difesa dalle minacce di matto"
                item = {"ply": ply, "fen": board.fen(), "played": uci, "playedSan": board.san(move),
                                  "best": best, "actual": actual, "loss": loss, "theme": theme,
                                  "stockfishCandidates": choices,
                                  "isPlayer": is_player, "forced": forced,
                                  "label": "Mossa obbligata" if forced else "Errore" if loss >= 180 else "Imprecisione" if loss >= 80 else "Buona scelta"}
                item['insight'] = insights.public(insights.compare(board.fen(), uci, best, actual))
                if theme == 'Calcolo e mosse candidate':
                    item['theme'] = {'tactical':'Conseguenze tattiche', 'mixed':'Tattica e posizione',
                                     'positional':'Valutare la posizione e scegliere un piano',
                                     'unclear':'Confrontare piani e varianti', 'neutral':theme}[item['insight']['kind']]
                reviewed_moves.append(item)
                if is_player and not forced:
                    decisions.append(item)
            board.push(move)
            update_job(job_id, progress=round((ply + 1) / len(moves) * 100))
        critical = sorted([d for d in decisions if d["loss"] >= 80], key=lambda d: -d["loss"])[:3]
        analysis = {"decisions": decisions, "moves": reviewed_moves, "reviewVersion": 3, "critical": critical, "engine": evaluator.name,
                    "createdAt": now(), "version": len(moves), "source": snapshot["source"], "note": "Analisi a budget limitato. Temi indicativi, non diagnosi definitive."}
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            current = find_game(con, snapshot['id'])
            if current['moves'] != snapshot['moves'] or current['revision'] != snapshot['revision']:
                raise ValueError('La partita è cambiata: riavvia l’analisi.')
            con.execute("UPDATE games SET analysis=?, analysis_version=? WHERE id=?",
                        (json.dumps(analysis), len(moves), snapshot["id"]))
            prevention.seed_game(con, snapshot, analysis, now())
            for item in critical:
                if not item["best"]["pv"]:
                    continue
                ex_id = f"{snapshot['id']}:{snapshot['revision']}:{item['ply']}"
                con.execute("""INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at)
                  VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(game_id,ply) DO UPDATE SET
                  best_move=excluded.best_move,loss=excluded.loss,theme=excluded.theme""",
                            (ex_id, snapshot["id"], item["ply"], snapshot["initial_fen"],
                             json.dumps(moves[:item["ply"]]), item["theme"], item["best"]["pv"][0], item["loss"], now()))
        update_job(job_id, status="complete", progress=100, result=analysis)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))


@app.post("/api/games/{game_id}/analysis")
def request_analysis(game_id: str):
    with database() as con:
        row = dict(find_game(con, game_id))
    return queue_analysis(row)


def queue_analysis(row, automatic=False):
    game_id = row['id']
    if not json.loads(row["moves"]):
        raise HTTPException(422, "Gioca almeno una mossa prima dell'analisi")
    with jobs_lock:
        for key, job in jobs.items():
            if job["gameId"] == game_id and job["status"] == "running" and job.get('version') == len(json.loads(row['moves'])) and job.get('revision') == row['revision']:
                return {"jobId": key}
        if not automatic and sum(j["status"] == "running" for j in jobs.values()) >= 4:
            raise HTTPException(429, "Ci sono già analisi in coda")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"gameId": game_id, "status": "running", "progress": 0,
                        "version": len(json.loads(row['moves'])), "revision": row['revision'], "automatic": automatic}
    executor.submit(analyze_game, job_id, row)
    return {"jobId": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(404, "Analisi non trovata: riavviala se il server è stato riavviato")
        return dict(jobs[job_id])


def exercise_view(row):
    board = reconstruct(row["initial_fen"], json.loads(row["history"]))
    return {"id": row["id"], "gameId": row["game_id"], "ply": row["ply"], "theme": row["theme"],
            "gameTitle": row['game_title'] if 'game_title' in row.keys() else None,
            "gameCreatedAt": row['game_created_at'] if 'game_created_at' in row.keys() else None,
            "fen": board.fen(), "turn": "w" if board.turn else "b", "dueAt": row["due_at"],
            "streak": row["streak"], "legalMoves": [m.uci() for m in board.legal_moves]}


def find_exercise(con, exercise_id):
    row = con.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Esercizio non trovato")
    return row


@app.get("/api/exercises")
def exercises():
    with database() as con:
        return [exercise_view(r) for r in con.execute("SELECT e.*,g.title AS game_title,g.created_at AS game_created_at FROM exercises e JOIN games g ON g.id=e.game_id ORDER BY e.due_at LIMIT 100")]


@app.post("/api/exercises/{exercise_id}/sessions")
def puzzle_session(exercise_id: str):
    session_id = str(uuid.uuid4())
    with database() as con:
        con.execute("BEGIN IMMEDIATE")
        ex = find_exercise(con, exercise_id)
        seen = con.execute("SELECT count(*) FROM puzzle_sessions WHERE exercise_id=?", (exercise_id,)).fetchone()[0]
        active = con.execute("SELECT * FROM puzzle_sessions WHERE exercise_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", (exercise_id,)).fetchone()
        if active:
            return {"id": active["id"], "version": active["guesses"], "exposure": active["exposure"]}
        exposure = "new" if not seen else "review" if ex["due_at"] <= now() else "practice"
        con.execute("INSERT INTO puzzle_sessions(id,exercise_id,created_at,exposure) VALUES(?,?,?,?)", (session_id, exercise_id, now(), exposure))
    return {"id": session_id, "version": 0, "exposure": exposure}


def active_session(con, exercise_id, session_id, version=None):
    session = con.execute("SELECT * FROM puzzle_sessions WHERE id=? AND exercise_id=?", (session_id, exercise_id)).fetchone()
    if session is None:
        raise HTTPException(404, "Sessione non trovata")
    if session["status"] != "active" or (version is not None and version != session["guesses"]):
        raise HTTPException(409, "Tentativo già registrato: seleziona di nuovo l'esercizio")
    return session


@app.post("/api/exercises/{exercise_id}/hint")
def hint(exercise_id: str, body: SessionInput):
    with database() as con:
        con.execute("BEGIN IMMEDIATE")
        active_session(con, exercise_id, body.session_id)
        con.execute("UPDATE puzzle_sessions SET hints=hints+1 WHERE id=?", (body.session_id,))
    return {"hint": "Prima di decidere: cerca gli scacchi, poi le catture e le minacce di entrambi i colori. Confronta almeno due mosse candidate."}


@app.post("/api/exercises/{exercise_id}/attempts")
def attempt(exercise_id: str, body: AttemptInput):
    with database() as con:
        row = dict(find_exercise(con, exercise_id))
        active_session(con, exercise_id, body.session_id, body.version)
    board = reconstruct(row["initial_fen"], json.loads(row["history"]))
    move = chess.Move.from_uci(body.move)
    if move not in board.legal_moves:
        raise HTTPException(422, "Mossa non legale")
    best, actual, loss = evaluator.compare(board, move, nodes=80000)
    success = loss <= 50
    with database() as con:
        con.execute("BEGIN IMMEDIATE")
        session = active_session(con, exercise_id, body.session_id, body.version)
        current = find_exercise(con, exercise_id)
        assisted = session["hints"] > 0
        first = session["guesses"] == 0
        due = current["due_at"]
        # Immediate retries and early practice never increase the independent streak.
        if first and session["exposure"] != "practice":
            streak = current["streak"] + 1 if success and not assisted else 0
            interval = [1, 3, 7, 14, 30][min(max(streak - 1, 0), 4)]
            due = (datetime.now(timezone.utc) + timedelta(days=interval)).isoformat()
            con.execute("UPDATE exercises SET streak=?,due_at=? WHERE id=?", (streak, due, exercise_id))
        inserted = con.execute("INSERT INTO attempts(exercise_id,move,success,assisted,created_at,session_id,is_first,exposure) VALUES(?,?,?,?,?,?,?,?)",
                    (exercise_id, body.move, int(success), int(assisted), now(), body.session_id, int(first), session["exposure"]))
        if not success:
            mistakes.record(con, 'puzzle', exercise_id, inserted.lastrowid, board, move, best, actual, now())
        con.execute("UPDATE puzzle_sessions SET guesses=guesses+1,status=? WHERE id=?", ("complete" if success else "active", body.session_id))
    return {"success": success, "assisted": assisted, "loss": loss, "best": best if success else None, "actual": actual,
            "insight": insights.public(insights.compare(board.fen(), body.move, best, actual)),
            "dueAt": due, "version": body.version + 1, "closed": success,
            "message": "Mossa valida: mantiene la qualità della posizione." if success else "C'è un'alternativa migliore. Puoi riprovare: il primo tentativo è già registrato."}


@app.post("/api/exercises/{exercise_id}/reveal")
def reveal(exercise_id: str, body: SessionInput):
    with database() as con:
        row = dict(find_exercise(con, exercise_id))
        active_session(con, exercise_id, body.session_id)
    best = evaluator.evaluate(reconstruct(row["initial_fen"], json.loads(row["history"])), nodes=80000)
    with database() as con:
        con.execute("BEGIN IMMEDIATE")
        session = active_session(con, exercise_id, body.session_id)
        if not session["guesses"]:
            con.execute("INSERT INTO attempts(exercise_id,move,success,assisted,created_at,session_id,is_first,exposure) VALUES(?,?,0,1,?,?,1,?)",
                        (exercise_id, "reveal", now(), body.session_id, session["exposure"]))
        due = find_exercise(con, exercise_id)["due_at"]
        if session["exposure"] != "practice":
            due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            con.execute("UPDATE exercises SET streak=0,due_at=? WHERE id=?", (due, exercise_id))
        con.execute("UPDATE puzzle_sessions SET status='revealed',hints=hints+1 WHERE id=?", (body.session_id,))
    return {"success": False, "assisted": True, "best": best, "actual": None, "loss": None, "dueAt": due,
            "version": session["guesses"], "closed": True, "message": "Soluzione mostrata. Riprova dopo una pausa per verificare cosa ricordi."}


@app.get("/api/drills")
def drill_catalog():
    with database() as con:
        history = [json.loads(r[0]) for r in con.execute("SELECT moves FROM games WHERE source IN ('maia','pgn')")]
        personal = con.execute("SELECT * FROM exercises ORDER BY due_at,loss DESC LIMIT 10").fetchall()
    result = []
    for template in CATALOG:
        _, moves, fen = materialize(template)
        matches = sum(bool(moves) and h[:len(moves)] == moves for h in history)
        result.append({**{k: template[k] for k in ('id','name','kind','theme','goal')}, "fen": fen,
                       "color": template.get("color"), "reason": f"Presente in {matches} tue partite." if matches else "Posizione del catalogo iniziale."})
    for ex in personal:
        board = reconstruct(ex["initial_fen"], json.loads(ex["history"]))
        result.insert(0, {"id": "personal:" + ex["id"], "name": "Riparti da una tua decisione", "kind": "personal",
                          "theme": ex["theme"], "goal": "Trova una buona mossa e continua il piano contro Maia.",
                          "fen": board.fen(), "color": "w" if board.turn else "b", "reason": "Da un momento critico di una tua partita analizzata."})
    return result


@app.post("/api/drills/{template_id}/start")
def start_drill(template_id: str, body: DrillInput):
    if template_id.startswith("personal:"):
        with database() as con:
            ex = find_exercise(con, template_id.removeprefix("personal:"))
            initial, moves = ex["initial_fen"], json.loads(ex["history"])
            board = reconstruct(initial, moves)
            template = {"name": "Drill dalla tua partita", "theme": ex["theme"], "goal": "Scegli una buona mossa e continua il piano contro Maia.", "color": "w" if board.turn else "b"}
    else:
        template = next((t for t in CATALOG if t["id"] == template_id), None)
        if template is None:
            raise HTTPException(404, "Drill non trovato")
        initial, moves, _ = materialize(template)
    game_id = str(uuid.uuid4())
    with database() as con:
        con.execute("INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES(?,?,?,?,?,?,?,?,?,?)", (game_id, initial, json.dumps(moves), template.get("color", body.color), body.elo,
                    template["name"], now(), None, None, "drill"))
        con.execute("INSERT INTO drill_sessions VALUES(?,?,?,?,?,?,?)", (game_id, template_id, template["name"], template["theme"], template["goal"], len(moves), body.target))
    return get_game(game_id)


@app.get("/api/profile")
def profile():
    with database() as con:
        game_count = con.execute("SELECT count(*) FROM games WHERE source!='snapshot'").fetchone()[0]
        attempts_count = con.execute("SELECT count(*) FROM attempts").fetchone()[0]
        unaided = con.execute("SELECT count(*) FROM attempts WHERE success=1 AND assisted=0 AND is_first=1 AND exposure IN ('new','review')").fetchone()[0]
        independent = con.execute("SELECT count(*) FROM attempts WHERE assisted=0 AND is_first=1 AND exposure IN ('new','review')").fetchone()[0]
        due = con.execute("SELECT count(*) FROM exercises WHERE due_at<=?", (now(),)).fetchone()[0]
        themes = [dict(r) for r in con.execute("SELECT theme,count(*) AS examples FROM exercises GROUP BY theme ORDER BY examples DESC")]
        domains = {key:0 for key in ('tactical','positional','mixed','unclear')}
        seen = set()
        for row in con.execute('SELECT analysis FROM games WHERE analysis IS NOT NULL AND source!=?', ('snapshot',)):
            for d in json.loads(row['analysis']).get('decisions',[]):
                identity=(d['fen'],d['played'])
                if d['loss']<80 or identity in seen:continue
                seen.add(identity)
                saved=d.get('insight')
                kind=(saved if saved and saved.get('version')==insights.VERSION else insights.compare(d['fen'],d['played'],d['best'],d['actual']))['kind']
                if kind in domains:domains[kind]+=1
    return {"games": game_count, "attempts": attempts_count, "independentAttempts": independent, "unaidedSuccesses": unaided, "due": due,
            "themes": themes, "domains": [{'kind':key,'label':insights.LABELS[key],'examples':value} for key,value in domains.items()], "confidence": "Osservazioni iniziali",
            "plan": [{"title": "Ripassa le tue decisioni", "minutes": 5, "description": f"{due} esercizi pronti per il ripasso."},
                     {"title": "Un drill e una partita consapevole", "minutes": 15, "description": "Riparti da una tua decisione critica contro Maia, poi applica il metodo nel gioco libero."},
                     {"title": "Rivedi un momento critico", "minutes": 5, "description": "Confronta la tua scelta con una variante verificata da Stockfish."}]}


@app.get('/api/tutor/status')
def tutor_status():
    try:
        key, model = tutor.configuration()
    except tutor.TutorError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    return {'configured': bool(key), 'provider': 'DeepSeek', 'model': model}


@app.get('/api/games/{game_id}/tutor')
def saved_tutor(game_id: str):
    with database() as con:
        row = find_game(con, game_id)
        if not row['analysis'] or row['analysis_version'] != len(json.loads(row['moves'])):
            return None
        fingerprint = hashlib.sha256(row['analysis'].encode()).hexdigest()
        review = con.execute('SELECT response FROM tutor_reviews WHERE game_id=? AND analysis_hash=? ORDER BY created_at DESC LIMIT 1', (game_id, fingerprint)).fetchone()
    return {**json.loads(review['response']), 'cached': True} if review else None


@app.post('/api/games/{game_id}/tutor')
def request_tutor(game_id: str, body: TutorInput):
    if not tutor_lock.acquire(blocking=False):
        raise HTTPException(429, 'Il tutor sta preparando una risposta. Attendi prima di richiederne un’altra.')
    try:
        key, model = tutor.configuration()
        if not key:
            raise tutor.TutorError('DeepSeek non è configurato sul server.', 503)
        with database() as con:
            row = dict(find_game(con, game_id))
            if body.version != len(json.loads(row['moves'])) or row['analysis_version'] != body.version or not row['analysis']:
                raise HTTPException(409, 'Completa l’analisi Stockfish della versione attuale prima di chiedere al tutor.')
            analysis = json.loads(row['analysis'])
            decisions = sorted(analysis['decisions'], key=lambda d: -d['loss'])[:3]
            for d in decisions:
                d['insight'] = insights.compare(d['fen'],d['played'],d['best'],d['actual'])
            if not decisions:
                raise HTTPException(422, 'Non ci sono decisioni analizzate da discutere.')
            selected_plies = {d['ply'] for d in decisions}
            exercise_rows = [dict(r) for r in con.execute('SELECT id,ply,theme,due_at FROM exercises WHERE game_id=?', (game_id,)) if r['ply'] in selected_plies]
        stats = profile()
        exercise_context = [{'id': e['id'], 'ply': e['ply'], 'theme': e['theme'], 'dueAt': e['due_at']} for e in exercise_rows]
        drills = [{'id': t['id'], 'name': t['name'], 'goal': t['goal']} for t in CATALOG]
        drills += [{'id': 'personal:' + e['id'], 'name': 'Continua dalla tua decisione', 'goal': e['theme']} for e in exercise_rows]
        context = {'playerColor': row['player_color'], 'referenceElo': row['elo'], 'source': row['source'],
                   'engine': analysis['engine'], 'analysisNote': analysis['note'], 'analyzedDecisions': len(analysis['decisions']),
                   'decisions': decisions, 'reflection': body.reflection.strip(), 'exercises': exercise_context, 'drills': drills,
                   'practice': {k: stats[k] for k in ('games', 'attempts', 'independentAttempts', 'unaidedSuccesses', 'due', 'themes','domains')}}
        fingerprint = hashlib.sha256(row['analysis'].encode()).hexdigest()
        cache_key = hashlib.sha256(json.dumps([tutor.PROMPT_VERSION, game_id, fingerprint, model, context], sort_keys=True).encode()).hexdigest()
        with database() as con:
            cached = con.execute('SELECT response FROM tutor_reviews WHERE cache_key=?', (cache_key,)).fetchone()
        if cached:
            return {**json.loads(cached['response']), 'cached': True}
        response = tutor.generate(context, model)
        response.update({'gameId': game_id, 'version': body.version, 'createdAt': now(), 'reflection': body.reflection.strip(),
                         'evidence': [{'ply': d['ply'], 'playedSan': d['playedSan'], 'bestSan': d['best']['san'], 'theme': d['theme'], 'insight':insights.public(d['insight'])} for d in decisions],
                         'cached': False})
        # A concurrent move or re-analysis invalidates the coaching; never attach it to a newer state.
        with database() as con:
            con.execute('BEGIN IMMEDIATE')
            current = find_game(con, game_id)
            if current['analysis'] != row['analysis'] or current['moves'] != row['moves']:
                raise HTTPException(409, 'La partita è cambiata durante la risposta: rivedi la nuova analisi.')
            con.execute('INSERT OR IGNORE INTO tutor_reviews VALUES(?,?,?,?,?)', (cache_key, game_id, fingerprint, now(), json.dumps(response)))
        return response
    except tutor.TutorError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    finally:
        tutor_lock.release()


prevention.install(app, database, reconstruct, now)
mistakes.install(app, database, tutor_lock)

DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
