# SparringMate

La revisione mostra fino a tre scelte per Stockfish (MultiPV, con valutazione e variante) e Maia (ordinate per probabilità al livello selezionato). Se le mosse legali sono meno di tre, mostra solo quelle disponibili. Le analisi salvate precedentemente si aggiornano con **Aggiorna revisione completa**.

Le frecce con spostamento da cavallo seguono un percorso a L: prima due case, poi una a 90°, anche nell’anteprima e con orientamento Nero.

Applicazione personale locale: Maia3 come sparring partner, Stockfish come verificatore e allenamento dalle proprie partite. Interfaccia italiana, React/TypeScript, FastAPI e SQLite. Installata in WSL Debian in `/opt/generic_projects/chess-coach`.

## Avvio sul PC

```bash
cd /opt/generic_projects/chess-coach
./start.sh
```

Aprire http://localhost:8033 nel browser Windows. Per fermare il server in primo piano: Ctrl+C. Per un'altra porta: `PORT=8001 ./start.sh`.

## Funzioni

Verifica del motore e differenze rispetto al gioco sul sito ufficiale: [audit Maia del 29 settembre 2026](docs/verifica-maia.md). Include controlli ripetibili del modello browser ai livelli 600, 1500 e 2600; la corrispondenza del modello non implica parità con il servizio server di Play.

- **Mosse durante la partita:** elenco aggiornato delle mosse di Bianco e Nero. Clicca una mossa o usa i comandi di navigazione per rivedere la posizione; dopo aver selezionato una mossa funzionano anche ←, →, Home ed End. **Torna alla posizione corrente** ripristina il gioco. Le posizioni precedenti sono consultabili senza modificare la partita; una risposta di Maia aggiorna l’elenco senza spostare la posizione osservata.

- **Frecce di analisi:** Stockfish in blu, Maia in rosso, mossa giocata in bianco. Le frecce mostrano solo la prima scelta di ciascun motore; le scelte coincidenti sono affiancate. Sotto la scacchiera puoi nascondere una fonte. La tabella conserva anche la seconda e la terza scelta. Le frecce seguono la posizione prima della mossa e il livello Maia scelto; le annotazioni manuali restano arancioni.

- **Esito Puzzle:** un messaggio sopra la scacchiera distingue mossa corretta, tentativo da migliorare e soluzione mostrata. Una risposta corretta resta visibile sulla scacchiera. **Prossimo puzzle** apre un esercizio non ancora concluso nella sessione; alla fine è possibile ricominciare. Le soluzioni mostrate non contano come risposte corrette.

- **Frecce sulla scacchiera:** tieni premuto il tasto destro e trascina tra due case. Puoi aggiungere più frecce; ripetere lo stesso gesto elimina quella freccia. Un clic destro senza trascinare evidenzia una casa con un cerchio. Clic sinistro, Esc o cambio di posizione cancellano le annotazioni. Disponibili anche durante la revisione e nei Drill; non modificano la partita.

- **Spazio di lavoro:** scacchiera e pannello affiancati sui monitor grandi; in Rivedi le schede Decisioni, Mosse, Andamento, Tutor e Approfondimenti conservano la posizione e i calcoli durante il cambio scheda. Archivio nella voce Partite. Drill separa catalogo e sessione. Su mobile il layout torna a una colonna.

- **Annulla ultima mossa:** in Gioca e Drill ritorna alla tua ultima decisione, togliendo anche la risposta di Maia o interrompendola se ancora in preparazione. Nei Drill conserva la sequenza iniziale. Disponibile anche dopo la conclusione; PGN importati e copie archiviate restano in sola revisione.
- **Decisioni, non Elo:** il riepilogo principale mostra scelte senza perdite rilevanti, errori e vantaggi conservati. La somiglianza con Maia è facoltativa, in un pannello secondario chiuso: il profilo più probabile non indica quanto bene hai giocato, non assegna titoli e non parte automaticamente. Il calcolo rimane compatibile con i dati salvati. Metodo matematico in [docs/elo-partita.md](docs/elo-partita.md).
- **Ritmo Maia:** risposte con attesa variabile di circa 1,2–3,2 secondi, comprendente il tempo di inferenza, e breve animazione del pezzo. Il caricamento iniziale del modello può richiedere più tempo. Lo stesso ritmo vale nei Drill; il cambio di sezione annulla le risposte ancora in preparazione.
- **Gioca:** bianco o nero contro il vero modello Maia3 del sito, livello selezionabile, mosse legali e salvataggio automatico. Puoi trascinare i pezzi con mouse o touch oppure usare due clic; le promozioni mantengono la scelta del pezzo.
- **Rivedi:** revisione passo passo di entrambe le parti. Ogni posizione confronta mossa giocata, scelta Stockfish e mossa più probabile di Maia al livello selezionato, con probabilità e varianti. Le frecce e il selettore delle mosse mostrano la scacchiera prima della decisione. Restano importazione/esportazione PGN e momenti critici personali. Per vecchie analisi, ricalcolare per includere tutte le mosse.
- **Drill:** aperture, finale di torre e posizioni delle proprie partite; 3–12 decisioni contro Maia e revisione dedicata.
- **Puzzle:** decisioni critiche personali, alternative verificate, tentativi, indizi, soluzione e ripassi distanziati.
- **Tutor DeepSeek:** spiegazioni e piano dopo la revisione Stockfish, con riflessione del giocatore e collegamenti agli esercizi. Vedi `docs/tutor-deepseek.md`.
- **Progressi:** evidenze iniziali e piano base di 25 minuti. Aiuti e ripetizioni immediate non gonfiano i successi indipendenti.

I Puzzle personali compaiono dopo aver analizzato una partita contenente errori rilevanti. Per cominciare senza partite, utilizzare il catalogo Drill o importare un proprio PGN.

## Motori e dati

Maia3 non è una CNN: è la generazione Transformer descritta nel paper Chessformer. Si usa l'artefatto ONNX pronto del sito ufficiale, eseguito nel browser tramite JavaScript/WASM, senza addestramento. Il primo caricamento trasferisce circa 46 MB dal server locale e li conserva nella cache del browser. Stockfish 19 gira in WSL.

Le partite restano in `data/coach.sqlite3`; gli asset sono in `web/public/maia3`, `web/public/ort` e `vendor/stockfish`. Maia e Stockfish funzionano localmente. Il tutor DeepSeek opzionale richiede una chiave e invia i dati selezionati al servizio solo quando richiesto. Salvare la cartella `data` a server fermo per il backup; a server acceso usare il backup SQLite.

## Installazione da un nuovo clone

Prerequisiti Debian: Python 3.10+, supporto venv, Node 20.19+ e npm, rete per scaricare dipendenze e asset.

```bash
./scripts/install.sh
./start.sh
```

L'installer scarica solo file con hash attesi nel manifest. Se il sito modifica il modello, il controllo fallisce: non adottare automaticamente un modello diverso senza verificare compatibilità e provenienza. Il binario Stockfish fornito dall'installer è per Linux x86-64. Per altre architetture fornire `STOCKFISH_PATH`.

## Sviluppo e verifiche

```bash
./scripts/dev.sh
.venv/bin/python -m pytest tests -q
cd web
npm run build
npm test
```

Le prove del browser usano Chromium di sistema (`/usr/bin/chromium`), il vero Maia e dati temporanei su una porta separata. Le prove Python verificano Stockfish, legalità, versioni, esercizi e registrazione dei progressi.

Le richieste Maia di gioco, revisione ed Elo condividono una coda: non vengono eseguite contemporaneamente sulla stessa sessione ONNX. Gli output vengono verificati anche nella dimensione e nella valutazione; in caso di numeri non validi il worker viene ricreato e la stessa inferenza ritentata una volta. Un errore persistente interrompe il calcolo senza salvare punteggi parziali. Le prove di recupero usano anche un worker simulato per iniettare errori numerici riproducibili.

## Dove estendere il progetto

| Percorso | Responsabilità |
|---|---|
| `web/src/engine/maia.ts` | Tokenizzazione, maschera legale, inferenza browser |
| `backend/engine.py` | Confine Stockfish e prospettiva delle valutazioni |
| `backend/main.py` | API, persistenza, analisi, Puzzle e piano iniziale |
| `backend/drills.py` | Catalogo e preparazione delle posizioni Drill |
| `web/src/Drills.tsx` | Sessione di pratica contro Maia |
| `docs/drill-puzzle-personalizzati.md` | Analisi del sito e progetto evolutivo del tutor |

Questo è un prototipo funzionante ed estendibile. Non include ancora un modello calibrato delle competenze, un generatore tattico a più mosse o verifiche di apprendimento su posizioni nuove. L'analisi individua fino a tre momenti critici per partita con budget limitato; i temi sono indicativi. Il piano attuale è semplice e trasparente, non un tutor autonomo completo.

Progetto indipendente, senza affiliazione a Maia Chess. Attribuzioni e licenze in `THIRD_PARTY.md`; sorgenti applicativi GPL-3.0, artefatti esterni con le rispettive condizioni.

Per fermare l'istanza avviata in background da questa sessione: `python3 scripts/stop.py`. L'arresto attende le eventuali analisi in corso.



## Aspetto della scacchiera

L'installazione sul PC usa il tema **Green** e i pezzi **Neo** richiesti, scaricati dai server pubblici di Chess.com e conservati localmente. Le immagini sono escluse da Git e conservano i diritti originali. Su un nuovo clone puoi installarle con `python3 scripts/install_chesscom_theme.py`, poi ricompilare il frontend. In assenza delle immagini sono disponibili una scacchiera CSS e pezzi Unicode di riserva.

## Configurazione del tutor

`python3 scripts/configure_deepseek.py` configura la chiave con input nascosto. La credenziale rimane in `.secrets/deepseek.json`, esclusa da Git. La spiegazione viene salvata nel database con l'analisi a cui si riferisce. Dettagli sui dati inviati, sul modello e sui limiti in `docs/tutor-deepseek.md`.


## Esportare PGN e tempi

**Esporta PGN** è disponibile in Gioca, Rivedi e nelle sessioni Drill, anche a partita in corso. **Includi tempi** aggiunge i dati registrati a ciascuna mossa. I file riportano risultato, nomi, data e posizione iniziale; l'importazione conserva anche i nomi originali, il risultato dichiarato e il controllo del tempo.

Le partite libere non hanno un conto alla rovescia: si registra il tempo attivo per mossa con l'annotazione PGN `[%emt h:mm:ss]`. Il conteggio si sospende lasciando il pannello di gioco o nascondendo la scheda; il tempo di Maia comprende inferenza e attesa visibile. Il turno in corso viene recuperato dopo un normale ricaricamento nella stessa scheda. I dati delle mosse confermate restano nel database, anche dopo il riavvio. Un turno il cui inizio non è stato osservato rimane senza tempo; le mosse delle vecchie partite non ricevono valori inventati.

Nei PGN importati si conservano sia `[%clk ...]` (tempo residuo sull'orologio) sia `[%emt ...]` (durata della mossa), quando presenti. Disattivare Includi tempi esclude queste annotazioni dal download senza cancellare i dati. Annullare una mossa rimuove anche i relativi tempi; un'eventuale copia di revisione conserva la linea originale con i suoi tempi.


## Blunder prevention

La sezione **Blunder prevention** propone le posizioni delle tue partite analizzate prima di un errore che rende la posizione perdente. Accetta qualsiasi mossa valutata da Stockfish almeno −1,00 dal tuo punto di vista, senza matto forzato contro di te: non serve trovare la prima scelta. Le posizioni già perse e le mosse obbligate vengono escluse, e ogni candidato è ricontrollato prima del primo tentativo.

I tentativi e i ripassi sono separati dai Puzzle. Dopo una scelta corretta o la richiesta di un esempio, puoi confrontare il vecchio errore, aprire la partita originale e passare alla posizione successiva. I retry e gli aiuti non gonfiano i successi al primo tentativo. Le analisi già presenti alimentano il catalogo automaticamente; per altre partite usa **Analizza partita**. [Criteri e limiti](docs/blunder-prevention.md).

In **Puzzle** e **Blunder prevention**, la mossa tentata viene mostrata subito e, se sbagliata, annullata lentamente dopo una breve pausa. Il pannello **Tentativi sbagliati** conserva gli errori della posizione con valutazione e perdita rispetto alla migliore alternativa. **Spiega motivo** richiede a DeepSeek una spiegazione basata sulle varianti Stockfish salvate; le spiegazioni vengono conservate per evitare richieste ripetute. Serve la configurazione DeepSeek già usata dal tutor. Le nuove evidenze vengono registrate da questa versione; i tentativi storici senza valutazioni dettagliate rimangono conservati nei dati originali.


## Tattica, posizione e strategia

La revisione e le spiegazioni DeepSeek distinguono conseguenze tattiche, cambiamenti posizionali e piano strategico. Gli indicatori confrontano la posizione prima della mossa, dopo la scelta e dopo l'alternativa Stockfish: sono fatti descrittivi, non una scomposizione del punteggio NNUE. Il saldo materiale è separato dalla valutazione e i casi non spiegabili vengono segnalati come causa da approfondire. La guida è disponibile anche in Puzzle, Blunder prevention e Drill; i Progressi distinguono i tipi di evidenza senza diagnosticare carenze da pochi esempi. [Review, confronto con altri sistemi e limiti](docs/strategy-tactics-review.md).

## Andamento della valutazione

In **Rivedi → Andamento** il grafico mostra la valutazione Stockfish iniziale e dopo ogni mossa dei due colori. Sopra lo zero è favorito il Bianco, sotto il Nero, indipendentemente dall'orientamento della scacchiera. Il punteggio è espresso in unità di pedone: non è Elo né un conteggio del materiale. I matti sono indicati separatamente con rombi ai bordi e non ricevono un valore numerico.

Cliccando un punto, usando le frecce della tastiera sul grafico o scegliendo una posizione dall'elenco si aggiorna la scacchiera. **Tutte le valutazioni** apre anche la tabella. Il grafico riutilizza le valutazioni salvate e si aggiorna al termine dell'analisi. Per vecchie analisi incomplete, **Completa il grafico** ricalcola tutte le mosse; i segmenti mancanti non vengono interpolati. Nei Drill la curva parte dalla prima posizione analizzata, dopo la preparazione iniziale. La scala verticale si adatta alla partita e le valutazioni rimangono stime alla profondità di analisi raggiunta.

## Analizzare una posizione con Lichess

Il tasto **Analizza con Lichess**, sotto la scacchiera in Gioca, Rivedi, Blunder prevention, Puzzle e Drill, apre una finestra su lichess.org con la posizione attualmente mostrata e lo stesso orientamento. Funziona anche quando si rivede una mossa precedente, la soluzione di un esercizio o il vecchio errore in Blunder prevention. Trasferisce la posizione FEN completa, non l'intera cronologia della partita; le mosse provate su Lichess non modificano la partita locale. Il browser può aprire una scheda invece di una finestra; se blocca la popup è disponibile un collegamento alternativo per la posizione richiesta.

## Analisi automatica e origine degli esercizi

Quando una mossa conclude una partita locale (matto o patta), Stockfish avvia automaticamente l'analisi dopo aver salvato la mossa. La schermata finale resta aperta e mostra l'avanzamento; l'analisi prosegue sul server anche chiudendo il browser. Riaprendo la partita si recupera il lavoro in corso, senza avviarne una seconda copia. Al termine, le posizioni adatte alimentano Puzzle e Blunder prevention. L'analisi può essere ricalcolata manualmente; le partite importate o interrotte restano analizzabili con il comando dedicato.

In ogni Puzzle e posizione di Blunder prevention, il riquadro **Dalla tua partita** mostra titolo, data di archiviazione e numero/colore della mossa. **Rivedi questa mossa nella partita** apre la revisione esattamente prima della decisione originale. Il riferimento è disponibile anche per gli esercizi già salvati e segue l'eventuale copia conservata quando si annullano mosse di una partita analizzata.

## Abbandonare una partita

Durante il gioco, **Abbandona partita** è disponibile sotto la scacchiera, anche mentre Maia pensa. Dopo la conferma viene registrata una sconfitta per il tuo colore, viene fermata la risposta di Maia e si avvia l'analisi automatica delle mosse giocate. Risultato e motivo restano salvati al ricaricamento e nel PGN esportato. La partita abbandonata resta consultabile, ma non accetta altre mosse o annullamenti. Se abbandoni prima della prima mossa, viene salvato il risultato senza avviare un'analisi vuota.

### Puzzle: ripasso e confronto dopo la soluzione

La lista e il contatore dei puzzle da ripassare diminuiscono solo dopo un primo tentativo corretto senza indizi. Errori, soluzioni mostrate e successi dopo tentativi sbagliati mantengono il puzzle in scadenza. Una nuova sessione permette di riprovarlo; dopo un errore occorre attendere quattro ore per una nuova verifica indipendente. La pratica anticipata non promuove il ripasso e non cancella lo storico. Prossimo puzzle evita quelli già conclusi nella sessione di navigazione.

Dopo una risposta corretta, la propria mossa rimane visibile brevemente, poi viene mostrata la posizione iniziale: freccia bianca per la mossa della partita originale, rossa per la prima scelta di Maia al livello della partita. Il pulsante consente di tornare alla propria soluzione. Il confronto non anticipa suggerimenti durante il tentativo.

## Importare Maia e pianificare gli allenamenti

**Importa PGN** accetta testo con più partite o più file, fino a 20 partite e 1 MB per operazione. Riconosce il colore umano contro Maia, conserva intestazioni e tempi presenti, distingue i duplicati tramite ID Maia e può avviare automaticamente l’analisi delle nuove partite. Gli errori vengono mostrati per singola partita. Non è una sincronizzazione dell’account: lo storico Maia provato senza autenticazione restituisce 403; usa Export → PGN sul sito e incolla il testo qui.

**Allenamento** propone prima i richiami scaduti, poi un numero limitato di posizioni nuove. Imposta minuti, limite delle nuove posizioni e giorni della settimana. La durata è stimata a due minuti per posizione. Puzzle e Blunder prevention usano intervalli di 4 ore, 1, 3, 7, 14, 30, 90 e 180 giorni; errori o aiuti azzerano la progressione. Un puzzle sbagliato resta in scadenza, ma il richiamo indipendente successivo attende quattro ore. Riaprirlo prima è pratica e non aumenta la padronanza. La lista giornaliera evita di proporre due volte la stessa posizione come puzzle e prevenzione.

Impostazioni, verifiche e scadenze sono salvate in SQLite; il calendario usa Europe/Rome e non invia notifiche esterne. Le prove anticipate non fanno avanzare l’obiettivo giornaliero. Il calendario misura il richiamo di posizioni già viste, non ancora il trasferimento delle abilità alle nuove partite.

La [guida pratica](docs/training-guide.html) si apre da **Allenamento → Apri la guida** in una popup con indice navigabile, impaginazione per telefono e stampa/PDF. È scaricabile in HTML per la lettura offline; se il browser blocca la popup, compare un collegamento per aprirla in una nuova scheda. Spiega importazione e calendario e contiene tutorial adattati al lavoro contro Maia per Aimchess, MoveTrainer e Noctie. Documentazione ufficiale verificata il 6 ottobre 2026; le aree personali dei servizi esterni non sono state provate con l’account dell’utente. Il sorgente resta in `docs/training-guide.md`; per rigenerare l’HTML usa `pwsh -File scripts/build_training_guide.ps1` (PowerShell 7, nessuna dipendenza aggiuntiva).

Verifiche dedicate: `tests/test_batch_import.py`, `tests/test_training_schedule.py` e `web/tests/training-plan.spec.ts`, oltre alle regressioni di Puzzle, Blunder prevention, analisi automatica e collegamenti Lichess.

## Qualità delle decisioni e valutazione delle minacce

**Rivedi → Decisioni** e il riepilogo dopo la partita mostrano solo le decisioni non obbligate del giocatore, esclusa l'apertura preimpostata dei drill. Soglie operative: perdita <80 centesimi senza peggioramento rilevante; 80–179 imprecisione; ≥180 errore rilevante. Vantaggio conservato significa valutazione ≥150 prima e dopo la propria mossa, non conversione dell'intera partita. I matti mantengono il segno separato dalla valutazione numerica. Questi indicatori dipendono dal budget Stockfish e non sono Elo.

**Progressi** separa partite e drill e confronta fino a 10 sessioni recenti con le 10 precedenti, con denominatori espliciti. È un confronto descrittivo: avversari e difficoltà non sono controllati. Le analisi obsolete e le copie conservate dopo annullamento non vengono conteggiate.

**Allenamento → Valuta la posizione** campiona tutte le categorie di valutazione, non solo errori o posizioni recuperabili. Si registra giudizio, sicurezza, minaccia temuta, impressione di partita già persa e familiarità prima di mostrare valutazione e variante. Le risposte sono persistenti e non modificabili; la stessa posizione non viene proposta nuovamente come nuova. Gli esercizi non vengono presi da sparring ancora in corso. Le posizioni ricordate sono escluse dagli indicatori di primo incontro. “Allarme di sconfitta non confermato” significa impressione di posizione persa con valutazione Stockfish ≥−100 centesimi; non è una diagnosi psicologica né una garanzia di facilità. Le fasce ±1 e ±3 sono convenzioni didattiche. Queste verifiche sono separate dai ripassi puzzle e non avanzano il calendario automaticamente.

API locali: GET `/api/games/{id}/decision-quality`, GET `/api/learning-progress`, POST `/api/position-judgments/next`, POST `/api/position-judgments/{id}`. Evidenza Stockfish congelata al momento della proposta; tabella SQLite `position_judgments`. Il tutor rispetta il ragionamento riferito dal giocatore e non deduce emozioni o omissioni dalle sole mosse.
