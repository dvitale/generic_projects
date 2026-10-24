import random
import chess
import pytest
from tactical_matches import choose, play_game


class Uniform:
    def predict(self,fen,elo):
        moves = list(chess.Board(fen).legal_moves)
        return {'moves':[{'uci':m.uci(),'probability':1/len(moves)} for m in moves]}


def test_sampling_is_reproducible_and_validated():
    board = chess.Board()
    prediction = Uniform().predict(board.fen(),600)
    assert choose(prediction,board,random.Random(5)) == choose(prediction,board,random.Random(5))
    with pytest.raises(ValueError,match='mismatch'):
        choose({'moves':prediction['moves'][:2]},board,random.Random(5))
    prediction['moves'][0]['probability'] = float('nan')
    with pytest.raises(ValueError,match='probabilities'):
        choose(prediction,board,random.Random(5))


def test_truncated_game_is_not_a_win_and_pgn_keeps_opening():
    result = play_game({'a':Uniform(),'b':Uniform()},{True:'a',False:'b'},5,['e2e4','e7e5'],max_plies=3)
    assert result['result'] == '*'
    assert result['termination'] == 'PLY_LIMIT'
    assert result['plies'] == 3
    assert result['decisions'][0]['ply'] == 2
    assert '1. e4 e5' in result['pgn']


def test_completed_game_reports_mate():
    result = play_game({'a':Uniform(),'b':Uniform()},{True:'a',False:'b'},5,
                       ['f2f3','e7e5','g2g4','d8h4'],max_plies=3)
    assert result['result'] == '0-1'
    assert result['termination'] == 'CHECKMATE'
    assert result['plies'] == 0
