import io
import json
from datetime import datetime, timedelta, timezone

import chess
import chess.pgn

from backend import main, study, tutor
from test_coach import client

# After 1.e4 e5 2.Nf3 Nc6: 3.Nxe5? loses the knight to 3...Nxe5.
FEN = 'r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3'


def analysed_game(client):
    g = client.post('/api/games', json={'fen': FEN, 'title': 'Studio'}).json()
    client.post(f"/api/games/{g['id']}/moves", json={'move': 'f3e5', 'version': 0, 'actor': 'human'})
    with main.database() as con:
        snapshot = dict(main.find_game(con, g['id']))
    main.jobs['study'] = {'gameId': g['id'], 'status': 'running', 'progress': 0}
    main.analyze_game('study', snapshot)
    assert main.jobs['study']['status'] == 'complete', main.jobs['study']
    return g['id']


def seed_exercises(count):
    fens = ['7k/8/5KQ1/8/8/8/8/8 w - - 0 1', FEN, '6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1',
            'r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4']
    themes = ['Riconoscere il matto', 'Conseguenze tattiche', 'Riconoscere il matto', 'Conseguenze tattiche']
    with main.database() as con:
        con.execute("INSERT INTO games(id,initial_fen,moves,player_color,elo,title,created_at,analysis,analysis_version,source) VALUES('seed',?,?,?,?,?,?,?,?,?)",
                    (FEN, '[]', 'w', 1500, 'Seed', main.now(), None, None, 'pgn'))
        for i in range(count):
            con.execute('INSERT INTO exercises(id,game_id,ply,initial_fen,history,theme,best_move,loss,due_at) VALUES(?,?,?,?,?,?,?,?,?)',
                        (f'ex{i}', 'seed', i, fens[i], '[]', themes[i], 'a1a1', 500, main.now()))


def test_note_cards_follow_self_rated_intervals(client):
    assert client.post('/api/study/cards', json={'fen': FEN, 'lesson': 'Chi difende e5?', 'move': 'e1e3'}).status_code == 422
    card = client.post('/api/study/cards', json={'fen': FEN, 'lesson': 'Chi difende e5?', 'move': 'f3e5', 'bestMove': 'f1c4'}).json()
    assert card['san'] == 'Nxe5' and card['bestSan'] == 'Bc4' and 'Nxe5' in card['question']
    assert card['preview'] == {'again': 0, 'hard': 1, 'good': 1, 'easy': 4}
    overview = client.get('/api/study/cards').json()
    assert [c['id'] for c in overview['due']] == [card['id']] and overview['total'] == 1
    good = client.post(f"/api/study/cards/{card['id']}/review", json={'rating': 'good'}).json()
    assert good['reps'] == 1 and good['intervalDays'] == 1 and good['preview']['good'] == 3
    assert client.get('/api/study/cards').json()['due'] == []
    # Not due any more: a second rating would inflate the interval.
    assert client.post(f"/api/study/cards/{card['id']}/review", json={'rating': 'easy'}).status_code == 409
    with main.database() as con:
        con.execute('UPDATE study_cards SET due_at=? WHERE id=?', (main.now(), card['id']))
    again = client.post(f"/api/study/cards/{card['id']}/review", json={'rating': 'again'}).json()
    assert again['reps'] == 0 and again['lapses'] == 1 and again['intervalDays'] == 0
    due = datetime.fromisoformat(again['dueAt']) - datetime.now(timezone.utc)
    assert timedelta(minutes=9) < due <= timedelta(minutes=10)
    assert client.post(f"/api/study/cards/{card['id']}/archive").json() == {'archived': True}
    assert client.get('/api/study/cards').json()['total'] == 0


def test_explained_mistakes_become_cards_unless_the_deeper_search_accepts_them(client):
    seed_exercises(1)
    board = chess.Board('7k/8/5KQ1/8/8/8/8/8 w - - 0 1')
    evidence = {'fen': board.fen(), 'turn': 'w', 'move': 'g6g8', 'san': 'Qg8+', 'best': {}, 'actual': {}, 'lossCp': None}
    with main.database() as con:
        for mistake, accepted in ((1, False), (2, True)):
            con.execute('INSERT INTO training_mistakes VALUES(?,?,?,?,?,?)', (mistake, 'puzzle', 'ex0', mistake, main.now(), json.dumps(evidence)))
            response = {'explanation': {'lesson': 'Controlla chi difende la casa d’arrivo.'},
                        'comparison': {'best': {'pv': ['g6g7'], 'san': ['Qg7#']}, 'verification': {'acceptedNow': accepted}}}
            con.execute('INSERT INTO mistake_explanations VALUES(?,?,?)', (f'k{mistake}', mistake, json.dumps(response)))
    cards = client.get('/api/study/cards').json()['due']
    assert len(cards) == 1
    card = cards[0]
    assert card['kind'] == 'explanation' and card['bestSan'] == 'Qg7#' and card['theme'] == 'Riconoscere il matto'
    assert card['gameId'] == 'seed' and card['lesson'].startswith('Controlla')
    # The sync is idempotent.
    assert client.get('/api/study/cards').json()['total'] == 1


def test_recall_quiz_is_engine_verified_and_keeps_the_first_answer(client):
    game_id = analysed_game(client)
    quiz = client.get(f'/api/study/games/{game_id}/quiz').json()
    kinds = [q['kind'] for q in quiz['questions']]
    assert kinds[:2] == ['best', 'refutation'] and 'evaluation' in kinds
    assert all('answer' not in q and 'result' not in q for q in quiz['questions'])
    refutation = next(q for q in quiz['questions'] if q['kind'] == 'refutation')
    labels = [o['label'] for o in refutation['options']]
    assert 'Nxe5' in labels and len(labels) >= 2
    wrong = next(i for i, o in enumerate(refutation['options']) if o['label'] != 'Nxe5')
    path = f"/api/study/quizzes/{quiz['id']}/answers"
    result = client.post(path, json={'question': refutation['index'], 'choice': wrong}).json()
    answered = result['questions'][refutation['index']]['result']
    assert not answered['correct'] and refutation['options'][answered['answer']]['label'] == 'Nxe5'
    # A later, correct answer does not overwrite the first one.
    client.post(path, json={'question': refutation['index'], 'choice': answered['answer']})
    again = client.get(f'/api/study/games/{game_id}/quiz').json()
    assert again['id'] == quiz['id'] and again['answered'] == 1 and again['score'] == 0
    evaluation = next(q for q in quiz['questions'] if q['kind'] == 'evaluation')
    result = client.post(path, json={'question': evaluation['index'], 'choice': 2}).json()
    assert result['questions'][evaluation['index']]['result']['correct']
    assert client.post(path, json={'question': 0, 'choice': 5}).status_code == 422


def test_game_pack_links_every_training_activity(client):
    game_id = analysed_game(client)
    client.post('/api/study/cards', json={'fen': FEN, 'lesson': 'Il cavallo c6 difende e5.', 'gameId': game_id, 'ply': 0})
    pack = client.get(f'/api/study/games/{game_id}/pack').json()
    moment = pack['moments'][0]
    assert moment['playedSan'] == 'Nxe5' and moment['refutation'][0] == 'Nxe5'
    assert moment['exerciseId'] and moment['preventionId'] and moment['cards'] == 1
    assert pack['quiz'] is None
    client.get(f'/api/study/games/{game_id}/quiz')
    assert client.get(f'/api/study/games/{game_id}/pack').json()['quiz']['answered'] == 0
    fresh = client.post('/api/games', json={}).json()
    assert client.get(f"/api/study/games/{fresh['id']}/pack").status_code == 409


def test_mock_exam_interleaves_themes_hides_feedback_and_skips_the_schedule(client):
    assert client.post('/api/study/exams', json={'size': 4}).status_code == 422
    seed_exercises(4)
    exam = client.post('/api/study/exams', json={'size': 4, 'minutes': 5}).json()
    assert exam['size'] == 4 and all('theme' not in item and 'exerciseId' not in item for item in exam['items'])
    themes = {f'ex{i}': t for i, t in enumerate(['Riconoscere il matto', 'Conseguenze tattiche'] * 2)}
    assert client.post('/api/study/exams', json={}).status_code == 409
    first = exam['items'][0]
    move = 'g6g7' if first['fen'].startswith('7k/8/5KQ1') else first['legalMoves'][0]
    answer = client.post(f"/api/study/exams/{exam['id']}/answers", json={'item': 0, 'move': move}).json()
    assert answer == {'recorded': True, 'answered': 1}
    assert client.post(f"/api/study/exams/{exam['id']}/answers", json={'item': 0, 'move': move}).status_code == 409
    finished = client.post(f"/api/study/exams/{exam['id']}/finish").json()
    assert finished['finishedAt'] and finished['answered'] == 1
    picked = [item['exerciseId'] for item in finished['items']]
    assert themes[picked[0]] != themes[picked[1]]
    assert sum(t['total'] for t in finished['themes']) == 4
    assert all(not item['success'] for item in finished['items'][1:])
    assert client.post(f"/api/study/exams/{exam['id']}/answers", json={'item': 1, 'move': finished['items'][1]['legalMoves'][0]}).status_code == 409
    with main.database() as con:
        assert con.execute('SELECT count(*) FROM attempts').fetchone()[0] == 0
        assert con.execute('SELECT count(*) FROM training_reviews').fetchone()[0] == 0
    history = client.get('/api/study/exams').json()
    assert history['active'] is None and history['history'][0]['size'] == 4 and history['nextRecommended']


def test_expired_exam_closes_at_the_deadline(client):
    seed_exercises(3)
    exam = client.post('/api/study/exams', json={'size': 4, 'minutes': 3}).json()
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with main.database() as con:
        con.execute('UPDATE study_exams SET deadline=? WHERE id=?', (past, exam['id']))
    item = exam['items'][0]
    assert client.post(f"/api/study/exams/{exam['id']}/answers", json={'item': 0, 'move': item['legalMoves'][0]}).status_code == 409
    history = client.get('/api/study/exams').json()
    assert history['active'] is None and history['history'][0]['score'] == 0


def test_moves_named_in_a_question_accept_italian_and_english_notation():
    board = chess.Board(FEN)
    assert [m.uci() for m in study.parse_moves(board, 'Perché non Cxe5? E Nxe5 o Ac4?')] == ['f3e5', 'f1c4']
    assert [m.uci() for m in study.parse_moves(board, 'e Td1?')] == []
    assert [m.uci() for m in study.parse_moves(board, 'perché d4 e non d2d3?')] == ['d2d4', 'd2d3']
    # A square next to a piece move is not read as a pawn move.
    assert [m.uci() for m in study.parse_moves(board, 'il cavallo in f3 può giocare Cg5?')] == ['f3g5']
    assert study.unverified_citations('Dopo Cxe5 Nxe5 la casa e5 cade; Qh5 no.', {'Nxe5'}) == ['Qh5']


def test_position_question_without_llm_answers_from_stockfish(client, monkeypatch):
    monkeypatch.setattr(tutor, 'configuration', lambda: ('', 'deepseek-flash'))
    result = client.post('/api/study/ask', json={'fen': FEN, 'question': 'Perché non Cxe5?'}).json()
    assert result['provider'] == 'Stockfish' and result['moves'][0]['san'] == 'Nxe5'
    assert result['moves'][0]['lossCp'] >= 150 and result['moves'][0]['line'][1] == 'Nxe5'
    assert 'Nxe5' in result['answer'] and result['best']['san']
    assert client.post('/api/study/ask', json={'fen': 'bad', 'question': 'ok?'}).status_code == 422


def test_position_answer_with_unverified_moves_is_replaced_by_engine_facts(client, monkeypatch):
    monkeypatch.setattr(tutor, 'configuration', lambda: ('key', 'deepseek-flash'))
    replies = iter([json.dumps({'answer': 'Nxe5 perde il cavallo dopo Nxe5.', 'lesson': 'Conta i difensori.'}),
                    json.dumps({'answer': 'Dopo Nxe5 gioca Rh7 e vinci.', 'lesson': 'Attacca.'})])
    monkeypatch.setattr(tutor, 'request_json', lambda context, model, system: (next(replies), {'total_tokens': 1}))
    ok = client.post('/api/study/ask', json={'fen': FEN, 'question': 'Perché non Nxe5?'}).json()
    assert ok['provider'] == 'DeepSeek' and ok['lesson'] == 'Conta i difensori.'
    invented = client.post('/api/study/ask', json={'fen': FEN, 'question': 'Perché non Nxe5?'}).json()
    # Rh7 is not even legal here: it cannot appear in a verified line.
    assert invented['provider'] == 'Stockfish' and 'notice' in invented and 'Rh7' not in invented['answer']


def test_notebook_groups_errors_by_theme_and_exports_annotated_pgn(client):
    game_id = analysed_game(client)
    client.post('/api/study/cards', json={'fen': FEN, 'lesson': 'Il cavallo c6 difende e5.', 'gameId': game_id, 'ply': 0})
    themes = client.get('/api/study/notebook').json()['themes']
    example = next(t for t in themes if t['examples'])['examples'][0]
    assert example['playedSan'] == 'Nxe5' and example['lessons'] == ['Il cavallo c6 difende e5.']
    assert any('Il cavallo c6 difende e5.' in t['lessons'] for t in themes)
    response = client.get('/api/study/notebook.pgn')
    assert response.status_code == 200 and 'quaderno' in response.headers['content-disposition']
    game = chess.pgn.read_game(io.StringIO(response.text))
    assert game.headers['Event'].startswith('Quaderno degli errori')
    assert game.next().san() == 'Nxe5' and 'Lezione: Il cavallo c6 difende e5.' in game.next().comment
    assert len(game.variations) == 2 and game.variations[1].comment == 'Alternativa di Stockfish'
