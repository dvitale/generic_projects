# Blunder prevention

## Riferimento osservato

Il 30 settembre 2026 è stata esaminata la pagina pubblica [Blunder Puzzles / Blunderbash di Chess Madra](https://chessmadra.com/blunder-puzzles) e la sua presentazione nella homepage. Il principio dichiarato è evitare il blunder senza dover trovare la mossa migliore. La pagina mostra una scacchiera, un rating, la rinuncia e impostazioni di pausa/riproduzione. Non è stato verificato l’algoritmo privato di valutazione; le soglie descritte sotto sono scelte di SparringMate, non parametri attribuiti a Chess Madra. Non sono state inviate partite personali a quel sito.

## Selezione personale

Si considerano tutte le decisioni del giocatore nelle analisi salvate, non soltanto i tre momenti critici dei Puzzle. Colore, FEN, storia e mossa giocata devono corrispondere alla partita. Sono escluse le mosse obbligate e le posizioni già perse. Le analisi esistenti vengono indicizzate all’avvio; le nuove analisi aggiornano il catalogo. Non si analizzano automaticamente partite non ancora revisionate.

Una candidata deve avere una scelta con valutazione almeno −100 centesimi di pedone dal punto di vista del giocatore, mentre la mossa originale deve scendere a −200 o peggio con perdita di almeno 200 centesimi, oppure consentire un matto forzato contro il giocatore. Una vittoria trasformata in pareggio non appartiene a questa modalità: il pareggio è per definizione una scelta non perdente.

Prima della prima sessione si ricontrollano la migliore e la mossa originale a 300.000 nodi per ricerca. Entro 50 centesimi dalla soglia di accettazione si ripete a 1.200.000 nodi. Un candidato non confermato viene escluso. La posizione e la sua storia sono conservate come evidenza; se la partita viene annullata dopo un’analisi, il collegamento passa alla copia della linea originale.

## Abbagli e lacune

Dal 29 ottobre 2026 (`REACH_VERSION` 1) un blunder entra nel catalogo solo se è un **abbaglio**: un errore grave che il giocatore, di norma, saprebbe evitare, e che riconosce subito appena gli si indica il punto. Quando l'errore nasce invece da una lacuna di competenza o di calcolo, appartiene ai Puzzle. La condizione di Stockfish descritta sopra resta necessaria, ma non basta più. Per ogni candidato, `assess_reach` in `backend/prevention.py` usa Maia sul server ([docs/maia-server.md](maia-server.md)) e la variante salvata dall'analisi:

| Esito (`reach_status`) | Regola | Nel catalogo |
|---|---|---|
| `typical`: errore tipico del livello | Maia, al livello della partita (entrambi i lati), gioca la mossa sbagliata almeno il 25% delle volte (`TYPICAL_PROBABILITY`) | no |
| `lapse`: abbaglio | Altrimenti, se la confutazione è elementare (matto in 1–2, oppure almeno 2 pedoni netti persi entro 4 semimosse dopo l'errore, cambi compresi) o se Maia, per l'avversario allo stesso livello, trova la prima mossa della confutazione almeno il 20% delle volte (`OBVIOUS_REPLY`) | sì |
| `complex`: confutazione da calcolare | Nessuno dei casi precedenti | no |
| nessun esito | La variante dopo l'errore manca, oppure Maia sul server non è disponibile | sì, come prima |

Il livello è l'Elo della partita: il livello di Maia scelto in Gioca, oppure quello di riferimento delle partite importate (1500 se manca). È un'approssimazione: indica contro chi stavi giocando, non la tua forza misurata. Le soglie sono convenzioni di allenamento, da rivedere con i dati.

Le nuove analisi valutano subito le posizioni. Quelle già indicizzate, o valutate con una versione precedente della regola, sono valutate dopo l'avvio sul thread delle analisi (`backfill_reach`): l'avvio resta rapido. Esito e indizi (`blunderProbability`, `reply`, `replyProbability`, `elementary`, `level`) sono salvati nella colonna `reach`. Le posizioni escluse non vengono cancellate e i loro tentativi restano. `GET /api/prevention` restituisce in `reach` il numero di posizioni per esito, che il riquadro **Solo abbagli, non lacune** mostra. Le posizioni ancora da valutare restano incluse.

## Valutazione della risposta

Ogni mossa legale proposta viene valutata, anche se non compare nelle prime tre. È accettata se mantiene almeno −1,00 dalla parte del giocatore, oppure se perde meno di 1,00 rispetto alla migliore (`TOLERANCE_CP`, dal 27 ottobre 2026: da −0,80 una mossa a −1,20 non è un blunder), e non permette un matto forzato contro di lui. Quando la migliore è un matto a favore vale solo la soglia di −1,00. Entro 50 centesimi da una delle due soglie la verifica si ripete a 1.200.000 nodi. Sopra −1,00 non si impone una perdita massima rispetto alla migliore: una mossa da +6 a 0 viene accettata, così come una vittoria che rinuncia al matto più corto. Questa è la differenza rispetto ai Puzzle, che richiedono una perdita massima di 50 centesimi dalla migliore.

La soglia è una convenzione pratica di allenamento, non una dimostrazione matematica di patta o vittoria. Stockfish lavora con un budget limitato; il criterio e i punteggi sono espliciti nell’interfaccia. Le valutazioni di matto vengono trattate come esiti, non sottratte come enormi perdite numeriche.

## Esperienza e progressi

La mossa sbagliata originale e gli esempi di soluzione restano nascosti fino al completamento o alla richiesta di aiuto. Ogni tentativo viene eseguito subito sulla scacchiera; dopo un errore resta visibile per 1,1 secondi dalla risposta del motore e poi torna indietro in 650 ms. Durante verifica e ritorno non si possono inviare altre mosse. La preferenza di accessibilità per ridurre il movimento disattiva le animazioni, mantenendo la pausa per osservare la scelta. Alla fine compaiono il confronto con il vecchio errore, il collegamento alla partita, **Gioca da qui** (nuova partita contro Maia dalla posizione prima dell’errore, disponibile solo a esercizio chiuso), **↺ Riprova da capo** e la prossima posizione. Riprova da capo riporta la scacchiera alla posizione prima dell’errore e accetta nuove mosse come pratica libera: `POST /api/prevention/{id}/practice` le verifica con la stessa soglia ma non le salva, e risponde 409 finché la sessione è aperta. È possibile saltare e ripetere come pratica.

Posizioni, sessioni e tentativi hanno tabelle SQLite dedicate e non alterano i risultati dei Puzzle. Solo il primo tentativo senza aiuti di una posizione nuova o in scadenza contribuisce ai successi indipendenti. I retry, gli esempi mostrati e le ripetizioni anticipate non aumentano la serie; ripassi previsti dopo 1, 3, 7, 14 e 30 giorni. I tentativi usano versioni per respingere richieste duplicate o fuori sequenza. Fra le posizioni in scadenza l'ordine ruota: prima quelle mai mostrate, poi quelle aperte meno di recente (`last_shown_at`, aggiornato a ogni apertura anche senza risposta).

Verifiche: test backend con Stockfish reale per entrambi i colori, alternativa diversa dalla prima scelta, errore originale, retry, aiuto, ripasso, ricostruzione e annullamento; test browser del percorso completo e dell’esito visibile.

## Storico degli errori e spiegazioni

Sia Blunder prevention sia Puzzle conservano ogni nuovo tentativo sbagliato in `training_mistakes`, nella stessa transazione del tentativo: FEN, colore, mossa, valutazione e variante effettiva, migliore alternativa, motore e data. Il pannello della posizione mostra anche gli errori delle sessioni precedenti. La perdita è la differenza dalla migliore alternativa in pedoni, non il punteggio assoluto; le valutazioni restano sempre dalla parte del giocatore. Quando una delle valutazioni indica matto, si mostrano i due esiti senza convertire i valori convenzionali del motore in perdite di pedoni. I tentativi precedenti a questa versione rimangono nelle tabelle originarie ma non hanno queste evidenze dettagliate, che non vengono inventate retroattivamente.

“Spiega motivo” invoca DeepSeek esclusivamente su richiesta. Il server recupera l’evidenza salvata del tentativo e ricostruisce le due varianti, aggiungendo pezzi mossi, catture e scacchi verificati. Non invia nomi dei giocatori, la partita intera o dati forniti dal browser. La risposta descrive il motivo, il seguito e un controllo pratico da fare prima di muovere. La spiegazione può svelare una scelta migliore; essendo disponibile solo dopo un errore, non può trasformare quel primo tentativo fallito in un successo indipendente.

Le risposte valide sono conservate in `mistake_explanations`, con cache legata a evidenza, modello e versione del prompt: richieste ripetute non richiamano il provider. Errori di rete, credito o formato non eliminano il tentativo e permettono di riprovare. La chiave rimane sul server e il tutor condivide il limite di concorrenza con quello delle partite. L’LLM spiega le evidenze, ma non decide se accettare la mossa e può produrre imprecisioni.
