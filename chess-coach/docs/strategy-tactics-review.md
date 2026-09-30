# Review: tattica, posizione e strategia in SparringMate

Review del 30 settembre 2026: codice dell’app e documentazione pubblica dei prodotti citati. Le descrizioni commerciali non dimostrano come funzionino i loro classificatori privati; non sono state inviate partite personali a servizi di confronto.

## Risultato principale

**Gravità e natura dell’errore sono due assi distinti.** Un blunder è un peggioramento rilevante della valutazione; non significa necessariamente lasciare un pezzo in presa. La tattica riguarda conseguenze concrete e calcolo delle risposte. La valutazione posizionale descrive le caratteristiche della scacchiera. La strategia sceglie obiettivi e piani in base a quelle caratteristiche. Le tre dimensioni interagiscono: un cambio forzato può produrre una debolezza duratura, e un cattivo piano può consentire una combinazione.

Stockfish chiarisce che le etichette come “blunder” vengono aggiunte dalle interfacce, mentre il motore produce valutazioni e varianti. La valutazione NNUE moderna non è un semplice conteggio del materiale: un calo di 2,00 non implica la cattura di due pedoni e non può essere scomposto onestamente in “1,20 di sicurezza del re + 0,80 di attività”. [Stockfish FAQ](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html).

| Dimensione | Domanda utile | Esempi | Verifica necessaria |
|---|---|---|---|
| Tattica | Qual è la risposta concreta che non ho previsto? | Scacco, cattura, difesa, minaccia, promozione, opportunità mancata | Variante legale, ricatture e saldo finale, non una singola cattura isolata |
| Posizione | Che cosa cambia nei pezzi e nella struttura? | Pedoni isolati, colonne, centro, portata dei pezzi, coppia degli alfieri, difese del re | Confronto delle posizioni e valutazione della compensazione |
| Strategia | Quale obiettivo devo perseguire adesso? | Attivare un pezzo, preparare una rottura, bloccare un passato, cambiare un difensore | Obiettivo concreto compatibile con le risposte tattiche avversarie |
| Causa incerta | Il materiale resta uguale: basta la linea per spiegare il calo? | Tattica oltre l’orizzonte mostrato, vantaggio dinamico, finale difficile | Dichiarare il limite; approfondire il confronto, senza inventare una causa |

Le definizioni sono coerenti con le presentazioni didattiche di [tattica](https://www.chess.com/terms/chess-tactics) e [strategia](https://www.chess.com/terms/chess-strategy) di Chess.com. “Strategico” non equivale a “lento” o “senza catture”, e “tattico” non equivale esclusivamente ad attacco.

## Confronto con sistemi analoghi

| Sistema | Elemento documentato | Scelta per SparringMate |
|---|---|---|
| Chess.com Game Review | Spiegazioni del coach, ripetizione della scelta e visualizzazione di idee, pezzi persi, forchette o matto | Collegare la spiegazione alla conseguenza osservabile, senza limitarsi al punteggio |
| Chess.com Skills | Categorie separate per fondamentali, aperture, tattica, strategia e finali | Distinguere area di allenamento e fase della partita; evitare che “apertura” sostituisca la causa |
| DecodeChess | Confronto prima/dopo, problemi e idee, funzioni dei pezzi e piani | Fornire all’LLM fatti prima/dopo e un’alternativa, chiedendo quale obiettivo ne consegue |
| Lichess | Gravità e accuratezza basate sul cambiamento delle possibilità di vittoria; limiti del confronto in centipawn | Tenere separati gravità, natura dell’errore e difficoltà pratica; non dedurre l’Elo o una carenza da pochi errori |

Fonti: [Game Review](https://support.chess.com/en/articles/8584089-how-does-game-review-work), [Skills](https://support.chess.com/en/articles/16243840-what-are-skills-on-chess-com), [DecodeChess](https://decodechess.com/features/), [Lichess Accuracy](https://lichess.org/page/accuracy). Questa review non attribuisce agli altri prodotti algoritmi interni non pubblicati.

## Problemi trovati nel progetto

1. La classificazione didattica delle analisi era quasi sempre “Calcolo e mosse candidate”, salvo i casi di matto. Non distingueva ragionamento posizionale e calcolo.
2. Le spiegazioni degli errori ricevevano FEN e varianti con catture/scacchi, ma non un confronto strutturato delle caratteristiche della posizione. Il prompt menzionava il peggioramento posizionale senza fornire sufficiente evidenza specifica.
3. “Perdita 4 pedoni” poteva essere letta come perdita materiale anziché variazione di valutazione.
4. Il tutor restituiva un commento generale e un piano, senza richiedere di separare conseguenze tattiche, cambiamenti posizionali e obiettivi strategici.
5. I conteggi dei temi non esplicitavano la distinzione fra gravità dell’errore, indizi sulla causa e diagnosi delle competenze.

## Modifiche introdotte

Il nuovo modulo `backend/insights.py` ricostruisce legalmente entrambe le linee già analizzate. Calcola il saldo materiale convenzionale (1/3/3/5/9), distinto dalla valutazione Stockfish, e confronta prima, dopo la mossa giocata e dopo la migliore alternativa. I due confronti immediati hanno sempre la stessa distanza di una semimossa.

Gli indicatori descrittivi coprono pedoni isolati, doppiati e passati, coppia degli alfieri, torri su colonne senza pedoni, case centrali attaccate, portata geometrica dei pezzi e, quando ci sono donne, pedoni davanti al re e case circostanti attaccate. Sono calcolati per entrambi i colori. Non rappresentano una valutazione causale: una coppia di alfieri non è sempre preferibile e una struttura danneggiata può avere compensazione. Portata e attacchi geometrici non garantiscono mosse legali o case sicure.

L’interfaccia distingue **Evidenza tattica**, **Indizi posizionali**, **Tattica e posizione**, **Causa da approfondire** e **Confronto didattico**. Sono orientamenti euristici, non verdetti del motore. Per la categoria mista occorrono evidenza tattica e un cambiamento strutturale della mossa rispetto alla posizione iniziale e all’alternativa: piccoli cambiamenti geometrici di attività non bastano. Il materiale alla fine di una variante è descritto come fatto della linea, non come perdita inevitabile: le linee possono avere lunghezze diverse o interrompersi prima di una compensazione.

La distinzione appare nella revisione passo passo, nelle spiegazioni degli errori di Puzzle e Blunder prevention, nel tutor della partita e nel piano di allenamento. Puzzle e Drill includono una guida compatta; i Progressi mostrano conteggi distinti delle decisioni da rivedere, deduplicando stessa FEN e mossa. Un conteggio elevato non viene presentato come diagnosi di una carenza stabile.

DeepSeek deve rispondere con quattro campi separati: **tattica**, **posizione**, **piano strategico** e **certezze/limiti**. Ogni attività proposta indica se allena calcolo tattico, strategia o entrambi. Il prompt vieta di attribuire quote del punteggio ai fattori, inventare varianti, confondere materiale e valutazione o dichiarare posizionale un errore per esclusione. Le risposte prive dei nuovi campi non vengono salvate. Le versioni dei prompt cambiano per non riusare vecchie spiegazioni come se rispettassero il nuovo contratto.

Le analisi archiviate ricevono gli indicatori in lettura, senza cancellare o ricalcolare automaticamente partite e tentativi. Le vecchie risposte del tutor restano consultabili con un avviso sul formato precedente; “Aggiorna il confronto” richiede il nuovo formato. Le nuove analisi salvano anche gli indicatori. Nessuna chiamata LLM avviene automaticamente.

## Esempio didattico

Se una scelta passa da +0,30 a −1,40 senza perdere materiale nella linea mostrata, una spiegazione utile non è “hai perso 1,70 pedoni” né “è certamente un errore strategico”. Deve indicare: il materiale nella linea resta uguale; un fatto osservabile è cambiato (per esempio una colonna disponibile o un difensore spostato); quel fatto **potrebbe** facilitare un piano avversario, se la variante lo sostiene; l’alternativa conserva una risorsa concreta. Se il collegamento non emerge, la causa rimane da approfondire. Questo esempio illustra il formato, non attribuisce una diagnosi a una partita dell’utente.

## Limiti e sviluppi successivi

- Non cambia la soglia di accettazione dei Puzzle o di Blunder prevention. Un confronto basato sulle probabilità di esito, come in Lichess, richiederebbe una scelta separata di prodotto e una calibrazione.
- Non è un classificatore completo di motivi tattici: inchiodature, sovraccarichi, deviazioni, zugzwang e fortezze non vengono “riconosciuti” soltanto dalla FEN o dall’assenza di catture.
- Non viene lanciata automaticamente una ricerca più profonda: la causalità può restare irrisolta con il budget e la linea disponibili. È preferibile un limite esplicito a una spiegazione plausibile ma inventata.
- Un’evoluzione utile è un approfondimento su richiesta con ricerca più lunga, confronto della stabilità del punteggio e riproduzione delle due linee sulla scacchiera. Per i progressi servono più esempi indipendenti e verifica su posizioni nuove, non semplici conteggi.

## Verifiche

Test dedicati distinguono un cambiamento posizionale senza perdita di materiale, una causa non determinabile da una linea corta, una cattura seguita da ricattura, matto e saldo materiale da entrambi i colori. Sono verificati anche arricchimento delle analisi storiche senza riscrittura, evidenze inviate al tutor, rifiuto di risposte incomplete, sezioni separate nell’interfaccia e layout mobile. Le chiamate DeepSeek nei test sono simulate: il contratto dei dati viene verificato, la qualità linguistica del provider resta variabile.
