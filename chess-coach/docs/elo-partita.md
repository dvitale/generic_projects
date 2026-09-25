# Punteggio della partita: metodo dei Drill Maia

Alla conclusione della partita il calcolo parte automaticamente e compare in **Gioca**. Riaprendo una partita conclusa in **Rivedi** si avvia il calcolo se manca un risultato aggiornato. Per le partite in corso c’è **Stima Elo della partita**. Gioca e Rivedi condividono il calcolo; uscire da queste sezioni lo interrompe. Il risultato viene salvato in SQLite.

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

La versione `maia3-drill-match-v2` sostituisce quel metodo. Un risultato v1 non viene presentato come aggiornato: sulle partite concluse si ricalcola automaticamente; sulle altre rimane il pulsante. Il server verifica anche la versione del metodo, impedendo a un vecchio frontend di salvare un risultato con parametri diversi.

## Salvataggio e precisione futura

I punteggi per livello, il numero di mosse, i parametri e il metodo restano nel database. Nuove mosse o annullamenti invalidano il risultato. I controlli di versione impediscono di associare una risposta al ramo sbagliato. Le copie delle partite già analizzate conservano esercizi e tentativi precedenti.

Per ridurre realmente l’incertezza servono più partite o decisioni informative, calibrazione su giocatori con rating noto e verifica su partite separate. Il punteggio delle mosse e la qualità Stockfish sono segnali diversi: non si converte arbitrariamente la perdita in centipawn in Elo e non si chiede a un LLM di inventare il numero.
