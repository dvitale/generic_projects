"""Observable chess facts, separate from engine scores and causal hypotheses."""
import chess

VERSION = 2
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
LABELS = {'tactical': 'Evidenza tattica', 'positional': 'Indizi posizionali',
          'mixed': 'Tattica e posizione', 'unclear': 'Causa da approfondire', 'neutral': 'Confronto didattico'}
LIMIT = ('La gravità dell’errore e la sua causa sono distinte. I punti Stockfish non sono pezzi persi. '
         'Questi indicatori descrivono la scacchiera, non scompongono il punteggio della rete neurale. '
         'Una variante breve senza perdite non esclude una tattica più lontana; i cambiamenti posizionali non provano da soli la causa.')


def material(board, color):
    return sum(value * (len(board.pieces(piece, color)) - len(board.pieces(piece, not color))) for piece, value in VALUES.items())


def features(board, color):
    pawns = board.pieces(chess.PAWN, color)
    enemy = board.pieces(chess.PAWN, not color)
    files = [chess.square_file(s) for s in pawns]
    isolated = [chess.square_name(s) for s in pawns if not any(abs(chess.square_file(s)-f)==1 for f in files)]
    passed = [chess.square_name(s) for s in pawns if not any(
        abs(chess.square_file(s)-chess.square_file(e))<=1 and
        (chess.square_rank(e)>chess.square_rank(s) if color else chess.square_rank(e)<chess.square_rank(s)) for e in enemy)]
    open_rooks = [chess.square_name(s) for s in board.pieces(chess.ROOK, color)
                  if not any(chess.square_file(p)==chess.square_file(s) for p in pawns | enemy)]
    king = board.king(color)
    ring = board.attacks(king) if king is not None else chess.SquareSet()
    shield = [chess.square_name(s) for s in pawns if king is not None and abs(chess.square_file(s)-chess.square_file(king))<=1
              and (chess.square_rank(s)-chess.square_rank(king) if color else chess.square_rank(king)-chess.square_rank(s)) in (1,2)]
    reach = sum(len(board.attacks(s) & ~chess.SquareSet(board.occupied_co[color]))
                for pt in (chess.KNIGHT,chess.BISHOP,chess.ROOK,chess.QUEEN) for s in board.pieces(pt,color))
    center = [chess.square_name(s) for s in (chess.D4,chess.E4,chess.D5,chess.E5) if board.is_attacked_by(color,s)]
    return {'isolated': isolated, 'doubled': sum(max(0,files.count(f)-1) for f in set(files)),
            'passed': passed, 'bishopPair': bool(board.pieces_mask(chess.BISHOP,color)&chess.BB_DARK_SQUARES) and bool(board.pieces_mask(chess.BISHOP,color)&chess.BB_LIGHT_SQUARES), 'openRooks': open_rooks,
            'kingShield': shield, 'kingRingAttacked': [chess.square_name(s) for s in ring if board.is_attacked_by(not color,s)],
            'pieceReach': reach, 'center': center}


def line(board, evaluation):
    cursor = board.copy(stack=False)
    steps = []
    for uci in evaluation.get('pv', [])[:16]:
        move = chess.Move.from_uci(uci)
        if move not in cursor.legal_moves:
            raise ValueError('La variante contiene una mossa non legale')
        captured = cursor.piece_at(move.to_square)
        steps.append({'san': cursor.san(move), 'side': 'w' if cursor.turn else 'b',
                      'captured': 'p' if cursor.is_en_passant(move) else captured.symbol() if captured else None,
                      'check': cursor.gives_check(move), 'promotion': chess.piece_symbol(move.promotion) if move.promotion else None})
        cursor.push(move)
        steps[-1]['materialBalance'] = material(cursor,board.turn)
    return {'steps': steps, 'finalFen': cursor.fen(), 'material': material(cursor,board.turn),
            'plies': len(steps), 'endsInCheck': cursor.is_check(), 'gameOver': cursor.is_game_over()}


def compare(fen, played, best, actual):
    board = chess.Board(fen)
    best_move = best.get('pv', [None])[0] if best.get('pv') else None
    if not best_move or not actual.get('pv') or actual['pv'][0] != played:
        return {'version': VERSION, 'kind': 'unclear', 'label': LABELS['unclear'], 'tacticalFacts': [],
                'positionalFacts': [], 'plans': [], 'note': 'Varianti salvate insufficienti: ricalcola l’analisi.'}
    paths = {name: line(board,value) for name,value in [('best',best),('actual',actual)]}
    after = board.copy();after.push_uci(played)
    alternative = board.copy();alternative.push_uci(best_move)
    facts, positional, plans = [], [], []
    structural_change = False
    if actual.get('mate') is not None and actual['mate'] <= 0 and (best.get('mate') is None or best['mate']>0):
        facts.append(f"Il motore segnala matto contro di te in {abs(actual['mate'])}; la migliore alternativa non ha questo esito nella ricerca disponibile.")
    if best.get('mate') is not None and best['mate']>0 and (actual.get('mate') is None or actual['mate']<=0):
        facts.append(f"La migliore alternativa ha un matto in {best['mate']}; la tua scelta non conserva il matto individuato dal motore.")
    if paths['actual']['steps'] and paths['best']['steps']:
        delta = paths['actual']['material']-paths['best']['material']
        # Use endpoint balance, not a temporary sacrifice before a recapture.
        if delta <= -1:
            facts.append(f"Al termine delle varianti mostrate il saldo materiale convenzionale è {paths['actual']['material']:+g} con la tua scelta e {paths['best']['material']:+g} con l’alternativa. Le linee hanno {paths['actual']['plies']} e {paths['best']['plies']} semimosse: non è una prova di perdita inevitabile né misura la compensazione.")
    comparisons=[]
    for color in (board.turn, not board.turn):
        owner = 'tuoi' if color==board.turn else 'avversari'
        before, chosen, better = features(board,color),features(after,color),features(alternative,color)
        comparisons.append({'side': 'w' if color else 'b', 'before': before, 'played': chosen, 'alternative': better})
        fields=[('isolated','Pedoni isolati','Struttura pedonale: valuta quali pedoni possono essere attaccati o difesi.'),
                ('doubled','Pedoni doppiati in eccesso','Struttura pedonale: confronta debolezze e colonne aperte ottenute in cambio.'),
                ('passed','Pedoni passati','Piano: considera blocco, sostegno e avanzata dei pedoni passati.'),
                ('bishopPair','Coppia degli alfieri','Cambi: valuta se la posizione aperta o chiusa favorisce i pezzi rimasti.'),
                ('openRooks','Torri su colonne senza pedoni','Attività: cerca una colonna utile e verifica le case di ingresso.'),
                ('center','Case centrali attaccate','Centro: confronta controllo, spinte e sviluppo prima di scegliere un piano.'),
                ('pieceReach','Portata geometrica dei pezzi','Attività: individua il pezzo meno attivo, controllando prima le minacce.')]
        if board.queens:
            fields += [('kingShield','Pedoni davanti al re','Sicurezza del re: verifica le linee aperte e le difese disponibili.'),
                       ('kingRingAttacked','Case adiacenti al re attaccate','Sicurezza del re: identifica accessi e difensori prima di avviare un attacco.')]
        def display(value):
            return ', '.join(value) if isinstance(value,list) and value else 'nessuno' if isinstance(value,list) else 'sì' if value is True else 'no' if value is False else str(value)
        for key, title, plan in fields:
            if chosen[key] == better[key]:continue
            # Small geometric changes are common, not a useful explanation of every move.
            if key=='pieceReach' and abs(chosen[key]-better[key])<4:continue
            if key in ('isolated','doubled','passed','bishopPair','kingShield','openRooks'):
                magnitude=lambda v:len(v) if isinstance(v,list) else int(v)
                if magnitude(chosen[key])!=magnitude(before[key]) and magnitude(chosen[key])!=magnitude(better[key]):
                    structural_change=True
            positional.append(f"{title} ({owner}): prima {display(before[key])}; dopo la tua mossa {display(chosen[key])}; dopo l’alternativa {display(better[key])}.")
            if plan not in plans:plans.append(plan)
    relevant = best_move != played and (best.get('mate')!=actual.get('mate') or best['cp']-actual['cp']>=50)
    # A geometric activity change accompanies almost every move. It does not by
    # itself turn a concrete tactical error into a mixed strategic diagnosis.
    kind = ('mixed' if facts and structural_change else 'tactical' if facts else 'positional' if positional else 'unclear') if relevant else 'neutral'
    return {'version': VERSION, 'kind': kind, 'label': LABELS[kind], 'tacticalFacts': facts,
            'positionalFacts': positional[:10], 'plans': plans[:3], 'note': LIMIT,
            'material': {'before': material(board,board.turn), 'immediate': material(after,board.turn),
                         'playedLine': paths['actual']['material'], 'bestLine': paths['best']['material']},
            'lines': paths, 'features': comparisons}


def enrich(analysis):
    if not analysis:return analysis
    by_ply={}
    for key in ('moves','decisions','critical'):
        for d in analysis.get(key,[]):
            if d['ply'] not in by_ply:
                saved=d.get('insight')
                by_ply[d['ply']]=saved if saved and saved.get('version')==VERSION else public(compare(d['fen'],d['played'],d['best'],d['actual']))
            d['insight']=by_ply[d['ply']]
    return analysis


def public(insight):
    return {k:v for k,v in insight.items() if k not in ('lines','features')}
