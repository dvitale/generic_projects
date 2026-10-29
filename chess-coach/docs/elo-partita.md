# Somiglianza con Maia: confronto facoltativo

Dal 9 ottobre 2026 il riepilogo principale è **Rivedi → Decisioni**: qualità Stockfish, errori e vantaggi conservati. La **Somiglianza con Maia** è in un pannello secondario chiuso e parte soltanto premendo **Confronta con i profili Maia**. Non vengono assegnate etichette come principiante o intermedio. Il confronto non serve a ordinare le prestazioni: un profilo 1300 può accompagnare una partita peggiore di un profilo 600. I risultati precedenti restano conservati in SQLite e si leggono aprendo il pannello.

Il numero è il **profilo Maia più compatibile con le mosse**, sulla scala di riferimento Lichess. Non è un rating FIDE o Chess.com, né una misura calibrata della forza individuale. Mostrare un valore puntuale non dimostra di aver ridotto l’incertezza reale.

## Verifica delle fonti, 25 settembre 2026

Repository CSSLab/maia-platform-frontend, commit `a6e52f5c811ee18863cb2f0e81f2433a5b9905de` (anche HEAD al momento dell’ispezione).

- [Livelli](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/constants/common.ts#L1-L9): 21 livelli da 600 a 2600, a passi di 100.
- [Calcolo](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/hooks/useOpeningDrillController/useOpeningDrillController.ts#L835-L889): media dei logaritmi delle probabilità delle mosse, con probabilità minima 0,001; vince il livello con il valore maggiore.
- [Inferenza](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/hooks/useOpeningDrillController/useOpeningDrillController.ts#L945-L951): entrambi gli input Elo, giocatore e avversario, ricevono il livello candidato. Non viene tenuto fisso il rating del bot affrontato.
- [Presentazione](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/components/Openings/MaiaRatingInsights.tsx#L63-L99): il sito mostra il vincitore e una fascia intorno a esso.

La fascia usa `standardDeviation: 150`, assegnato come **costante**. Non viene stimata dalle probabilità o dal numero di mosse. Il nome della variabile non ne fa una deviazione standard empirica. La percentuale del grafico upstream è una trasformazione lineare limitata tra 0 e 1 del log-score medio, non una distribuzione di probabilità sui rating.

Questa implementazione è nei **Drill**, non in una testa del modello Maia3 che predice direttamente il rating del giocatore. Il [paper Chessformer, §4.2](https://arxiv.org/html/2605.19091v1#S4.SS2) descrive la previsione delle mosse condizionata sui rating forniti come input. Anche i modelli Python rilasciati mantengono questa distinzione; il modello browser esistente rimane quello utilizzato dall’app.

## Formula e implementazione locale v2

Per ogni candidato `r` e ogni decisione `i`:

`p_i(r) = Maia(mossa_i | posizione_prima_della_mossa_i, EloSelf=r, EloOppo=r)`

`L(r) = (1/N) × somma_i log(max(p_i(r), 0.001))`

Il punteggio è `argmax_r L(r)`. Somma e media producono lo stesso vincitore, perché tutti i livelli usano le stesse posizioni. La trasformazione grafica upstream non cambia l’ordinamento e non serve a selezionare il vincitore.

Nel dettaglio delle tre migliori corrispondenze mostriamo `exp(L(r))`, la media geometrica delle probabilità delle mosse dopo il limite minimo: **non** la probabilità di possedere quel rating. Valori vicini indicano che il vincitore è sensibile a piccole variazioni delle mosse.

Differenze intenzionali rispetto al sito:

- Almeno 10 decisioni non obbligate per evitare punteggi su pochissime mosse.
- Mosse obbligate escluse: aggiungere fattori con probabilità 1 non cambierebbe il vincitore. Nei Drill si esclude anche la sequenza preparatoria.
- Tutte le decisioni ammesse, senza il precedente limite di 40. L’app limita già la partita a 600 semimosse; il calcolo resta interrompibile.
- Una parità numerica tra massimi non viene risolta scegliendo arbitrariamente il livello più basso.
- Nessuna fascia ±150: non sarebbe un’incertezza ricavata dai dati. Al bordo si segnala il limite della griglia, senza estrapolare oltre 600–2600.
- Il criterio dei Drill viene applicato anche alle partite libere e importate. L’estensione non costituisce una validazione scientifica del rating della partita.

Non sono stati scaricati nuovi pesi o addestrati modelli: viene usato il modello ONNX browser già installato, localmente e senza DeepSeek.

## Perché prima appariva 600–2600

Il metodo locale v1 usava 11 livelli a passi di 200, avversario fisso, limite di probabilità `1e-12` e includeva nella fascia ogni livello entro 2 unità di log-score dal migliore. Su una curva piatta la fascia copriva tutta la griglia e il numero centrale era nascosto. La soglia 2 era una scelta del prototipo, **non una regola documentata di Maia**. Presentarla come valutazione utile della partita era inadeguato.

La versione `maia3-drill-match-v2` sostituisce quel metodo. Un risultato v1 non viene presentato come aggiornato: si può ricalcolare soltanto su richiesta tramite il pulsante. Il server verifica anche la versione del metodo, impedendo a un vecchio frontend di salvare un risultato con parametri diversi.

## Salvataggio e precisione futura

I punteggi per livello, il numero di mosse, i parametri e il metodo restano nel database. Nuove mosse o annullamenti invalidano il risultato. I controlli di versione impediscono di associare una risposta al ramo sbagliato. Le copie delle partite già analizzate conservano esercizi e tentativi precedenti.

Per ridurre realmente l’incertezza servono più partite o decisioni informative, calibrazione su giocatori con rating noto e verifica su partite separate. Il punteggio delle mosse e la qualità Stockfish sono segnali diversi: non si converte arbitrariamente la perdita in centipawn in Elo e non si chiede a un LLM di inventare il numero.

## Prestazione stimata dalla precisione

Da ottobre 2026 Rivedi mostra, sotto la **Precisione**, una **Prestazione stimata** per ciascun lato, e **Progressi** la stessa stima sulle ultime 10 partite analizzate contro Maia. È un metodo diverso dalla somiglianza con Maia: usa la qualità delle mosse secondo Stockfish, non quanto sono tipiche di un livello.

**Calibrazione.** `scripts/calibrate_accuracy_rating.py` legge in streaming l’archivio Lichess `lichess_db_standard_rated_2025-09.pgn.zst` (CC0, non viene salvato) e tiene le partite rated rapid e classical (durata stimata base + 40 × incremento ≥ 480 s), dalla posizione iniziale, terminate normalmente o per tempo, con l’analisi di Lichess su ogni mossa e almeno 10 mosse per lato: 150.000 partite, 299.553 giocatori. La precisione usa la stessa formula di `web/src/accuracy.ts`, con +0,15 per la posizione iniziale come Lichess. Il risultato è `web/src/data/accuracy-rating.json`: per ogni livello da 600 a 2600, a passi di 100 (i rating fuori vanno al primo o all’ultimo), la probabilità di ciascuna precisione, smussata di 3 punti di precisione e di un livello.

**Stima.** Tutti i livelli partono ugualmente possibili. Ogni partita moltiplica le probabilità dei livelli secondo la sua precisione; il risultato è la mediana, con l’intervallo fra il 10° e il 90° percentile, arrotondati a 50. Non si parte dalla distribuzione dei giocatori Lichess, concentrata intorno a 1500: quella tirerebbe ogni stima verso il centro e assegnerebbe a un principiante con una partita al 55% circa 1300.

La relazione è debole: la precisione mediana va dal 67% dei 600 all’88% dei 2400, mentre fra le partite di uno stesso giocatore ne varia facilmente 10–15 punti.

**Verifica.** Un giocatore su cinque, scelto in base al nome, resta fuori dalla calibrazione e serve a controllare gli intervalli. Le partite dello stesso giocatore non sono indipendenti (lo stile pesa), quindi le probabilità combinate vengono attenuate con l’esponente che porta al 80% la copertura su 10 partite: oggi 0,7.

| Partite | Giocatori di verifica | Rating vero nell’intervallo | Larghezza mediana |
|---|---|---|---|
| 1 | 26.033 | 97% | ~1590 punti |
| 5 | 2.773 | 90% | ~1230 punti |
| 10 | 533 | 81% | ~990 punti |

Con una sola partita l’intervallo è largo e prudente; anche con 10 resta circa ±500 punti. Il numero serve a seguire la tendenza, non a certificare un livello.

**Limiti.**
- Scala Lichess rapid e classical, non FIDE né chess.com.
- La nostra analisi usa Stockfish a 12.000 nodi per posizione, quella di Lichess è più profonda: le precisioni non sono perfettamente confrontabili.
- Le partite contro Maia sono senza orologio, quelle di calibrazione a tempo.
- In Progressi contano solo le partite contro Maia dalla posizione iniziale, analizzate per intero, con almeno 10 mosse proprie; sono esclusi Drill, PGN importati (possono essere partite di altri) e le mosse giocate dopo un suggerimento. In Rivedi servono almeno 10 mosse non obbligate.

Per rifare la calibrazione su un altro mese: `.venv/bin/python scripts/calibrate_accuracy_rating.py --month AAAA-MM [--games 150000]` (circa 8 minuti ogni 100.000 partite), poi `make build`.
