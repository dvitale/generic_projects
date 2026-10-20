"""Chess encoding shared by preprocessing and inference; no neural dependencies."""
import chess

PROMOTIONS = (None, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


def move_id(move):
    return (move.from_square * 64 + move.to_square) * 5 + PROMOTIONS.index(move.promotion)


def encode(board, rating):
    pieces = [0] * 64
    for square, piece in board.piece_map().items():
        pieces[square] = piece.piece_type + (0 if piece.color else 6)
    ep = [int(square == board.ep_square) for square in range(64)]
    context = [
        (rating - 1500) / 1000, float(board.turn),
        float(board.has_kingside_castling_rights(chess.WHITE)),
        float(board.has_queenside_castling_rights(chess.WHITE)),
        float(board.has_kingside_castling_rights(chess.BLACK)),
        float(board.has_queenside_castling_rights(chess.BLACK)),
        min(board.halfmove_clock, 150) / 150,
        min(board.fullmove_number, 200) / 200,
    ]
    return pieces, ep, context
