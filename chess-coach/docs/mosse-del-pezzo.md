# Mosse del pezzo · Maia e Stockfish

In **Rivedi** un clic su un pezzo del giocatore che muove mette su ogni casa raggiungibile un'etichetta: la probabilità che Maia, al livello scelto nella revisione, giochi quella mossa, colorata secondo il giudizio di Stockfish. Si vede a colpo d'occhio la mossa sbagliata ma probabile, quella che al tuo livello tenta di più. L'idea viene dall'interfaccia di analisi di maiachess.com.

## Da dove vengono i numeri

- **Probabilità:** la previsione Maia che Rivedi chiede già per la freccia rossa (`POST /api/maia/predict`), con tutte le mosse legali. Le promozioni sulla stessa casa si sommano.
- **Giudizio:** `POST /api/review/piece-moves` con `fen` e `square` (`backend/piece_moves.py`). Stockfish valuta la posizione intera (80.000 nodi) e, in una sola ricerca MultiPV ristretta alle mosse del pezzo (`Evaluator.rank`, 20.000 nodi per mossa), ogni mossa del pezzo. Le linee che la ricerca non riporta vengono valutate una per una. Il calo si misura in punteggio atteso (curva logistica di Lichess) rispetto alla mossa migliore trovata:

| Colore | Giudizio | Regola |
|---|---|---|
| Verde | mossa migliore | è la prima scelta di Stockfish nella posizione |
| Grigio | buona | perde meno di 5 punti di punteggio atteso |
| Arancio | imprecisione | da 5 a meno di 10 punti |
| Rosso | errore | 10 punti o più |

Le soglie sono quelle del paper Queen (arXiv 2610.03695). Il bordo blu segna la prima scelta di Maia, se è una mossa del pezzo selezionato. Finché Stockfish non risponde l'etichetta è grigia e il titolo dice «in valutazione». I risultati restano in memoria nel server per le ultime 256 coppie posizione–casa.

## Uso

- Un secondo clic sullo stesso pezzo, un clic su un pezzo dell'altro colore, un cambio di posizione o l'interruttore **Mosse del pezzo** sotto la scacchiera tolgono le etichette.
- Il titolo della casa, letto anche dagli screen reader, dice mossa, probabilità e punti persi, per esempio «Qxe5+ · Maia 0,1% · Stockfish: errore (−48 punti di punteggio atteso)».
- Sotto i 600 px di larghezza restano solo i pallini colorati; i dettagli sono nel titolo.

## Limiti

- Stockfish ha un budget di nodi limitato: fra mosse quasi equivalenti il verde può cadere sull'una o sull'altra.
- Il giudizio è sul punteggio atteso: in una posizione già vinta o persa anche una mossa che cambia molto la valutazione in centipawn può restare «buona».

## Verifica

`tests/test_piece_moves.py` (backend) e `web/tests/piece-odds.spec.ts` (browser: donna in h5 prima di 3. Qxe5+, etichetta rossa su e5, deselezione e interruttore).
