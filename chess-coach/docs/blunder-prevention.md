# Blunder prevention

## Riferimento osservato

Il 30 settembre 2026 è stata esaminata la pagina pubblica [Blunder Puzzles / Blunderbash di Chess Madra](https://chessmadra.com/blunder-puzzles) e la sua presentazione nella homepage. Il principio dichiarato è evitare il blunder senza dover trovare la mossa migliore. La pagina mostra una scacchiera, un rating, la rinuncia e impostazioni di pausa/riproduzione. Non è stato verificato l’algoritmo privato di valutazione; le soglie descritte sotto sono scelte di SparringMate, non parametri attribuiti a Chess Madra. Non sono state inviate partite personali a quel sito.

## Selezione personale

Si considerano tutte le decisioni del giocatore nelle analisi salvate, non soltanto i tre momenti critici dei Puzzle. Colore, FEN, storia e mossa giocata devono corrispondere alla partita. Sono escluse le mosse obbligate e le posizioni già perse. Le analisi esistenti vengono indicizzate all’avvio; le nuove analisi aggiornano il catalogo. Non si analizzano automaticamente partite non ancora revisionate.

Una candidata deve avere una scelta con valutazione almeno −100 centesimi di pedone dal punto di vista del giocatore, mentre la mossa originale deve scendere a −200 o peggio con perdita di almeno 200 centesimi, oppure consentire un matto forzato contro il giocatore. Una vittoria trasformata in pareggio non appartiene a questa modalità: il pareggio è per definizione una scelta non perdente.

Prima della prima sessione si ricontrollano la migliore e la mossa originale a 300.000 nodi per ricerca. Entro 50 centesimi dalla soglia di accettazione si ripete a 1.200.000 nodi. Un candidato non confermato viene escluso. La posizione e la sua storia sono conservate come evidenza; se la partita viene annullata dopo un’analisi, il collegamento passa alla copia della linea originale.

## Valutazione della risposta

Ogni mossa legale proposta viene valutata, anche se non compare nelle prime tre. È accettata se mantiene almeno −1,00 dalla parte del giocatore e non permette un matto forzato contro di lui. Non si impone una perdita massima rispetto alla migliore: una mossa da +6 a 0 viene accettata, così come una vittoria che rinuncia al matto più corto. Questa è la differenza rispetto ai Puzzle, che richiedono una perdita massima di 50 centesimi dalla migliore.

La soglia è una convenzione pratica di allenamento, non una dimostrazione matematica di patta o vittoria. Stockfish lavora con un budget limitato; il criterio e i punteggi sono espliciti nell’interfaccia. Le valutazioni di matto vengono trattate come esiti, non sottratte come enormi perdite numeriche.

## Esperienza e progressi

La mossa sbagliata originale e gli esempi di soluzione restano nascosti fino al completamento o alla richiesta di aiuto. Un tentativo sbagliato lascia la scacchiera iniziale disponibile per riprovare. Alla fine compaiono il confronto con il vecchio errore, il collegamento alla partita e la prossima posizione. È possibile saltare e ripetere come pratica.

Posizioni, sessioni e tentativi hanno tabelle SQLite dedicate e non alterano i risultati dei Puzzle. Solo il primo tentativo senza aiuti di una posizione nuova o in scadenza contribuisce ai successi indipendenti. I retry, gli esempi mostrati e le ripetizioni anticipate non aumentano la serie; ripassi previsti dopo 1, 3, 7, 14 e 30 giorni. I tentativi usano versioni per respingere richieste duplicate o fuori sequenza.

Verifiche: test backend con Stockfish reale per entrambi i colori, alternativa diversa dalla prima scelta, errore originale, retry, aiuto, ripasso, ricostruzione e annullamento; test browser del percorso completo e dell’esito visibile.
