"""One plain-language sentence on why a mistake loses, read from Stockfish's refutation line.

Each motif is claimed only when a board check confirms it (static exchange, attacks, legal
escapes) and the engine line agrees on the material outcome. Otherwise the text states what
the line shows and says the cause is not immediate."""
import chess

from .insights import VALUES, features, material

KING_VALUE = 100
NAMES = {chess.PAWN: ('pedone', 'pedoni', 'm'), chess.KNIGHT: ('cavallo', 'cavalli', 'm'),
         chess.BISHOP: ('alfiere', 'alfieri', 'm'), chess.ROOK: ('torre', 'torri', 'f'),
         chess.QUEEN: ('donna', 'donne', 'f'), chess.KING: ('re', 're', 'm')}
NUMBERS = {2: 'due', 3: 'tre', 4: 'quattro', 5: 'cinque', 6: 'sei', 7: 'sette', 8: 'otto'}
TITLES = {'mate': 'Matto contro', 'missed_mate': 'Matto non visto', 'hanging': 'Pezzo in presa',
          'undefended': 'Difesa tolta', 'ignored_threat': 'Minaccia non parata', 'opened_line': 'Linea aperta',
          'skewer': 'Infilata', 'fork': 'Attacco doppio', 'trapped': 'Pezzo intrappolato',
          'discovered': 'Attacco di scoperta', 'pin': 'Inchiodatura', 'promotion': 'Promozione avversaria',
          'material': 'Perdita di materiale', 'king': 'Re esposto', 'positional': 'Svantaggio di posizione',
          'unclear': 'Causa non immediata'}
MIN_LOSS = 80


def the(piece):
    name, _, gender = NAMES[piece.piece_type]
    return f"l’{name}" if name[0] in 'aeiou' else ('la ' if gender == 'f' else 'il ') + name


def one(piece):
    name, _, gender = NAMES[piece.piece_type]
    return ('una ' if gender == 'f' else 'un ') + name


def agree(piece, stem):
    return stem + ('a' if NAMES[piece.piece_type][2] == 'f' else 'o')


def pronoun(piece):
    return 'la' if NAMES[piece.piece_type][2] == 'f' else 'lo'


def pieces_text(pieces):
    """"due pedoni e un cavallo", largest first."""
    parts = []
    for kind in sorted({p.piece_type for p in pieces}, key=lambda t: -VALUES[t]):
        count = sum(p.piece_type == kind for p in pieces)
        sample = next(p for p in pieces if p.piece_type == kind)
        parts.append(one(sample) if count == 1 else f"{NUMBERS.get(count, count)} {NAMES[kind][1]}")
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' e ' + parts[-1]


def articled(preposition, side):
    """'del Nero' from 'il Nero': Italian merges the preposition with the article."""
    return side.replace('il ', preposition + ' ', 1)


def value(piece):
    return KING_VALUE if piece.piece_type == chess.KING else VALUES[piece.piece_type]


def see(board, square, by):
    """Material `by` wins by starting the captures on `square`, or 0 if capturing loses."""
    target = board.piece_at(square)
    if target is None or target.color != (not by):
        return 0
    cursor, side, victim, gains = board.copy(stack=False), by, value(target), []
    while True:
        attackers = list(cursor.attackers(side, square))
        if not attackers:
            break
        attacker = min(attackers, key=lambda s: value(cursor.piece_at(s)))
        gains.append(victim - (gains[-1] if gains else 0))
        victim = value(cursor.piece_at(attacker))
        cursor.set_piece_at(square, cursor.remove_piece_at(attacker))
        side = not side
    for i in range(len(gains) - 1, 0, -1):
        gains[i - 1] = -max(-gains[i - 1], gains[i])
    return max(gains[0], 0) if gains else 0


def unsafe(board, square):
    piece = board.piece_at(square)
    return piece is not None and see(board, square, not piece.color) > 0


def trapped(board, square):
    """The piece on `square` is lost where it stands and every legal escape loses it too."""
    piece = board.piece_at(square)
    if piece is None or piece.piece_type in (chess.PAWN, chess.KING) or piece.color != board.turn or not unsafe(board, square):
        return False
    for move in board.legal_moves:
        if move.from_square != square:
            continue
        gained = board.piece_at(move.to_square)
        after = board.copy(stack=False)
        after.push(move)
        if see(after, move.to_square, after.turn) <= (value(gained) if gained else 0):
            return False
    return True


def label(board, move):
    return f"{board.fullmove_number}{'.' if board.turn else '…'} {board.san(move)}"


def walk(board, pv):
    """Positions along the line and the pieces each side captured."""
    positions, taken = [board.copy(stack=False)], {chess.WHITE: [], chess.BLACK: []}
    for uci in pv:
        cursor = positions[-1]
        move = chess.Move.from_uci(uci)
        if move not in cursor.legal_moves:
            break
        captured = chess.Piece(chess.PAWN, not cursor.turn) if cursor.is_en_passant(move) else cursor.piece_at(move.to_square)
        if captured:
            taken[cursor.turn].append(captured)
        following = cursor.copy(stack=False)
        following.push(move)
        positions.append(following)
    return positions, taken


def settled(positions, pv, me):
    """Material for `me` at the end of the line, counting the recapture still pending on the last move's square."""
    end, balance = positions[-1], material(positions[-1], me)
    if len(positions) < 2:
        return balance
    square = chess.Move.from_uci(pv[len(positions) - 2]).to_square
    gain = see(end, square, end.turn)
    return balance + gain if end.turn == me else balance - gain


def sans(positions, pv, start, count=6):
    return ' '.join(label(positions[i], chess.Move.from_uci(pv[i])) if i == start or positions[i].turn else positions[i].san(chess.Move.from_uci(pv[i]))
                    for i in range(start, min(len(positions) - 1, start + count)))


def beyond(board, origin, through):
    """First piece behind `through` on the line from `origin`."""
    df = (chess.square_file(through) > chess.square_file(origin)) - (chess.square_file(through) < chess.square_file(origin))
    dr = (chess.square_rank(through) > chess.square_rank(origin)) - (chess.square_rank(through) < chess.square_rank(origin))
    f, r = chess.square_file(through) + df, chess.square_rank(through) + dr
    while 0 <= f < 8 and 0 <= r < 8:
        square = chess.square(f, r)
        if board.piece_at(square):
            return square
        f, r = f + df, r + dr
    return None


def fork(answer, landing, hitter, me):
    targets = [s for s in answer.attacks(landing) if (p := answer.piece_at(s)) and p.color == me
               and (p.piece_type == chess.KING or value(p) > value(hitter) or unsafe(answer, s))]
    return sorted(targets, key=lambda s: -value(answer.piece_at(s))) if len(targets) >= 2 else []


def refutation(board, played, positions, pv, lost):
    """Motif of the opponent's reply that wins material, with the squares to look at."""
    me, move = board.turn, chess.Move.from_uci(played)
    after = positions[1]
    moved = after.piece_at(move.to_square)
    grabbed = board.piece_at(move.to_square) or (chess.Piece(chess.PAWN, not me) if board.is_en_passant(move) else None)
    san = board.san(move)
    lead = f"{san} prende {one(grabbed)}, ma" if grabbed else f"Dopo {san}"
    if len(positions) < 3:
        return None
    reply, answer = chess.Move.from_uci(pv[1]), positions[2]
    reply_text, hitter = label(after, reply), after.piece_at(reply.from_square)
    target = after.piece_at(reply.to_square)
    landing = reply.to_square
    forked = fork(answer, landing, hitter, me)
    if forked:
        listed = [f"{the(answer.piece_at(s))} in {chess.square_name(s)}" for s in forked]
        kind = 'forchetta' if hitter.piece_type in (chess.KNIGHT, chess.PAWN) else 'attacco doppio'
        took = f"prende {the(target)} e " if target else ''
        return 'fork', (f"{lead} {reply_text} {took}attacca insieme {', '.join(listed[:-1])} e {listed[-1]} ({kind}): "
                        f"non puoi salvare tutto."), [chess.square_name(landing)] + [chess.square_name(s) for s in forked]
    if target and target.color == me and see(after, reply.to_square, not me) > 0:
        square = chess.square_name(reply.to_square)
        if reply.to_square == move.to_square:
            if not after.is_attacked_by(me, reply.to_square):
                return 'hanging', f"{lead} {the(moved)} in {square} non è {agree(moved, 'difes')}: {reply_text} {pronoun(moved)} cattura.", [square]
            how = f"con {one(hitter)}, che vale meno" if value(hitter) < value(moved) else 'e la difesa non basta'
            return 'hanging', f"{lead} {the(moved)} in {square} è {agree(moved, 'attaccat')} più di quanto sia {agree(moved, 'difes')}: {reply_text} {pronoun(moved)} cattura {how}.", [square]
        defenders = board.attackers(me, reply.to_square)
        if move.from_square in defenders and move.to_square not in after.attackers(me, reply.to_square):
            opener = f"{san} prende {one(grabbed)}, ma" if grabbed else san
            return 'undefended', (f"{opener} sposta {the(board.piece_at(move.from_square))} da {chess.square_name(move.from_square)} "
                                  f"e lascia senza difesa {the(target)} in {square}: {reply_text} {pronoun(target)} cattura."), [chess.square_name(move.from_square), square]
        waiting = board.copy(stack=False)
        if not waiting.is_check():
            waiting.push(chess.Move.null())
            if reply in waiting.legal_moves and see(waiting, reply.to_square, not me) > 0:
                return 'ignored_threat', (f"{the(target).capitalize()} in {square} era già {agree(target, 'attaccat')} e {san} non {pronoun(target)} "
                                          f"protegge: {reply_text} {pronoun(target)} cattura."), [square]
        if move.from_square in chess.SquareSet(chess.between(reply.from_square, reply.to_square)):
            return 'opened_line', f"{lead} libera la linea {chess.square_name(reply.from_square)}–{square}: {reply_text} cattura {the(target)}.", [chess.square_name(reply.from_square), square]
        return 'hanging', f"{lead} {the(target)} in {square} non è {agree(target, 'difes')} abbastanza: {reply_text} {pronoun(target)} cattura.", [square]
    if answer.is_check() and hitter.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        king = answer.king(me)
        behind = beyond(answer, landing, king)
        prize = answer.piece_at(behind) if behind is not None else None
        if prize and prize.color == me and value(prize) >= 3 and king in answer.attacks(landing):
            return 'skewer', (f"{lead} {reply_text} dà scacco al re e, quando il re si sposta, {the(hitter)} cattura "
                              f"{the(prize)} in {chess.square_name(behind)} (infilata)."), [chess.square_name(landing), chess.square_name(behind)]
    # Pieces the line actually loses come first; a short line may stop before the loss.
    lost_kinds = {p.piece_type for p in lost}
    candidates = sorted((s for s in chess.SquareSet(answer.occupied_co[me]) if value(answer.piece_at(s)) >= 3 and answer.piece_at(s).piece_type != chess.KING),
                        key=lambda s: (answer.piece_at(s).piece_type not in lost_kinds, s != move.to_square, -value(answer.piece_at(s))))
    for square in candidates:
        if trapped(answer, square):
            piece = answer.piece_at(square)
            return 'trapped', (f"{lead} {the(piece)} in {chess.square_name(square)} resta {agree(piece, 'intrappolat')}: dopo {reply_text} è "
                               f"{agree(piece, 'attaccat')} e non ha case sicure."), [chess.square_name(square), chess.square_name(landing)]
    for square in candidates:
        piece = answer.piece_at(square)
        for slider in answer.attackers(not me, square):
            if slider != landing and reply.from_square in chess.SquareSet(chess.between(slider, square)) and unsafe(answer, square):
                return 'discovered', (f"{lead} {reply_text} sposta {the(hitter)} e scopre l’attacco di {the(answer.piece_at(slider))} "
                                      f"su {the(piece)} in {chess.square_name(square)} (attacco di scoperta)."), [chess.square_name(slider), chess.square_name(square)]
        if answer.is_pinned(me, square) and unsafe(answer, square):
            return 'pin', (f"{lead} {reply_text} inchioda {the(piece)} in {chess.square_name(square)} al re: non può spostarsi "
                           f"e viene {agree(piece, 'pers')}."), [chess.square_name(square)]
    # Slow traps: the piece is cut off first and attacked only by the opponent's next move.
    if len(positions) >= 5:
        later, closing = positions[4], chess.Move.from_uci(pv[3])
        for square in chess.SquareSet(later.occupied_co[me]):
            piece = later.piece_at(square)
            if piece.piece_type in lost_kinds and trapped(later, square):
                return 'trapped', (f"{lead} {the(piece)} in {chess.square_name(square)} resta {agree(piece, 'intrappolat')}: dopo {reply_text} "
                                   f"e {label(positions[3], closing)} non ha più case sicure."), [chess.square_name(square)]
    return None


def positional(board, played, best_move, opponent):
    me = board.turn
    after, alternative = board.copy(stack=False), board.copy(stack=False)
    after.push_uci(played)
    alternative.push_uci(best_move)
    mine, mine_alt = features(after, me), features(alternative, me)
    theirs, theirs_alt = features(after, not me), features(alternative, not me)
    reasons = []
    if board.queens and len(mine['kingShield']) < len(mine_alt['kingShield']):
        reasons.append('indebolisce i pedoni davanti al tuo re')
    if new := [s for s in theirs['passed'] if s not in theirs_alt['passed']]:
        reasons.append(f"concede {articled('al', opponent)} un pedone passato in {', '.join(new)}")
    if new := [s for s in mine['isolated'] if s not in mine_alt['isolated']]:
        reasons.append(f"ti lascia un pedone isolato in {', '.join(new)}")
    if mine['doubled'] > mine_alt['doubled']:
        reasons.append('ti lascia pedoni doppiati')
    if mine_alt['pieceReach'] - mine['pieceReach'] >= 4:
        reasons.append('lascia i tuoi pezzi meno attivi')
    if theirs['pieceReach'] - theirs_alt['pieceReach'] >= 4:
        reasons.append(f"dà più spazio ai pezzi {articled('del', opponent)}")
    return reasons[:2]


def explain(fen, played, best, actual):
    board = chess.Board(fen)
    pv, best_pv = actual.get('pv') or [], best.get('pv') or []
    if not pv or not best_pv or pv[0] != played or best_pv[0] == played:
        return None
    mated, missed = (actual.get('mate') or 0) < 0 <= (best.get('mate') or 0), (best.get('mate') or 0) > 0 and not (actual.get('mate') or 0) > 0
    mate_change = mated or missed
    if not mate_change and best['cp'] - actual['cp'] < MIN_LOSS:
        return None
    me, opponent = board.turn, 'il Nero' if board.turn else 'il Bianco'
    positions, taken = walk(board, pv)
    best_positions, best_taken = walk(board, best_pv)
    if len(positions) < 2 or len(best_positions) < 2:
        return None
    san, best_san = board.san(chess.Move.from_uci(played)), board.san(chess.Move.from_uci(best_pv[0]))
    # A line cut in the middle of an exchange would otherwise look like a loss of material.
    net = settled(positions, pv, me) - material(board, me)
    best_net = settled(best_positions, best_pv, me) - material(board, me)
    line_text, best_text = sans(positions, pv, 1), sans(best_positions, best_pv, 0)
    focus, motif, text = [], None, None
    if mated:
        motif, text = 'mate', f"Dopo {san} {opponent} ha un matto in {abs(actual['mate'])}: {line_text}."
        end = positions[-1]
        if end.is_checkmate() and chess.square_rank(end.king(me)) == (0 if me else 7) and all(
                end.piece_at(s) and end.piece_at(s).color == me for s in end.attacks(end.king(me))
                if chess.square_rank(s) != chess.square_rank(end.king(me))):
            text += ' Il tuo re è chiuso sulla traversa dai suoi stessi pezzi.'
    elif missed:
        motif, text = 'missed_mate', f"Avevi un matto in {best['mate']}: {best_text}. {san} lo lascia sfuggire."
    # A motif needs the line to lose material, unless the line stops right after the reply.
    elif (net - best_net <= -2 or len(positions) <= 3 and best['cp'] - actual['cp'] >= 150) and (
            found := refutation(board, played, positions, pv, taken[not me])):
        motif, text, focus = found
    elif net - best_net <= -2 and net < 0:
        if any(chess.Move.from_uci(pv[i]).promotion for i in range(1, len(positions) - 1) if positions[i].turn != me):
            motif, text = 'promotion', f"Dopo {san} il pedone {articled('del', opponent)} arriva a promozione: {line_text}."
        else:
            won = f", in cambio di {pieces_text(taken[me])}" if taken[me] else ''
            motif, text = 'material', f"Dopo {san} la risposta più forte {articled('del', opponent)} ({line_text}) ti costa {pieces_text(taken[not me])}{won}."
    else:
        # Checks that trade or win pieces are an exchange, not an attack on the king.
        checks = [i for i in range(1, len(positions) - 1) if positions[i].turn != me and positions[i + 1].is_check()
                  and not ((p := positions[i].piece_at(chess.Move.from_uci(pv[i]).to_square)) and value(p) >= 3)]
        if len(checks) >= 2:
            motif, text = 'king', f"Dopo {san} il tuo re resta esposto: {opponent} prende l’iniziativa con una serie di scacchi ({line_text})."
        elif reasons := positional(board, played, best_pv[0], opponent):
            motif, text = 'positional', f"Non perdi materiale subito, ma rispetto a {best_san} la tua mossa {' e '.join(reasons)}: è uno svantaggio che pesa più avanti."
        else:
            motif, text = 'unclear', (f"Nelle prossime mosse non perdi materiale e non c’è una tattica evidente: la differenza con {best_san} "
                                      f"riguarda la posizione o sta oltre la variante mostrata. Confronta le due varianti.")
    better = None
    if motif != 'missed_mate':
        if best_net >= 2 and best_taken[me]:
            better = f"Con {best_san} vincevi {pieces_text(best_taken[me])}: {best_text}."
        else:
            better = f"Stockfish preferisce {best_san}: {best_text}."
    return {'motif': motif, 'title': TITLES[motif], 'text': text, 'better': better, 'focus': focus,
            'fen': fen, 'line': pv[:len(positions) - 1], 'bestLine': best_pv[:len(best_positions) - 1]}
