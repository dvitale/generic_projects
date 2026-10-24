from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import signal
import sqlite3
from types import SimpleNamespace

import chess
import chess.pgn
import pytest
import torch
import zstandard

import monthly_cycle as cycle
import monthly_data as md
import train as training
from policy import Config


def games(month, count=160):
    result = []
    for i in range(count):
        rng = random.Random(f'{month}:{i}')
        game = chess.pgn.Game()
        game.headers.update(Event='Rated Rapid game', Site=f'https://lichess.org/{month[-2:]}{i:06d}',
                            UTCDate=f'{month.replace("-", ".")}.{i%28+1:02d}', TimeControl='900+10',
                            WhiteElo=str(600+(i%10)*200), BlackElo=str(800+(i%8)*200), Result='1-0')
        board, node = game.board(), game
        for _ in range(18):
            if board.is_game_over():
                break
            move = rng.choice(list(board.legal_moves))
            board.push(move)
            node = node.add_variation(move)
        result.append(str(game))
    return '\n\n'.join(result) + '\n'


@pytest.fixture(autouse=True)
def restore_signals():
    handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    yield
    for sig, handler in handlers.items():
        signal.signal(sig, handler)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(md, 'check_space', lambda *a, **kw: None)
    source = tmp_path/'fixture.pgn'
    source.write_text(games('2026-09'))
    output = tmp_path/'month.sqlite'
    md.prepare_month(source, output, '2026-09', tmp_path, max_positions=10000, modulus=1)
    return source, output


def test_month_sample_spans_days_is_bounded_and_idempotent(prepared, tmp_path):
    source, output = prepared
    with sqlite3.connect(output) as db:
        assert md.get_meta(db, 'complete')
        assert md.get_meta(db, 'stats')['scanned_games'] == 160
        assert 0 < db.execute('SELECT count(*) FROM positions').fetchone()[0] <= 10000
        assert len({row[0].split(':')[1] for row in db.execute('SELECT DISTINCT bucket FROM positions')}) >= 20
    before = training.fingerprint(output)
    md.prepare_month(source, output, '2026-09', tmp_path, max_positions=10000, modulus=1)
    assert training.fingerprint(output) == before


def test_fixed_holdout_excluded_from_train_and_replay(prepared, tmp_path):
    _, source = prepared
    fixed, data, replay = tmp_path/'fixed.sqlite', tmp_path/'train.sqlite', tmp_path/'replay.sqlite'
    blocked = md.fixed_and_training(source, fixed, data)
    assert md.heldout_keys(fixed)
    with sqlite3.connect(data) as db:
        keys = {r[0] for r in db.execute('SELECT position_key FROM positions')}
        assert keys and not keys & blocked
        opening = hashlib.sha256(' '.join(chess.Board().fen().split()[:4]).encode()).hexdigest()
        assert opening in keys  # Novel holdout must not remove all common openings from training.
        assert {r[0] for r in db.execute('SELECT DISTINCT split FROM positions')} == {'train'}
    md.copy_rows(replay, [data], ['train'], 20, {'speed': 'rapid'}, blocked)
    with sqlite3.connect(replay) as db:
        assert 0 < db.execute('SELECT count(*) FROM positions').fetchone()[0] <= 20


def test_sampling_checkpoint_recovers_interruption(tmp_path, monkeypatch):
    monkeypatch.setattr(md, 'check_space', lambda *a, **kw: None)
    source = tmp_path/'fixture.pgn'
    source.write_text(games('2026-09', 30))
    original = md.candidate_rows
    calls = []
    def stop(block, *a, **kw):
        calls.append(1)
        if len(calls) == 12:
            raise KeyboardInterrupt()
        return original(block, *a, **kw)
    monkeypatch.setattr(md, 'candidate_rows', stop)
    with pytest.raises(KeyboardInterrupt):
        md.prepare_month(source, tmp_path/'resume.sqlite', '2026-09', tmp_path, 10000, 1)
    monkeypatch.setattr(md, 'candidate_rows', original)
    md.prepare_month(source, tmp_path/'resume.sqlite', '2026-09', tmp_path, 10000, 1)
    md.prepare_month(source, tmp_path/'full.sqlite', '2026-09', tmp_path, 10000, 1)
    with sqlite3.connect(tmp_path/'resume.sqlite') as a, sqlite3.connect(tmp_path/'full.sqlite') as b:
        assert a.execute(f'SELECT {md.FIELDS} FROM positions ORDER BY game_id,ply').fetchall() == b.execute(f'SELECT {md.FIELDS} FROM positions ORDER BY game_id,ply').fetchall()


def test_quality_gate_checks_regression_and_invalid_results():
    before = {'all': dict(count=1000, nll=2., uniform_nll=3., top1=.4),
              '600': dict(count=100, top1=.4)}
    assert cycle.acceptance(before, before)['accepted']
    bad = {**before, 'all': {**before['all'], 'nll': 2.1}}
    assert not cycle.acceptance(bad, before)['accepted']
    bad = {**before, '600': dict(count=100, top1=.3)}
    assert not cycle.acceptance(bad, before)['accepted']
    assert not cycle.acceptance({})['accepted']


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    (tmp_path/'data/monthly').mkdir(parents=True)
    monkeypatch.setattr(cycle, 'storage_budget', lambda *a, **kw: None)
    monkeypatch.setattr(md, 'check_space', lambda *a, **kw: None)
    monkeypatch.setattr(training, 'Config', lambda: Config(dim=32, layers=1, heads=4, head_dim=8, dropout=0))
    def download(month, folder, host_disk):
        folder.mkdir(exist_ok=True, parents=True)
        path = folder/f'lichess_db_standard_rated_{month}.pgn.zst'
        path.write_bytes(zstandard.ZstdCompressor().compress(games(month).encode()))
        md.write_json(folder/f'{month}.manifest.json', dict(name=path.name, sha256=training.fingerprint(path)))
    def prepare(source, output, month, host_disk, **kwargs):
        md.prepare_month(source, output, month, host_disk, 10000, 1, **kwargs)
    monkeypatch.setattr(cycle, 'download', download)
    monkeypatch.setattr(cycle, 'prepare_month', prepare)
    monkeypatch.setattr(cycle, 'acceptance', lambda *a, **kw: dict(accepted=True, reasons=[]))
    args = SimpleNamespace(max_steps=2, chunk_steps=1, patience=3, host_disk=str(tmp_path), keep_archive=False)
    return tmp_path, args


@pytest.mark.parametrize('next_month', ['2026-10', '2026-08'])
def test_two_months_keep_optimizer_fixed_holdout_and_replay_then_cleanup(pipeline, next_month):
    root, args = pipeline
    args.allow_earlier_month = next_month < '2026-09'
    cycle.run_month(root, '2026-09', args)
    fixed = training.fingerprint(root/'data/cycles/fixed.sqlite')
    parent = root/'runs/monthly/2026-09/best.pt'
    parent_sha = training.fingerprint(parent)
    first = torch.load(parent, weights_only=True)
    cycle.run_month(root, next_month, args)
    assert training.fingerprint(root/'data/cycles/fixed.sqlite') == fixed
    second = torch.load(root/'runs/monthly'/next_month/'best.pt', weights_only=True)
    assert second['step'] > first['step']
    assert second['parent_sha256'] == parent_sha
    assert second['setup']['replay_positions'] > 0
    assert second['sampling'].endswith('_replay20')
    assert all(float(v['step']) > first['step'] for v in second['optimizer']['state'].values())
    assert not list((root/'data/monthly').glob('*.pgn.zst'))
    assert json.loads((root/'data/cycles/ledger.json').read_text())['active_month'] == next_month
    assert not md.heldout_keys(root/'data/cycles/fixed.sqlite') & {
        r[0] for r in sqlite3.connect(root/'data/cycles/replay.sqlite').execute('SELECT position_key FROM positions')}
    # Restarting a completed month must not retrain or download it.
    cycle.run_month(root, next_month, args)
    assert training.fingerprint(root/'runs/monthly/2026-09/best.pt') == parent_sha


def test_rejected_month_preserves_archive(pipeline, monkeypatch):
    root, args = pipeline
    monkeypatch.setattr(cycle, 'acceptance', lambda *a, **kw: dict(accepted=False, reasons=['fixture']))
    with pytest.raises(ValueError, match='Qualità peggiorata'):
        cycle.run_month(root, '2026-09', args)
    assert (root/'data/monthly/lichess_db_standard_rated_2026-09.pgn.zst').exists()
    assert json.loads((root/'data/cycles/ledger.json').read_text())['active_month'] is None


def test_cleanup_refuses_missing_or_modified_proofs(pipeline):
    root, args = pipeline
    args.keep_archive = True
    cycle.run_month(root, '2026-09', args)
    record = json.loads((root/'data/cycles/ledger.json').read_text())['months']['2026-09']
    archive = root/'data/monthly/lichess_db_standard_rated_2026-09.pgn.zst'
    with pytest.raises(ValueError, match='non completato'):
        cycle.guarded_remove_archive(root, '2026-09', {**record, 'state':'training'})
    report = root/'runs/monthly/2026-09/verification.json'
    report.write_text(report.read_text() + ' ')
    with pytest.raises(ValueError, match='non corrispondenti'):
        cycle.guarded_remove_archive(root, '2026-09', record)
    assert archive.exists()


def test_cleanup_refuses_archive_symlink(pipeline, tmp_path):
    root, args = pipeline
    args.keep_archive = True
    cycle.run_month(root, '2026-09', args)
    record = json.loads((root/'data/cycles/ledger.json').read_text())['months']['2026-09']
    archive = root/'data/monthly/lichess_db_standard_rated_2026-09.pgn.zst'
    stored = root/'payload-to-preserve'
    archive.rename(stored)
    archive.symlink_to(stored)
    with pytest.raises(ValueError, match='Percorso archivio'):
        cycle.guarded_remove_archive(root, '2026-09', record)
    assert stored.exists()


def test_retention_keeps_last_two_and_rejects_escaping_paths(tmp_path):
    months = ['2026-07', '2026-08', '2026-09']
    for month in months:
        folder = tmp_path/'runs/monthly'/month
        folder.mkdir(parents=True)
        (folder/'best.pt').write_bytes(b'fixture')
    cycle.prune_old_artifacts(tmp_path, {'months': {m: {'state':'complete'} for m in months}})
    assert not (tmp_path/'runs/monthly/2026-07/best.pt').exists()
    assert (tmp_path/'runs/monthly/2026-08/best.pt').exists()
    assert (tmp_path/'runs/monthly/2026-09/best.pt').exists()
    victim = tmp_path/'preserve.pt'
    victim.write_bytes(b'preserve')
    (tmp_path/'runs/monthly/2026-07/best.pt').symlink_to(victim)
    with pytest.raises(ValueError, match='Percorso da conservare'):
        cycle.prune_old_artifacts(tmp_path, {'months': {m: {'state':'complete'} for m in months}})
    assert victim.read_bytes() == b'preserve'


def test_storage_budget_blocks_without_removing_files(tmp_path, monkeypatch):
    folder = tmp_path/'data/cycles'
    folder.mkdir(parents=True)
    saved = folder/'keep.sqlite'
    saved.write_bytes(b'keep')
    with pytest.raises(RuntimeError, match='Budget'):
        cycle.storage_budget(tmp_path, tmp_path, limit_gib=0)
    assert saved.read_bytes() == b'keep'


def test_restart_after_replay_written_before_ledger_commit(pipeline, monkeypatch):
    root, args = pipeline
    real_write = cycle.write_json
    def fail_commit(path, value):
        if path.name == 'ledger.json' and value.get('active_month') == '2026-09':
            raise OSError('simulated power failure')
        real_write(path, value)
    monkeypatch.setattr(cycle, 'write_json', fail_commit)
    with pytest.raises(OSError, match='power failure'):
        cycle.run_month(root, '2026-09', args)
    assert (root/'data/cycles/replay.sqlite').exists()
    assert (root/'data/monthly/lichess_db_standard_rated_2026-09.pgn.zst').exists()
    monkeypatch.setattr(cycle, 'write_json', real_write)
    cycle.run_month(root, '2026-09', args)
    assert json.loads((root/'data/cycles/ledger.json').read_text())['active_month'] == '2026-09'


@pytest.mark.parametrize('active,requested', [('2026-09', '2026-08'), ('2026-07', '2026-08')])
def test_historical_month_requires_opt_in_before_download(tmp_path, monkeypatch, active, requested):
    folder = tmp_path/'data/cycles'
    folder.mkdir(parents=True)
    cycle.write_json(folder/'ledger.json', dict(active_month=active, months={
        '2026-09': {'state': 'complete'}, '2026-07': {'state': 'complete'}}, fixed_sha256=None))
    monkeypatch.setattr(cycle, 'download', lambda *a: pytest.fail('Unexpected download'))
    with pytest.raises(ValueError, match='allow-earlier-month'):
        cycle.run_month(tmp_path, requested, SimpleNamespace(keep_archive=False))


def test_retention_uses_training_order_for_historical_months(tmp_path):
    months = ['2026-09', '2026-08', '2026-07']
    for month in months:
        folder = tmp_path/'runs/monthly'/month
        folder.mkdir(parents=True)
        (folder/'best.pt').write_bytes(b'fixture')
    cycle.prune_old_artifacts(tmp_path, {'months': {m: {'state': 'complete'} for m in months}})
    assert not (tmp_path/'runs/monthly/2026-09/best.pt').exists()
    assert (tmp_path/'runs/monthly/2026-08/best.pt').exists()
    assert (tmp_path/'runs/monthly/2026-07/best.pt').exists()
