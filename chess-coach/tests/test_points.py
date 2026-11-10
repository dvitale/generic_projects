from backend import points


def test_the_score_splits_into_material_now_material_after_the_line_and_the_rest():
    # Black has just taken on d2; Nc6+ forks king and queen and wins it back with interest.
    fen = 'rnbqk2r/ppp2ppp/8/b2pN3/3P4/2P5/PP1nQPPP/R1B1KB1R w KQkq - 0 8'
    found = points.breakdown(fen, {'cp': 653, 'mate': None, 'pv': 'e5c6 d2e4 c6d8 e8d8 e2b5 b8c6 b5d5 c8d7'.split()})
    assert (found['now'], found['end'], found['plies'], found['cp'], found['mate']) == (-3, 4, 8, 653, None)
    assert found['rest'] == 2.53 and found['expected'] == 92


def test_a_mate_has_no_rest_and_a_line_stops_at_an_illegal_move():
    found = points.breakdown('7k/8/5KQ1/8/8/8/8/8 w - - 0 1', {'cp': 0, 'mate': 1, 'pv': ['g6g7', 'a1a2']})
    assert (found['now'], found['plies'], found['rest'], found['expected']) == (9, 1, None, 100)


def test_diagnoses_and_position_judgments_carry_the_breakdown():
    from backend import diagnosis, learning
    row = {'id': 'x', 'fen': '7k/8/5KQ1/8/8/8/8/8 w - - 0 1', 'ply': 0, 'game_id': 'g',
           'answer': '{"assessment": "equal", "fearedLost": false}', 'evidence': '{"cp": 900, "mate": null, "pv": [], "san": []}'}
    assert learning.public_judgment(row)['points']['now'] == 9
    saved = {**row, 'kind': 'puzzle', 'created_at': '', 'search': 'missed_solution', 'reading': '[]', 'rule_version': 2,
             'evidence': '{"best": {"cp": 900, "mate": null, "pv": []}}'}
    assert diagnosis.public(saved)['points']['rest'] == 0.0
