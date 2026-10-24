import io
import json
import sqlite3
from types import SimpleNamespace

import chess.pgn
import pytest
import torch

import monthly_cycle as cycle
import monthly_data as md
import train as training
from test_monthly_cycle import games, pipeline, prepared, restore_signals


@pytest.mark.parametrize('white,black,parity', [(1500, 1501, 0), (1501, 1500, 1), (599, 1500, 1)])
def test_cutoff_uses_mover_inclusive_at_1500(white, black, parity):
    game = chess.pgn.read_game(io.StringIO(games('2026-08', 1)))
    game.headers['WhiteElo'], game.headers['BlackElo'] = str(white), str(black)
    rows = md.candidate_rows(str(game), '2026-08', modulus=1, low=600, high=1500)
    assert rows
    assert all(row[3] == 1500 and row[1] % 2 == parity for row in rows)
    game.headers['WhiteElo'] = game.headers['BlackElo'] = '1501'
    assert not md.candidate_rows(str(game), '2026-08', modulus=1, low=600, high=1500)


def test_focused_sample_and_replay_exclude_higher_ratings(prepared, tmp_path):
    source, broad = prepared
    focused = tmp_path/'focused.sqlite'
    md.prepare_month(source, focused, '2026-09', tmp_path, 10000, 1, low=600, high=1500)
    with sqlite3.connect(focused) as db:
        assert md.get_meta(db, 'settings')['high'] == 1500
        low, high, count = db.execute('SELECT min(elo),max(elo),count(*) FROM positions').fetchone()
        assert 600 <= low <= high <= 1500 and 0 < count <= 10000
    with pytest.raises(ValueError, match='parametri'):
        md.prepare_month(source, focused, '2026-09', tmp_path, 10000, 1)
    replay = tmp_path/'replay-focus.sqlite'
    md.copy_rows(replay, [broad], ['train'], 30, {}, rating_range=[600, 1500])
    with sqlite3.connect(replay) as db, sqlite3.connect(broad) as original:
        actual = db.execute('SELECT game_id,ply FROM positions ORDER BY priority').fetchall()
        expected = original.execute("SELECT game_id,ply FROM positions WHERE split='train' AND elo BETWEEN 600 AND 1500 ORDER BY priority LIMIT 30").fetchall()
        assert actual == expected  # Filter before capping, not after.


def test_specialization_preserves_parent_and_holdout_filters_replay_and_inherits_range(pipeline, monkeypatch):
    root, args = pipeline
    cycle.run_month(root, '2026-09', args)
    fixed = root/'data/cycles/fixed.sqlite'
    fixed_sha = training.fingerprint(fixed)
    parent = root/'runs/monthly/2026-09/best.pt'
    parent_sha = training.fingerprint(parent)
    assert torch.load(parent, weights_only=True)['rating_bounds'][1] > 1500
    args.max_elo, args.allow_earlier_month, args.keep_archive = 1500, True, True
    cycle.run_month(root, '2026-08', args)
    assert training.fingerprint(parent) == parent_sha
    assert training.fingerprint(fixed) == fixed_sha
    child = torch.load(root/'runs/monthly/2026-08/best.pt', weights_only=True)
    assert child['parent_sha256'] == parent_sha
    assert child['step'] > 2 and child['rating_bounds'][1] <= 1500
    assert child['setup']['replay_positions'] > 0
    assert all(float(item['step']) > 2 for item in child['optimizer']['state'].values())
    view = root/'data/cycles/fixed-600-1500.sqlite'
    with sqlite3.connect(fixed) as db, sqlite3.connect(view) as filtered:
        expected = db.execute("SELECT game_id,ply FROM positions WHERE split='validation' AND elo BETWEEN 600 AND 1500 ORDER BY game_id,ply").fetchall()
        assert filtered.execute('SELECT game_id,ply FROM positions ORDER BY game_id,ply').fetchall() == expected
        assert expected
    for name in ('months/2026-08.train.sqlite', 'months/2026-08.replay.sqlite', 'replay.sqlite'):
        with sqlite3.connect(root/'data/cycles'/name) as db:
            assert db.execute('SELECT count(*) FROM positions WHERE elo>1500 OR elo<600').fetchone()[0] == 0
            assert not md.heldout_keys(fixed) & {row[0] for row in db.execute('SELECT position_key FROM positions')}
    report = json.loads((root/'runs/monthly/2026-08/verification.json').read_text())
    assert report['validation']['all']['count'] == len(expected)
    assert report['previous_validation']['all']['count'] == len(expected)
    assert report['global_validation']['all']['count'] > len(expected)
    assert report['test'] == 'Not evaluated'
    args.max_elo = None
    cycle.run_month(root, '2026-08', args)  # Resume uses saved range without a flag.
    args.max_elo = 2600
    with pytest.raises(ValueError, match='filtri diversi'):
        cycle.run_month(root, '2026-08', args)
    args.max_elo = None
    def stop_download(*a):
        raise OSError('stop before transfer')
    monkeypatch.setattr(cycle, 'download', stop_download)
    with pytest.raises(OSError, match='stop before transfer'):
        cycle.run_month(root, '2026-10', args)
    assert json.loads((root/'runs/monthly/2026-10/request.json').read_text())['rating_range'] == [600, 1500]
    record = json.loads((root/'data/cycles/ledger.json').read_text())['months']['2026-08']
    with view.open('ab') as out:
        out.write(b'changed')
    with pytest.raises(ValueError, match='Sottoinsieme'):
        cycle.guarded_remove_archive(root, '2026-08', record)
    assert (root/'data/monthly/lichess_db_standard_rated_2026-08.pgn.zst').exists()


@pytest.mark.parametrize('low,high', [(600, 599), (1501, 1500), (599, 1500), (600, 2601)])
def test_bad_range_rejected_before_download(tmp_path, low, high, monkeypatch):
    monkeypatch.setattr(cycle, 'download', lambda *a: pytest.fail('Unexpected download'))
    with pytest.raises(ValueError, match='Intervallo rating'):
        cycle.run_month(tmp_path, '2026-08', SimpleNamespace(min_elo=low, max_elo=high))
