import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('calibrate_accuracy_rating', ROOT / 'scripts' / 'calibrate_accuracy_rating.py')
calibration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibration)


def pgn(evals, white: int | str = 1500, black: int | str = 1400, control='600+0', termination='Normal', extra='', name='p'):
    moves = ' '.join(f'{i // 2 + 1}{"." if i % 2 == 0 else "..."} Nf3 {{ {"[%eval " + e + "] " if e else ""}[%clk 0:10:00] }}'
                     for i, e in enumerate(evals))
    return (f'[Event "Rated Rapid game"]\n[White "{name}w"]\n[Black "{name}b"]\n[WhiteElo "{white}"]\n[BlackElo "{black}"]\n[TimeControl "{control}"]\n'
            f'[Termination "{termination}"]\n{extra}\n{moves} 1-0\n\n')


def parsed(text):
    return list(calibration.games(text.splitlines(keepends=True)))


def test_accuracy_matches_the_app_formula():
    # Same cases as web/tests/review-summary.spec.ts.
    steady = calibration.game_accuracy([calibration.win_percent(20)] * 4)
    assert steady == {'w': (100.0, 2), 'b': (100.0, 1)}
    swing = [calibration.win_percent(c) for c in (20, 20, -600, -600)]
    assert calibration.game_accuracy(swing)['w'][0] == 100
    white = calibration.game_accuracy([calibration.win_percent(c) for c in (20, -600, -600, -600)])
    assert white['w'][0] < 60
    assert calibration.win_percent(mate='b') == 0 and calibration.win_percent(5000) == calibration.win_percent(1000)


def test_only_analysed_rapid_games_long_enough_become_samples():
    good = ['0.2'] * 24
    [(headers, moves)] = parsed(pgn(good))
    assert [(n, r) for n, r, _ in calibration.samples(headers, moves)] == [('pw', 1500), ('pb', 1400)]
    # The mating move has no evaluation; mates are read with their side.
    [(headers, moves)] = parsed(pgn(['0.2'] * 22 + ['#-1', '']))
    found = calibration.samples(headers, moves)
    assert len(found) == 2 and found[0][2] < found[1][2]
    for text in (pgn(good, control='180+2'), pgn(good, termination='Abandoned'), pgn(['0.2'] * 18),
                 pgn(['0.2'] * 10 + [''] + ['0.2'] * 13), pgn([''] * 24), pgn(good, extra='[FEN "8/8/8/8/8/8/8/K6k w - - 0 1"]')):
        [(headers, moves)] = parsed(text)
        assert calibration.samples(headers, moves) == []
    # Unrated or anonymous players are skipped, the other side is kept.
    [(headers, moves)] = parsed(pgn(good, black='?'))
    assert [r for _, r, _ in calibration.samples(headers, moves)] == [1500]


def synthetic(players=200, games=10):
    """Players whose accuracy rises with rating: 600 → about 60%, 2600 → about 90%."""
    points = []
    for p in range(players):
        rating = 600 + (p * 37) % 2001
        for g in range(games):
            points.append((f'player{p}', rating, 60 + 30 * (rating - 600) / 2000 + ((g * 7 + p) % 11 - 5)))
    return points


def test_estimate_uses_a_flat_prior_and_narrows_with_more_games():
    rows = calibration.likelihood(synthetic())
    assert len(rows) == len(calibration.BANDS) and all(abs(sum(r) - 1) < 1e-4 for r in rows)
    weak, strong = calibration.estimate(rows, [62]), calibration.estimate(rows, [88])
    assert weak[0] <= weak[1] <= weak[2] and weak[1] < 1200 < 2000 < strong[1]
    one, ten = calibration.estimate(rows, [75]), calibration.estimate(rows, [75] * 10)
    assert ten[2] - ten[0] < one[2] - one[0]
    assert 1300 < ten[1] < 1900
    # Tempering widens the range; extremes stay within the levels.
    tempered = calibration.estimate(rows, [75] * 10, 0.3)
    assert tempered[2] - tempered[0] > ten[2] - ten[0]
    assert all(600 <= v <= 2600 for a in (0, 100, 150) for v in calibration.estimate(rows, [a] * 5))


def test_held_out_players_check_the_range():
    rows, temper, validation = calibration.build(synthetic(players=400))
    assert temper in calibration.TEMPERS
    assert [v['games'] for v in validation] == [1, 5, 10]
    ten = validation[2]
    assert ten['players'] > 30 and 0 <= ten['coverage'] <= 1 and ten['medianWidth'] > 0


def test_calibration_writes_the_web_table(tmp_path):
    source = tmp_path / 'games.pgn'
    source.write_text(pgn(['0.2'] * 24) + pgn(['0.2', '-3.0'] + ['-3.0'] * 22, white=900, black=1900) + pgn(['0.2'] * 24, control='60+0'))
    target = tmp_path / 'table.json'
    calibration.calibrate(str(source), 10, target)
    data = json.loads(target.read_text())
    assert data['games'] == 2 and data['samples'] == 4 and data['minMoves'] == 10
    assert data['bands'][0] == 600 and len(data['likelihood']) == len(data['bands']) and len(data['likelihood'][0]) == 101
    assert data['validation'][0]['games'] == 1
