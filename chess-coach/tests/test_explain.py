import chess
from backend import explain, insights
from test_insights import value


def why(fen, best, actual, best_cp=0, actual_cp=-400, best_mate=None, actual_mate=None):
    b = chess.Board(fen)
    return explain.explain(fen, actual[0], value(b, best, best_cp, best_mate), value(b, actual, actual_cp, actual_mate))


def test_a_free_pawn_that_leaves_the_queen_en_prise():
    result = why('rnbqkb1r/pp2pppp/2p2n2/3p4/2PP4/1Q6/PP2PPPP/RNB1KBNR w KQkq - 0 4', ['g1f3', 'd5c4'], ['b3b7', 'c8b7', 'g1f3'])
    assert result['motif'] == 'hanging' and result['focus'] == ['b7']
    assert result['text'] == 'Qxb7 prende un pedone, ma la donna in b7 non è difesa: 4… Bxb7 la cattura.'
    assert result['line'] == ['b3b7', 'c8b7', 'g1f3'] and result['better'].startswith('Stockfish preferisce Nf3')


def test_moving_the_only_defender_and_ignoring_an_existing_attack():
    moved = why('4r1k1/5ppp/8/4B3/8/5N2/5PPP/6K1 w - - 0 1', ['e5c3', 'e8e2'], ['f3g5', 'e8e5', 'g5f3'])
    assert moved['motif'] == 'undefended'
    assert moved['text'] == 'Ng5 sposta il cavallo da f3 e lascia senza difesa l’alfiere in e5: 1… Rxe5 lo cattura.'
    ignored = why('4r1k1/5ppp/8/4B3/8/8/5PPP/6K1 w - - 0 1', ['e5c3', 'e8e2'], ['h2h3', 'e8e5'])
    assert ignored['motif'] == 'ignored_threat'
    assert ignored['text'] == 'L’alfiere in e5 era già attaccato e h3 non lo protegge: 1… Rxe5 lo cattura.'


def test_knight_fork_and_the_winning_alternative():
    result = why('r3k3/8/8/8/3n4/8/7P/R3K3 w Q - 0 1', ['a1a8'], ['h2h3', 'd4c2', 'e1d2', 'c2a1'], best_cp=900)
    assert result['motif'] == 'fork' and result['focus'] == ['c2', 'e1', 'a1']
    assert 'attacca insieme il re in e1 e la torre in a1 (forchetta)' in result['text']
    assert result['better'] == 'Con Rxa8+ vincevi una torre: 1. Rxa8+.'


def test_a_slow_trap_for_a_greedy_bishop():
    result = why('2k5/pp6/8/8/3B4/8/5PPP/6K1 w - - 0 1', ['h2h4', 'b7b6'], ['d4a7', 'b7b6', 'h2h3', 'c8b7', 'g2g4', 'b7a7'])
    assert result['motif'] == 'trapped'
    assert result['text'] == 'Bxa7 prende un pedone, ma l’alfiere in a7 resta intrappolato: dopo 1… b6 e 2… Kb7 non ha più case sicure.'


def test_mates_for_and_against_the_player():
    back_rank = why('4r1k1/5ppp/8/8/8/8/5PPP/3R2K1 b - - 0 1', ['h7h6', 'd1d7'], ['e8e7', 'd1d8', 'e7e8', 'd8e8'], actual_mate=-2)
    assert back_rank['motif'] == 'mate' and back_rank['text'].startswith('Dopo Re7 il Bianco ha un matto in 2: 2. Rd8+ Re8 3. Rxe8#.')
    assert back_rank['text'].endswith('Il tuo re è chiuso sulla traversa dai suoi stessi pezzi.')
    missed = why('6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1', ['d1d8'], ['d1d7', 'g8f8'], best_cp=100000, actual_cp=0, best_mate=1)
    assert missed['motif'] == 'missed_mate' and missed['text'] == 'Avevi un matto in 1: 1. Rd8#. Rd7 lo lascia sfuggire.'
    assert missed['better'] is None


def test_no_material_loss_is_described_as_positional_or_left_to_the_engine_line():
    b = chess.Board(); b.push_san('e4'); b.push_san('e5')
    result = why(b.fen(), ['g1f3', 'b8c6'], ['e1e2', 'g8f6'], best_cp=50, actual_cp=-100)
    assert result['motif'] == 'positional' and 'pedoni davanti al tuo re' in result['text']
    quiet = why('7k/8/8/8/8/8/8/K7 w - - 0 1', ['a1a2', 'h8g7'], ['a1b1', 'h8g8', 'b1c2'], best_cp=50, actual_cp=-300)
    assert quiet['motif'] == 'engine' and quiet['title'] == 'Deriva dalla linea di Stockfish'
    assert quiet['text'] == 'Linea di Stockfish: 1. Kb1 Kg8 2. Kc2.' and quiet['line'] == ['a1b1', 'h8g8', 'b1c2']


def test_a_move_that_loses_nothing_but_misses_a_won_piece_is_a_missed_gain():
    # Game 102, 5. Nf3?: 5. d3 wins the e4 knight (it cannot move because of Ng6+), the move played only keeps equality.
    fen = 'rnb1kb1r/pppp1ppp/8/4N3/4n2q/8/PPPPQPPP/RNB1KB1R w KQkq - 2 5'
    result = why(fen, ['d2d3', 'h4f2', 'e2f2', 'e4f2', 'e1f2', 'f8c5', 'c1e3', 'c5e3', 'f2e3', 'd7d5'],
                 ['e5f3', 'h4e7', 'b1c3', 'e4c3', 'd2c3', 'e7e2', 'f1e2', 'b8c6'], best_cp=634, actual_cp=30)
    assert result['motif'] == 'missed_gain' and result['title'] == 'Occasione mancata'
    assert result['text'] == 'Nf3 non perde materiale, ma lascia sfuggire un’occasione: c’era una mossa che vinceva un cavallo.'
    assert result['better'].startswith('Con d3 vincevi un cavallo, in cambio di un pedone: 5. d3 Qxf2+') and result['bestWins']


def test_small_losses_and_best_moves_have_no_explanation():
    b = chess.Board()
    assert why(b.fen(), ['e2e4'], ['e2e3'], best_cp=30, actual_cp=0) is None
    assert why(b.fen(), ['e2e4'], ['e2e4'], best_cp=30, actual_cp=30) is None


def test_insights_carry_the_explanation():
    b = chess.Board('4r1k1/5ppp/8/4B3/8/8/5PPP/6K1 w - - 0 1')
    result = insights.public(insights.compare(b.fen(), 'h2h3', value(b, ['e5c3', 'e8e2'], 0), value(b, ['h2h3', 'e8e5'], -400)))
    assert insights.VERSION == 10 and result['explanation']['motif'] == 'ignored_threat'


def test_a_line_cut_in_the_middle_of_an_exchange_does_not_hide_a_lost_piece():
    # Real game: Ba4 drops the knight, while Stockfish's Rad1 line stops before White recaptures on d5.
    fen = 'r3r1k1/5pp1/p1bb1q1p/2p5/8/1BN5/PPP2PPP/R3RQK1 w - - 0 18'
    result = why(fen, ['a1d1', 'e8e1', 'f1e1', 'a8e8', 'e1d2', 'd6e5', 'c3d5', 'c6d5'],
                 ['b3a4', 'c6a4', 'c3a4', 'f6f4', 'g2g3', 'f4a4', 'b2b3', 'a4c6'], best_cp=21, actual_cp=-570)
    assert result['motif'] == 'material'
    assert result['text'].startswith('Dopo Ba4 la risposta più forte del Nero (18… Bxa4 19. Nxa4 Qf4')
    assert result['text'].endswith('ti costa un cavallo.')


def test_a_loss_found_only_in_the_pending_recapture_still_names_the_piece():
    # The line ends with the queen landing on h5, where the knight takes it: nothing is captured inside the line.
    result = why('6k1/8/5n2/8/8/8/7P/3Q2K1 w - - 0 1', ['d1d2', 'g8h8'], ['h2h3', 'g8h8', 'd1h5'], best_cp=900, actual_cp=0)
    assert result is not None and 'donna' in result['text']


def test_the_better_line_shows_every_capture_it_counts():
    # The queen falls on the seventh half-move: a text cut at six named a gain the line never showed.
    result = why(chess.STARTING_FEN, ['e2e4', 'e7e5', 'g1f3', 'b8c6', 'f1c4', 'd8g5', 'f3g5'], ['a2a3', 'e7e5'], best_cp=900, actual_cp=0)
    assert result['bestWins']
    assert result['better'] == 'Con e4 vincevi una donna: 1. e4 e5 2. Nf3 Nc6 3. Bc4 Qg5 4. Nxg5.'


def test_traded_pieces_cancel_and_the_pending_recapture_is_shown():
    # 4. d5 in a real game: the queens come off on d1, so dxe5 wins three pawns, not a queen and three pawns.
    fen = 'rn1qkbnr/ppp2ppp/3pb3/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 1 4'
    result = why(fen, ['d4e5', 'a7a6', 'c1f4', 'g8e7', 'e5d6', 'e7g6', 'd6c7', 'd8d1'], ['d4d5', 'e6d7'], best_cp=175, actual_cp=65)
    assert result['better'] == 'Con dxe5 vincevi tre pedoni: 4. dxe5 a6 5. Bf4 Ne7 6. exd6 Ng6 7. dxc7 Qxd1+ 8. Kxd1.'
    assert result['bestLine'][-1] == 'e1d1' and result['bestWins']


def test_a_line_cut_before_a_forced_recapture_is_continued_until_the_exchange_ends():
    from backend.engine import evaluator
    board = chess.Board('r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4')
    settled = evaluator.settle(board, {'pv': ['b5c6'], 'san': ['Bxc6'], 'cp': 0, 'mate': None})
    assert settled['pv'][1] in ('d7c6', 'b7c6') and len(settled['pv']) == 3 and len(settled['san']) == 3
    # A line that ends on a quiet move stays as it is.
    quiet = {'pv': ['g1f3'], 'san': ['Nf3'], 'cp': 20, 'mate': None}
    assert evaluator.settle(chess.Board(), quiet) is quiet


def test_the_better_move_is_the_point_only_when_no_other_move_comes_close():
    fen = 'r3k3/8/8/8/3n4/8/7P/R3K3 w Q - 0 1'
    b = chess.Board(fen)
    best, actual = value(b, ['a1a8'], 900), value(b, ['h2h3', 'd4c2', 'e1d2', 'c2a1'], -400)
    # A rook move that wins almost as much: Rxa8+ is no longer presented as the one winning blow.
    close, far = value(b, ['a1a7'], 880), value(b, ['a1a7'], 300)
    shared = explain.explain(fen, 'h2h3', best, actual, [best, close])
    assert shared['motif'] == 'fork' and not shared['bestWins']
    assert shared['better'] == 'Stockfish preferisce Rxa8+: 1. Rxa8+. Quasi altrettanto buona era Ra7: non c’era un solo colpo da trovare.'
    assert explain.explain(fen, 'h2h3', best, actual, [best, far])['better'] == 'Con Rxa8+ vincevi una torre: 1. Rxa8+.'
    # The move played is never its own rival.
    assert explain.explain(fen, 'h2h3', best, actual, [best, actual])['better'] == 'Con Rxa8+ vincevi una torre: 1. Rxa8+.'


def test_a_recapture_that_opens_the_file_to_the_rook_is_not_a_trapped_knight():
    # Game 106: 7. b4? Bxb4 pins the knight, but the loss is the rook: 8. axb4 opens the a-file for Qxa1.
    fen = 'r1b1kb1r/ppp2ppp/2n1pn2/q7/3P4/P1N2N2/1PP2PPP/R1BQKB1R w KQkq - 1 7'
    result = why(fen, ['c1d2', 'a7a6', 'f1d3', 'a5b6'], ['b2b4', 'f8b4', 'a3b4', 'a5a1', 'c3b5', 'e8g8', 'b5c7', 'a8b8'],
                 best_cp=164, actual_cp=-356)
    assert result['motif'] == 'opened_line' and result['focus'] == ['a3', 'a1']
    assert result['text'] == ('Dopo b4, 7… Bxb4 prende un pedone: se lo riprendi con 8. axb4 liberi la linea a5–a1 '
                              'e 8… Qxa1 cattura la torre.')


def test_a_pin_that_wins_nothing_yet_is_named_with_what_saving_the_piece_costs():
    # Game 142, 10. Nc3?: 10... Bb4 pins the knight to the king, Ne4 attacks it too; a3 Bxc3+ bxc3 saves the material
    # but leaves doubled c-pawns and an isolated a-pawn, which 10. Nbd2 does not.
    fen = 'r2qk2r/ppp3pp/2nb1p2/5b2/4n2B/5N2/PPP1QPPP/RN2KB1R w KQkq - 2 10'
    result = why(fen, ['b1d2', 'd8e7', 'd2e4', 'f5e4', 'e1c1', 'e8c8', 'f3d2', 'e4f5', 'e2e7', 'd6e7'],
                 ['b1c3', 'd6b4', 'a2a3', 'b4c3', 'b2c3', 'd8d5', 'e2b5', 'e8c8', 'b5d5', 'd8d5'], best_cp=-58, actual_cp=-303)
    assert result['motif'] == 'pressure' and result['title'] == 'Pezzo inchiodato' and result['focus'] == ['c3', 'b4']
    assert result['text'].startswith('Dopo Nc3, 10… Bb4 inchioda il cavallo in c3 al re: è attaccato da due pezzi e difeso da uno solo.')
    assert result['text'].endswith('11. a3 Bxc3+ 12. bxc3 Qd5 13. Qb5 O-O-O 14. Qxd5 Rxd5 e ti restano pedoni doppiati in colonna c e un pedone isolato in a3.')
