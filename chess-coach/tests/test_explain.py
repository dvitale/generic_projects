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


def test_no_material_loss_is_described_as_a_positional_or_unclear_cause():
    b = chess.Board(); b.push_san('e4'); b.push_san('e5')
    result = why(b.fen(), ['g1f3', 'b8c6'], ['e1e2', 'g8f6'], best_cp=50, actual_cp=-100)
    assert result['motif'] == 'positional' and 'pedoni davanti al tuo re' in result['text']
    quiet = why('7k/8/8/8/8/8/8/K7 w - - 0 1', ['a1a2'], ['a1b1'], best_cp=50, actual_cp=-300)
    assert quiet['motif'] == 'unclear'


def test_small_losses_and_best_moves_have_no_explanation():
    b = chess.Board()
    assert why(b.fen(), ['e2e4'], ['e2e3'], best_cp=30, actual_cp=0) is None
    assert why(b.fen(), ['e2e4'], ['e2e4'], best_cp=30, actual_cp=30) is None


def test_insights_carry_the_explanation():
    b = chess.Board('4r1k1/5ppp/8/4B3/8/8/5PPP/6K1 w - - 0 1')
    result = insights.public(insights.compare(b.fen(), 'h2h3', value(b, ['e5c3', 'e8e2'], 0), value(b, ['h2h3', 'e8e5'], -400)))
    assert insights.VERSION == 4 and result['explanation']['motif'] == 'ignored_threat'


def test_a_line_cut_in_the_middle_of_an_exchange_does_not_hide_a_lost_piece():
    # Real game: Ba4 drops the knight, while Stockfish's Rad1 line stops before White recaptures on d5.
    fen = 'r3r1k1/5pp1/p1bb1q1p/2p5/8/1BN5/PPP2PPP/R3RQK1 w - - 0 18'
    result = why(fen, ['a1d1', 'e8e1', 'f1e1', 'a8e8', 'e1d2', 'd6e5', 'c3d5', 'c6d5'],
                 ['b3a4', 'c6a4', 'c3a4', 'f6f4', 'g2g3', 'f4a4', 'b2b3', 'a4c6'], best_cp=21, actual_cp=-570)
    assert result['motif'] == 'material'
    assert result['text'].startswith('Dopo Ba4 la risposta più forte del Nero (18… Bxa4 19. Nxa4 Qf4')
    assert 'ti costa un cavallo e un alfiere, in cambio di un alfiere' in result['text']
