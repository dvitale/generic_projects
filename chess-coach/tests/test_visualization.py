import random

import chess
from backend import visualization
from test_coach import client

GAME = ('1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O Bxc3 9. d5 Bf6 '
        '10. Re1 Ne7 11. Rxe4 d6 12. Bg5 Bxg5 13. Nxg5 h6 14. Qe2 hxg5 15. Re1 Be6 16. dxe6 f6 17. Re3 c6 *')


def test_the_line_grows_after_three_right_answers_and_shrinks_after_a_wrong_one():
    assert visualization.level([]) == 2
    assert visualization.level([(2, True)] * 3) == 3
    assert visualization.level([(2, True)] * 3 + [(3, False)]) == 2
    # Answers on shorter lines than the current one do not count towards the next step.
    assert visualization.level([(2, True)] * 3 + [(2, True)] * 3) == 3
    assert visualization.level([(1, False)] * 5) == 1
    assert visualization.level([(p, True) for p in range(2, 9) for _ in range(3)] + [(8, True)] * 3) == 8


def check(start, moves, asked):
    kind, text, options, answer, explanation = asked
    end = start.copy()
    for move in moves:
        end.push(move)
    assert len(set(options)) == len(options) >= 2 and 0 <= answer < len(options) and text and explanation
    right = options[answer]
    if kind == 'piece':
        square = chess.parse_square(text.split(' in ')[-1].rstrip('?'))
        piece = end.piece_at(square)
        assert right == ('Casa vuota' if piece is None else visualization.named(piece).capitalize())
    elif kind == 'check':
        assert right == ('Sì' if end.is_check() else 'No')
    elif kind == 'mate':
        assert right == ('Sì' if end.is_checkmate() else 'No')
    elif kind == 'captures':
        assert right == ['Nessuna', '1', '2', '3 o più'][min(3, sum(end.is_capture(m) for m in end.legal_moves))]
    elif kind == 'attackers':
        square = chess.parse_square(text.split(' in ')[-1].rstrip('?'))
        assert right == ['Nessuno', '1', '2', '3 o più'][min(3, len(end.attackers(not end.piece_at(square).color, square)))]
    elif kind == 'escape':
        legal = [visualization.long(end, m) for m in end.legal_moves]
        assert right in legal and all(o not in legal for o in options if o != right)
    return kind


def test_every_question_is_answered_by_the_board_after_the_line():
    board = chess.Board()
    moves = [board.push_san(m) or board.peek() for m in GAME.replace('*', '').split() if not m.endswith('.')]
    kinds = set()
    for seed in range(300):
        rng = random.Random(seed)
        start_ply, length = rng.randrange(10, 30), rng.randint(1, 4)
        start = chess.Board()
        for move in moves[:start_ply]:
            start.push(move)
        line = moves[start_ply:start_ply + length]
        kinds.add(check(start, line, visualization.question(start, line, rng)))
    assert {'piece', 'check', 'captures', 'attackers'} <= kinds
    # A line that ends in check also asks about mate and the legal way out.
    checked = chess.Board('4k3/8/8/8/8/8/3PPP2/4K2R w K - 0 1')
    line = [chess.Move.from_uci('h1h8')]
    asked = {check(checked, line, visualization.question(checked, line, random.Random(seed))) for seed in range(60)}
    assert {'mate', 'escape'} <= asked


def test_questions_keep_the_answer_on_the_server_until_chosen(client):
    assert client.post('/api/visualization/next').status_code == 409
    client.post('/api/import', json={'pgn': GAME, 'color': 'w'})
    asked = client.post('/api/visualization/next').json()
    assert asked['plies'] == 2 and len(asked['line'].split()) >= 2 and 'answer' not in asked and asked['orientation'] == 'w'
    answered = client.post(f"/api/visualization/{asked['id']}/answer", json={'choice': 0}).json()
    assert answered['correct'] == (answered['answer'] == 0) and answered['finalFen'] and len(answered['moves']) == 2
    assert client.post(f"/api/visualization/{asked['id']}/answer", json={'choice': 0}).status_code == 409
    summary = client.get('/api/visualization/summary').json()
    assert summary['answered'] == 1 and summary['byDepth'] == [{'plies': 2, 'answered': 1, 'correct': int(answered['correct'])}]
