from datetime import datetime, timedelta

import chess
from backend import lessons, main
from backend.engine import INACCURACY_CP
from test_coach import client


def test_the_lesson_file_replays_and_carries_the_engine_analysis():
    data = lessons.load()
    assert lessons.validate(data) == []
    assert 5 <= len(data['lessons']) <= 10
    for lesson in data['lessons']:
        assert lesson['question'] and lesson['explanation'] and lesson['bookIdea']
        # The book's idea and Stockfish stay separate: the lesson says when they disagree.
        best = lesson['engine']['lines'][0]
        played = lesson['engine']['moves'][lesson['played']]
        if lessons.review_loss(best, played) >= INACCURACY_CP:
            assert lesson.get('engineNote'), lesson['id']


def test_validation_catches_extraction_errors():
    data = lessons.load()
    broken = {**data, 'lessons': [dict(data['lessons'][0], fen=chess.STARTING_FEN), dict(data['lessons'][1], history=['e4', 'e5', 'Nf6']),
                                  dict(data['lessons'][2], moves={**data['lessons'][2]['moves'], 'Bc5': {'verdict': 'good', 'note': ''}})]}
    errors = '\n'.join(lessons.validate(broken))
    assert 'diversa da quella rigiocata' in errors and 'non si rigioca' in errors and 'Bc5 non è legale' in errors


def test_review_steps_forward_only_without_hints():
    now = '2026-11-03T10:00:00+00:00'
    assert lessons.schedule(None, True, 0, now) == (1, (datetime.fromisoformat(now) + timedelta(hours=4)).isoformat())
    assert lessons.schedule({'stage': 2}, True, 0, now)[0] == 3
    assert lessons.schedule({'stage': 2}, True, 1, now)[0] == 0
    assert lessons.schedule({'stage': 5}, False, 0, now)[0] == 0


def test_lessons_answer_keep_book_and_engine_apart_and_schedule_reviews(client):
    overview = client.get('/api/lessons').json()
    assert overview['path']['title'] == 'Ragionamento mossa per mossa'
    assert overview['new'] == len(overview['lessons']) and overview['next'] == 'lc-01-nf3'
    lesson = client.get('/api/lessons/lc-05-qe7').json()
    assert lesson['turn'] == 'b' and lesson['line'].startswith('1.e4 e5 2.Nf3') and len(lesson['hints']) == 3
    assert 'p. 14' in lesson['game']['citation'] and 'Teichmann' in lesson['game']['citation']
    assert 'played' not in lesson and 'moves' not in lesson
    assert client.post('/api/lessons/lc-05-qe7/answer', json={'move': 'e2e4', 'hints': 0}).status_code == 422
    assert client.get('/api/lessons/missing').status_code == 404

    # The game move: right for the book, an inaccuracy for Stockfish, which prefers Nf6.
    answer = client.post('/api/lessons/lc-05-qe7/answer', json={'move': 'd8e7', 'hints': 0}).json()
    assert answer['success'] and answer['verdict'] == 'game' and answer['counted'] and answer['stage'] == 1
    assert answer['engine']['lines'][0]['san'] == 'Nf6' and answer['engine']['move']['label'] == 'Imprecisione'
    assert answer['engineNote'] and answer['bookIdea'] and not answer['engine']['move']['live']
    assert answer['moves'][0]['san'] == 'Qe7' and {m['verdict'] for m in answer['moves']} >= {'game', 'good', 'weak'}
    # Answering again before the review is due is practice: it does not move the schedule.
    again = client.post('/api/lessons/lc-05-qe7/answer', json={'move': 'a7a6', 'hints': 0}).json()
    assert not again['success'] and not again['counted'] and again['stage'] == 1 and again['status'] == 'waiting'

    # An alternative the lesson accepts counts as right; with hints it does not step the review forward.
    good = client.post('/api/lessons/lc-01-nf3/answer', json={'move': 'g1f3', 'hints': 2}).json()
    assert good['success'] and good['stage'] == 0 and good['counted']
    # A move outside the list is judged live by the engine and never counts as the lesson's answer.
    other = client.post('/api/lessons/lc-02-nc6/answer', json={'move': 'b8a6', 'hints': 0}).json()
    assert other['verdict'] == 'other' and not other['success'] and other['engine']['move']['live']
    assert other['engine']['move']['san'] == 'Na6' and other['engine']['move']['loss'] > 0

    overview = client.get('/api/lessons').json()
    states = {l['id']: l for l in overview['lessons']}
    assert states['lc-05-qe7']['status'] == 'waiting' and states['lc-01-nf3']['status'] == 'waiting'
    assert overview['next'] == 'lc-03-bc4' and overview['nextDue']

    # Five hours later the failed and assisted lessons are due again; the first right answer waits 4 hours too.
    with main.database() as con:
        con.execute('UPDATE lesson_progress SET due_at=?', ((datetime.fromisoformat(main.now()) - timedelta(minutes=1)).isoformat(),))
    overview = client.get('/api/lessons').json()
    assert overview['due'] == 3 and overview['next'] in {'lc-01-nf3', 'lc-02-nc6', 'lc-05-qe7'}


def test_the_followed_game_replays_and_says_where_book_and_engine_disagree():
    data = lessons.load()
    assert lessons.validate_walks(data) == []
    assert [w['id'] for w in data['walks']] == ['partita-1', 'partita-2', 'partita-3', 'partita-6', 'partita-7', 'partita-10', 'partita-12', 'partita-14', 'partita-24']
    walk = lessons.walk_by_id('partita-1')
    assert walk['side'] == 'b' and len(lessons.walk_plies(walk)) == 17
    assert lessons.replay([m['san'] for m in walk['moves']]).fen().startswith('r3k2r/1pp2ppp/p2p4/P7/2B1P1n1/2P2Nq1/1P3b2/R1BQ1R1K w')
    for followed in data['walks']:
        assert followed['summary'] and followed['result'] in ('1-0', '0-1') and followed['game'] in data['games']
        for ply in lessons.walk_plies(followed):
            entry, lesson, *_ = lessons.walk_step(followed, ply)
            analysis = entry['engine']
            if not lesson and lessons.review_loss(analysis['lines'][0], analysis['moves'][entry['san']]) >= INACCURACY_CP:
                assert entry.get('engineNote'), (followed['id'], entry['san'])
    # Every lesson of a followed game is one of its moves: the book games 2, 10, 14 and 24 carry the other lessons.
    linked = {m['lesson'] for w in data['walks'] for m in w['moves'] if m.get('lesson')}
    assert linked == {l['id'] for l in data['lessons']} - {'lc-01-nf3', 'lc-03-bc4'}
    # The lesson moves of the game are the lessons themselves.
    assert [lessons.walk_step(walk, p)[1]['id'] for p in (3, 5, 7)] == ['lc-02-nc6', 'lc-04-bc5', 'lc-05-qe7']


def test_walk_validation_catches_broken_games():
    data = lessons.load()
    walk = data['walks'][0]
    moves = [dict(m) for m in walk['moves']]
    moves[1] = {**moves[1], 'san': 'e4'}
    errors = '\n'.join(lessons.validate_walks({**data, 'walks': [{**walk, 'moves': moves}]}, engine=False))
    assert 'mossa illegale' in errors
    moves = [dict(m) for m in walk['moves']]
    moves[9] = {**moves[9], 'lesson': 'lc-02-nc6'}
    moves[11] = {k: v for k, v in moves[11].items() if k != 'question'}
    errors = '\n'.join(lessons.validate_walks({**data, 'walks': [{**walk, 'moves': moves}]}, engine=False))
    assert 'non è questa posizione' in errors and 'servono una domanda' in errors


def test_following_a_game_plays_the_other_side_and_scores_first_answers(client):
    overview = client.get('/api/lesson-walks').json()['walks']
    assert overview[0]['id'] == 'partita-1' and overview[0]['total'] == 17 and overview[0]['current'] is None
    assert client.post('/api/lesson-walks/missing/start').status_code == 404

    step = client.post('/api/lesson-walks/partita-1/start').json()
    run = step['run']['id']
    assert step['ply'] == 1 and step['number'] == 1 and step['turn'] == 'b' and step['line'] == '1.e4'
    assert [r['san'] for r in step['replies']] == ['e4'] and step['replies'][0]['note'] and len(step['hints']) == 2
    assert 'played' not in step and 'moves' not in step
    assert client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 2, 'move': 'g1f3', 'hints': 0}).status_code == 422
    assert client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 1, 'move': 'e2e4', 'hints': 0}).status_code == 422
    assert client.post('/api/lesson-walks/partita-1/answer', json={'run': 'nope', 'ply': 1, 'move': 'e7e5', 'hints': 0}).status_code == 404

    answer = client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 1, 'move': 'e7e5', 'hints': 0}).json()
    assert answer['success'] and answer['counted'] and answer['nextPly'] == 3 and not answer['finished']
    assert answer['run']['found'] == 1 and answer['run']['clean'] == 1 and answer['fenAfter'].startswith('rnbqkbnr/pppp1ppp/8/4p3/4P3')
    # A second try at the same move is practice: it does not change the score.
    again = client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 1, 'move': 'a7a6', 'hints': 0}).json()
    assert not again['success'] and not again['counted'] and again['run']['answered'] == 1

    # The opponent's move comes with the next step, with its note and Stockfish's judgement.
    step = client.get(f'/api/lesson-walks/partita-1/runs/{run}').json()
    assert step['ply'] == 3 and [r['san'] for r in step['replies']] == ['Nf3'] and step['lesson'] == 'lc-02-nc6'
    assert step['question'] == lessons.lesson_by_id('lc-02-nc6')['question'] and step['replies'][0]['engine']['label']
    # A lesson move accepts the lesson's alternatives; with a hint it is found but not clean.
    answer = client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 3, 'move': 'd7d6', 'hints': 1}).json()
    assert answer['verdict'] in ('good', 'partial') and answer['played'] == 'Nc6' and answer['explanation']

    # 8...Ba7: right for the book, while Stockfish prefers Nxa5; the answer says so.
    walk = lessons.walk_by_id('partita-1')
    answer = client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 15, 'move': 'a7a6', 'hints': 0})
    assert answer.status_code == 422
    answer = client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': 15, 'move': 'c6a5', 'hints': 0}).json()
    assert answer['verdict'] == 'good' and answer['engineNote'] and answer['engine']['played']['san'] == 'Ba7'

    for ply in [p for p in lessons.walk_plies(walk) if p not in (1, 3, 15)]:
        board = lessons.replay([m['san'] for m in walk['moves'][:ply]])
        uci = board.parse_san(walk['moves'][ply]['san']).uci()
        last = client.post('/api/lesson-walks/partita-1/answer', json={'run': run, 'ply': ply, 'move': uci, 'hints': 0}).json()
    assert last['finished'] and last['result'] == '0-1' and last['ending'] and last['tail'] == [] and last['engineNote']
    assert last['run']['answered'] == 17 and last['run']['finishedAt'] and last['run']['found'] >= 16
    assert client.get(f'/api/lesson-walks/partita-1/runs/{run}').status_code == 409
    overview = client.get('/api/lesson-walks').json()['walks'][0]
    assert overview['current'] is None and overview['best']['found'] == last['run']['found']


def test_following_a_game_as_white_starts_with_your_move(client):
    step = client.post('/api/lesson-walks/partita-24/start').json()
    run = step['run']['id']
    assert step['ply'] == 0 and step['turn'] == 'w' and step['replies'] == [] and step['line'] == '' and step['run']['total'] == 20
    answer = client.post('/api/lesson-walks/partita-24/answer', json={'run': run, 'ply': 0, 'move': 'e2e4', 'hints': 0}).json()
    assert answer['success'] and answer['verdict'] == 'good' and answer['played'] == 'd4' and answer['nextPly'] == 2
    step = client.get(f'/api/lesson-walks/partita-24/runs/{run}').json()
    assert step['ply'] == 2 and [r['san'] for r in step['replies']] == ['Nf6'] and not step['replies'][0]['white']
    # 12.Rab1 is lesson lc-10: the walk asks the lesson's question.
    walk = lessons.walk_by_id('partita-24')
    assert lessons.walk_step(walk, 22)[1]['id'] == 'lc-10-rab1'


def test_a_lesson_answer_plays_the_game_move_and_leads_into_the_followed_game(client):
    answer = client.post('/api/lessons/lc-01-nf3/answer', json={'move': 'b1c3', 'hints': 0}).json()
    assert answer['playedUci'] == 'g1f3' and answer['fenAfter'].startswith('rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/')
    assert answer['walk'] == {'id': 'partita-1', 'ply': 3, 'number': 2}
    assert client.post('/api/lessons/lc-05-qe7/answer', json={'move': 'd8e7', 'hints': 0}).json()['walk']['ply'] == 9
    # A white lesson leads into a game followed as White.
    assert client.post('/api/lessons/lc-08-c3/answer', json={'move': 'c2c3', 'hints': 0}).json()['walk'] == {'id': 'partita-10', 'ply': 12, 'number': 7}

    # A run started from the lesson begins at that move; it scores only the moves from there to the end.
    assert client.post('/api/lesson-walks/partita-1/start', json={'ply': 8}).status_code == 422
    step = client.post('/api/lesson-walks/partita-1/start', json={'ply': 9}).json()
    assert step['ply'] == 9 and step['number'] == 5 and [r['san'] for r in step['replies']] == ['O-O']
    assert step['run']['total'] == 13 and step['run']['fromNumber'] == 5 and step['line'].endswith('4.c3 Qe7 5.O-O')
    walk = lessons.walk_by_id('partita-1')
    for ply in [p for p in lessons.walk_plies(walk) if p >= 9]:
        board = lessons.replay([m['san'] for m in walk['moves'][:ply]])
        last = client.post('/api/lesson-walks/partita-1/answer', json={'run': step['run']['id'], 'ply': ply,
                                                                       'move': board.parse_san(walk['moves'][ply]['san']).uci(), 'hints': 0}).json()
    assert last['finished'] and last['run']['answered'] == 13 and last['run']['found'] == 13
    # Only runs from the first move compete for the best score.
    assert client.get('/api/lesson-walks').json()['walks'][0]['best'] is None
