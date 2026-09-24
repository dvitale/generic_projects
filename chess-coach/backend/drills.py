"""Small curated repertoire. Selection and evidence stay separate from chess engines."""
import chess

CATALOG = [
    {"id": "italiana", "name": "Partita italiana", "kind": "opening", "theme": "Sviluppo e sicurezza del re",
     "san": "e4 e5 Nf3 Nc6 Bc4 Bc5", "goal": "Completa lo sviluppo e prepara l'arrocco, rispondendo alle minacce."},
    {"id": "siciliana", "name": "Difesa siciliana", "kind": "opening", "theme": "Calcolo e mosse candidate",
     "san": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6", "goal": "Confronta sviluppo, controllo del centro e mosse attive."},
    {"id": "caro-kann", "name": "Difesa Caro-Kann", "kind": "opening", "theme": "Sviluppo e sicurezza del re",
     "san": "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5", "goal": "Sviluppa i pezzi senza trascurare la sicurezza del re."},
    {"id": "gambetto-donna", "name": "Gambetto di donna", "kind": "opening", "theme": "Calcolo e mosse candidate",
     "san": "d4 d5 c4 e6 Nc3 Nf6", "goal": "Scegli un piano di sviluppo coerente e controlla le catture centrali."},
    {"id": "torre-re", "name": "Re e torre contro re", "kind": "endgame", "theme": "Tecnica dei finali",
     "fen": "8/8/4k3/8/8/4K3/8/R7 w - - 0 1", "color": "w",
     "goal": "Riduci lo spazio del re avversario e coordina re e torre, evitando lo stallo."},
]


def materialize(template):
    board = chess.Board(template.get("fen", chess.STARTING_FEN))
    initial = board.fen()
    for san in template.get("san", "").split():
        board.push_san(san)
    assert board.is_valid()
    return initial, [move.uci() for move in board.move_stack], board.fen()


def decisions_played(initial_fen, moves, start_ply, color):
    starting_color = chess.Board(initial_fen).turn
    return sum(1 for i in range(start_ply, len(moves)) if (starting_color if i % 2 == 0 else not starting_color) == (color == "w"))
