"""Bounded whole-month sampling and compact fixed holdout/replay datasets."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import struct

import chess
import chess.pgn
import zstandard

from dataset import CompleteGameBuilder, game_key, speed_of, split_for
from download_month import check_space, write_json
from features import encode, move_id
from train import fingerprint

FIELDS = "game_id,ply,split,elo,fen,pieces,ep,context,legal,target,bucket,priority,position_key,month"


def database(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA max_page_count=524288")  # 2 GiB with the default 4 KiB page size.
    db.executescript('''
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS positions(
      id INTEGER PRIMARY KEY,game_id TEXT,ply INTEGER,split TEXT,elo INTEGER,fen TEXT,
      pieces BLOB,ep BLOB,context BLOB,legal BLOB,target INTEGER,bucket TEXT,priority TEXT,
      position_key TEXT,month TEXT,UNIQUE(game_id,ply));
    CREATE INDEX IF NOT EXISTS bucket_priority ON positions(bucket,priority DESC);
    CREATE INDEX IF NOT EXISTS positions_split ON positions(split);
    CREATE INDEX IF NOT EXISTS position_key ON positions(position_key);
    ''')
    return db


def put_meta(db, key, value):
    db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, json.dumps(value)))


def get_meta(db, key, default=None):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def pgn_blocks(stream):
    block, size = [], 0
    for line in stream:
        if line.startswith('[Event ') and block:
            yield ''.join(block)
            block, size = [], 0
        size += len(line)
        if size > 2*1024**2:
            raise ValueError("PGN singolo oltre 2 MiB: estrazione interrotta")
        block.append(line)
    if block and any(line.startswith('[Event ') for line in block):
        yield ''.join(block)


def candidate_rows(block, month, modulus=64, positions_per_game=8):
    headers = dict(re.findall(r'^\[(\w+) "([^"\n]*)"\]', block, re.M))
    if (not headers.get("Event", "").startswith("Rated ") or
        headers.get("Variant", "Standard") != "Standard" or
        "BOT" in (headers.get("WhiteTitle"), headers.get("BlackTitle")) or
        speed_of(headers.get("TimeControl")) != "rapid" or
        not headers.get("UTCDate", headers.get("Date", "")).startswith(month.replace('-', '.') + '.')):
        return []
    ratings = [int(headers.get(key, '0')) if headers.get(key, '').isdigit() else 0
               for key in ('WhiteElo', 'BlackElo')]
    if not any(600 <= rating <= 2600 for rating in ratings):
        return []
    identity = headers.get('Site', '').rstrip('/').split('/')[-1][:8]
    if not re.fullmatch(r'[A-Za-z0-9]{8}', identity):
        return []
    key = hashlib.sha256(identity.encode()).hexdigest()
    divisor = max(1, modulus//4) if any(600 <= rating < 1200 for rating in ratings) else modulus
    if int(key[8:16], 16) % divisor:
        return []
    game = chess.pgn.read_game(io.StringIO(block), Visitor=CompleteGameBuilder)
    if (game is None or game.errors or not getattr(game, 'has_movetext_result', False)
        or game.headers.get('Result') not in ('1-0', '0-1', '1/2-1/2')):
        return []
    board = game.board()
    if not board.is_valid():
        return []
    moves = list(game.mainline_moves())
    priorities = {ply: hashlib.sha256(f'{key}:{ply}'.encode()).hexdigest() for ply in range(len(moves))}
    selected = set(sorted(priorities, key=priorities.get)[:positions_per_game])
    day = headers.get('UTCDate', headers.get('Date'))[-2:]
    if not day.isdigit() or not 1 <= int(day) <= 31:
        return []
    rows = []
    for ply, move in enumerate(moves):
        rating = ratings[0 if board.turn else 1]
        if ply in selected and 600 <= rating <= 2600:
            pieces, ep, context = encode(board, rating)
            legal = [move_id(m) for m in board.legal_moves]
            material = sum(len(board.pieces(piece, color))*value for piece, value in
                           ((chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9))
                           for color in chess.COLORS)
            phase = 'end' if material <= 13 else 'opening' if board.fullmove_number <= 10 else 'middle'
            split = split_for(key)
            band = min(2400, rating//200*200)
            bucket = f'{split}:{day}:{band}:{phase}'
            position_key = hashlib.sha256(' '.join(board.fen().split()[:4]).encode()).hexdigest()
            rows.append((key, ply, split, rating, board.fen(en_passant='fen'), bytes(pieces), bytes(ep),
                         struct.pack('<8f', *context), struct.pack(f'<{len(legal)}H', *legal),
                         legal.index(move_id(move)), bucket, priorities[ply], position_key, month))
        board.push(move)
    return rows


def prepare_month(source, output, month, host_disk='/mnt/c', max_positions=1_000_000, modulus=64):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = dict(schema=2, source_sha256=fingerprint(source), month=month, speed='rapid', low=600,
                    high=2600, max_positions=max_positions, modulus=modulus, positions_per_game=8)
    db = database(output)
    old = get_meta(db, 'settings')
    if old is not None and old != settings:
        db.close()
        raise ValueError('Sorgente o parametri del campione mensile cambiati')
    if get_meta(db, 'complete', False):
        db.close()
        return
    put_meta(db, 'settings', settings)
    cursor = get_meta(db, 'cursor', 0)
    stats = Counter(get_meta(db, 'stats', {}))
    limits = {split: max(1, int(max_positions*ratio)//930)
              for split, ratio in (('train', .8), ('validation', .1), ('test', .1))}
    if sum(value*930 for value in limits.values()) > max_positions:
        raise ValueError('Limite posizioni troppo piccolo per le fasce previste')
    db.commit()
    counts = dict(db.execute('SELECT bucket,count(*) FROM positions GROUP BY bucket'))
    cutoffs = dict(db.execute('SELECT bucket,max(priority) FROM positions GROUP BY bucket'))
    committed_stats = stats.copy()
    report_path = output.with_suffix('.progress.json')
    try:
        with Path(source).open('rb') as raw:
            stream = zstandard.ZstdDecompressor().stream_reader(raw) if str(source).endswith('.zst') else raw
            with io.TextIOWrapper(stream, encoding='utf-8') as text:
                index = cursor
                for index, block in enumerate(pgn_blocks(text), 1):
                    if index <= cursor:
                        continue
                    if index % 10000 == 1:
                        check_space(output.parent, host_disk)
                    rows = candidate_rows(block, month, modulus)
                    stats['scanned_games'] += 1
                    stats['selected_games'] += bool(rows)
                    for row in rows:
                        bucket, priority = row[10:12]
                        cap = limits[row[2]]
                        if counts.get(bucket, 0) >= cap and priority >= cutoffs[bucket]:
                            continue
                        changed = db.execute(f'INSERT OR IGNORE INTO positions({FIELDS}) VALUES({",".join("?"*14)})', row).rowcount
                        counts[bucket] = counts.get(bucket, 0) + changed
                        if counts[bucket] > cap:
                            db.execute('DELETE FROM positions WHERE id=(SELECT id FROM positions WHERE bucket=? ORDER BY priority DESC LIMIT 1)', (bucket,))
                            counts[bucket] -= 1
                        cutoffs[bucket] = db.execute('SELECT max(priority) FROM positions WHERE bucket=?', (bucket,)).fetchone()[0]
                    if index % 10000 == 0:
                        put_meta(db, 'cursor', index)
                        put_meta(db, 'stats', dict(stats))
                        db.commit()
                        committed_stats = stats.copy()
                        write_json(report_path, dict(state='sampling', **stats, positions=sum(counts.values())))
                put_meta(db, 'cursor', index)
                put_meta(db, 'stats', dict(stats))
                put_meta(db, 'complete', True)
                db.commit()
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        write_json(report_path, dict(state='complete', **stats,
                                    positions=db.execute('SELECT count(*) FROM positions').fetchone()[0]))
    except BaseException:
        db.rollback()
        write_json(report_path, dict(state='interrupted', **committed_stats))
        raise
    finally:
        db.close()


def copy_rows(destination, sources, splits, limit_per_split, settings, exclude_keys=()):
    """Stable hash-priority retention, bounded independently for every split."""
    temp = Path(str(destination) + '.tmp')
    if temp.exists():
        temp.unlink()
    db = database(temp)
    excluded = set(exclude_keys)
    try:
        for path in sources:
            with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True) as source:
                for split in splits:
                    for row in source.execute(f'SELECT {FIELDS} FROM positions WHERE split=? ORDER BY priority', (split,)):
                        if row[12] not in excluded:
                            db.execute(f'INSERT OR IGNORE INTO positions({FIELDS}) VALUES({",".join("?"*14)})', row)
                    db.execute('DELETE FROM positions WHERE split=? AND id NOT IN (SELECT id FROM positions WHERE split=? ORDER BY priority LIMIT ?)',
                               (split, split, limit_per_split))
                    db.commit()
        put_meta(db, 'settings', settings)
        put_meta(db, 'complete', True)
        db.commit()
        db.execute('VACUUM')
    finally:
        db.close()
    temp.replace(destination)


def heldout_keys(path):
    with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True) as db:
        return {row[0] for row in db.execute("SELECT position_key FROM positions WHERE split IN ('validation','test')")}


def fixed_and_training(month_data, fixed, training):
    with sqlite3.connect(month_data) as db:
        settings = get_meta(db, 'settings')
        training_keys = {row[0] for row in db.execute("SELECT position_key FROM positions WHERE split='train'")}
    if not Path(fixed).exists():
        # Keep common openings in training; choose novel heldout positions first.
        copy_rows(fixed, [month_data], ['validation', 'test'], 10000,
                  {**settings, 'purpose': 'fixed_holdout'}, exclude_keys=training_keys)
    blocked = heldout_keys(fixed)
    copy_rows(training, [month_data], ['train'], 1_000_000,
              {**settings, 'fixed_sha256': fingerprint(fixed)}, exclude_keys=blocked)
    return blocked
