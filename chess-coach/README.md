# SparringMate

La revisione mostra fino a tre scelte per Stockfish (MultiPV, con valutazione e variante) e Maia (ordinate per probabilità al livello selezionato). Se le mosse legali sono meno di tre, mostra solo quelle disponibili. Le analisi salvate precedentemente si aggiornano con **Aggiorna revisione completa**.

Le frecce con spostamento da cavallo seguono un percorso a L: prima due case, poi una a 90°, anche nell’anteprima e con orientamento Nero.

Applicazione personale locale: Maia3 come sparring partner, Stockfish come verificatore e allenamento dalle proprie partite. Interfaccia italiana, React/TypeScript, FastAPI e SQLite. Installata in WSL Debian in `/opt/generic_projects/chess-coach`.

## Avvio sul PC

```bash
cd /opt/generic_projects/chess-coach
make start
make status
```

Aprire http://localhost:8033 nel browser Windows. Il server resta in background dopo la chiusura del terminale, finché WSL rimane attivo.

| Comando | Funzione |
|---|---|
| `make start` | Avvia il server; se è già pronto non crea un secondo processo. |
| `make status` | Mostra stato, indirizzo, PID quando presente e percorso del log. |
| `make restart` | Attende l'arresto, poi riavvia. |
| `make stop` | Arresta conservando partite e allenamenti. Ripetibile a server già fermo. |
| `make logs` | Mostra le ultime 60 righe del log. |
| `make build` | Ricompila l'interfaccia dopo modifiche al frontend. |
| `make deploy` | Pubblica la versione corrente su sparringmate.u-s.it (`scripts/deploy.sh`). |
| `make` | Mostra l'aiuto. |

Per un'altra porta usa, per esempio, `make start PORT=8001` e lo stesso `PORT` per status/stop/restart. PID e log sono separati per porta in `.run/`; una seconda porta usa comunque gli stessi dati, salvo `CHESS_COACH_DATA` esplicito. All'avvio l'interfaccia viene compilata solo se manca `web/dist/index.html`: dopo modifiche esegui `make build`.

L'arresto invia SIGTERM solo a un processo Uvicorn verificato per questa cartella e porta. I comandi sono serializzati; un PID vecchio non autorizza ad arrestare altri processi. Una porta occupata da un servizio diverso impedisce l'avvio. Se un'analisi richiede oltre 60 secondi per terminare, l'arresto segnala l'attesa e il riavvio non parte: controlla `make status` oppure aumenta l'attesa con `make restart STOP_TIMEOUT=180`. Non viene usato SIGKILL.

Alternativa in primo piano: `./start.sh`, arresto con Ctrl+C; altra porta: `PORT=8001 ./start.sh`. `make start` non configura un avvio automatico al riavvio di Windows/WSL. Esegui i comandi con lo stesso utente che ha avviato il server. Serve GNU Make (`sudo apt install make` su Debian se manca).

## Accesso

Se `.env`, nella cartella del progetto, contiene `SPARRINGMATE_USER` e `SPARRINGMATE_PASSWORD`, l’app chiede di accedere: tutte le API tranne `/api/health` e `/api/auth/*` rispondono 401 senza una sessione valida.

```bash
SPARRINGMATE_USER=nome
SPARRINGMATE_PASSWORD=password
```

Le stesse variabili d’ambiente, se impostate, prevalgono su `.env`. Il file è escluso da Git; tienilo con permessi `600`, perché la password è salvata in chiaro. La sessione dura 30 giorni in un cookie firmato (`HttpOnly`, `SameSite=Strict`). La firma usa `data/session.key`, generato al primo avvio: cambiare la password o cancellare quel file chiude tutte le sessioni. Le modifiche a `.env` valgono dalla richiesta successiva, senza riavvio. Dopo cinque tentativi errati in cinque minuti lo stesso indirizzo deve attendere. **Esci** è in alto a destra. Senza le due variabili l’app resta aperta come prima.

Il login non sostituisce HTTPS: per un accesso da altri dispositivi esponi il servizio solo dietro un proxy TLS. Il cookie diventa `Secure` quando la richiesta arriva in HTTPS.

## Pubblicazione su sparringmate.u-s.it

L’istanza pubblica gira su Debian 11 in `/opt/sparringmate`, con l’utente di sistema `sparringmate`. Il servizio è `sparringmate.service` e Uvicorn ascolta solo su `127.0.0.1:8033`. nginx termina TLS con il certificato `*.u-s.it` e reindirizza HTTP su HTTPS. Unit e virtual host sono in `deploy/`; sul server il virtual host si trova in `/etc/nginx/sites-enabled/sparringmate.conf`.

- **Python:** il server ha Python 3.9, quindi il venv usa Python 3.12 da `/opt/uv-python`, creato con `uv venv` e installato con `uv pip install -r requirements.lock`.
- **Stockfish:** il binario `universal` richiede glibc 2.35, mentre Debian 11 ha la 2.31. Stockfish 19 è quindi compilato sul server dai sorgenti in `vendor/stockfish/src` con `make profile-build ARCH=x86-64-avx2`; servono anche `vendor/stockfish/scripts`. Il binario si trova in `/opt/sparringmate/engine/stockfish` e il servizio lo indica con `STOCKFISH_PATH`.
- **Cache del browser:** le pagine HTML hanno `Cache-Control: no-cache` e i file in `/assets/`, che hanno l’hash nel nome, una cache di un anno. Dopo un deploy il browser carica subito la nuova interfaccia, senza ricaricamento forzato.
- **Dati e credenziali:** i dati sono in `/opt/sparringmate/data`, l’unica cartella scrivibile dal servizio. Le credenziali sono in `/opt/sparringmate/.env`, con permessi `600`.
- **Proxy:** Uvicorn parte con `--proxy-headers`, così vede lo schema HTTPS (il cookie diventa `Secure`) e l’indirizzo reale di chi tenta l’accesso. Le scritture sono accettate da localhost o dallo stesso host che serve la pagina; ogni altra origine riceve 403. nginx limita anche `/api/auth/login` a 10 richieste al minuto per indirizzo.

Per aggiornare l’istanza: `make deploy`. Il comando compila l’interfaccia, sincronizza il codice, aggiorna le dipendenze e installa unit e virtual host se sono cambiati, verificando nginx prima di ricaricarlo; poi riavvia il servizio e controlla che risponda. Usa la chiave SSH oppure, se impostata, la variabile `SSHPASS`. Dettagli del server, ricompilazione di Stockfish e storia della configurazione: [`deploy/SERVER.md`](deploy/SERVER.md).

## Funzioni

- **Scelta delle mosse di Maia:** in Gioca, per la prossima partita contro Maia: **Completa** (sorteggio su tutte le mosse, la modalità storica: varia molto ma prima o poi esce una svista rara), **Bilanciata** (temperatura 0,7, top-p 0,95), **Solida** (temperatura 0,4, top-p 0,8), entrambe con tutte le mosse di Maia nelle prime 5 mosse (temperatura 1, top-p 1, come Mobile Maia) per non ripetere sempre la stessa apertura, e **Prima scelta** (sempre la mossa più probabile, più forte del livello indicato). La scelta resta fissata per la partita, è ricordata per la successiva e finisce nel PGN (`MoveSelection`). Il sorteggio lo fa il server, che salva il seme di ogni mossa. Dettagli in [docs/verifica-maia.md](docs/verifica-maia.md#come-sceglie-sparringmate).

Verifica del motore e differenze rispetto al gioco sul sito ufficiale: [audit Maia del 29 settembre 2026](docs/verifica-maia.md). Include controlli ripetibili del modello browser ai livelli 600, 1500 e 2600; la corrispondenza del modello non implica parità con il servizio server di Play.

- **Mosse durante la partita:** elenco aggiornato delle mosse di Bianco e Nero. Clicca una mossa o usa i comandi di navigazione per rivedere la posizione; dopo aver selezionato una mossa funzionano anche ←, →, Home ed End. **Torna alla posizione corrente** ripristina il gioco. Le posizioni precedenti sono consultabili senza modificare la partita; una risposta di Maia aggiorna l’elenco senza spostare la posizione osservata.

- **Frecce di analisi:** stile di maiachess.com (chessground di Lichess): linee semitrasparenti con estremità arrotondate e punta triangolare. Stockfish in blu, Maia in rosso, mossa giocata in bianco con bordo azzurro, disegnata sopra le altre. La freccia Maia viene calcolata su tutte le schede di Rivedi; se coincide con quella di Stockfish resta visibile come bordo rosso. Quando più frecce di colore diverso indicano la stessa mossa, quella in primo piano cambia a intervalli casuali fra 2 e 4 secondi, così ogni colore torna visibile per intero. Le frecce del cavallo seguono un percorso a L con angolo retto. Le frecce mostrano solo la prima scelta di ciascun motore; le scelte coincidenti sono affiancate. Sotto la scacchiera puoi nascondere una fonte. La tabella conserva anche la seconda e la terza scelta. Le frecce seguono la posizione prima della mossa e il livello Maia scelto; le annotazioni manuali sono verdi. Passando il mouse sulla casa di partenza o di arrivo di una freccia compare un breve titolo con il colore, la fonte e la mossa (per esempio «Freccia rossa · Maia: e4»): le frecce lasciano passare i clic alla scacchiera, quindi il titolo sta sulle case. Nel confronto finale dei Puzzle la tua soluzione ha una freccia verde e il rosso resta solo per Maia: se Maia avrebbe giocato la stessa mossa, la freccia rossa non compare e la legenda lo dice.

- **Esito Puzzle:** un messaggio sopra la scacchiera distingue mossa corretta, tentativo da migliorare e soluzione mostrata. Una risposta corretta resta visibile sulla scacchiera. **Prossimo puzzle** apre un esercizio non ancora concluso nella sessione; alla fine è possibile ricominciare. Le soluzioni mostrate non contano come risposte corrette.

- **Mosse del pezzo · Maia e Stockfish:** in Rivedi, un clic su un pezzo del giocatore che muove mostra su ogni casa raggiungibile la probabilità che Maia, al livello scelto, giochi quella mossa; il colore è il giudizio di Stockfish (verde la migliore della posizione, grigio buona, arancio imprecisione, rosso errore) e il bordo blu segna la prima scelta di Maia. Passando sulla casa compaiono mossa, probabilità e punti di punteggio atteso persi. Un secondo clic, un'altra posizione o l'interruttore **Mosse del pezzo** sotto la scacchiera la tolgono; sui telefoni restano solo i pallini colorati. [Dettagli](docs/mosse-del-pezzo.md).
- **Frecce sulla scacchiera:** tieni premuto il tasto destro e trascina tra due case. Puoi aggiungere più frecce; ripetere lo stesso gesto elimina quella freccia. Un clic destro senza trascinare evidenzia una casa con un cerchio. Clic sinistro, Esc o cambio di posizione cancellano le annotazioni. Disponibili anche durante la revisione e nei Drill; non modificano la partita.

- **Spazio di lavoro:** scacchiera e pannello affiancati sui monitor grandi; in Rivedi le schede Decisioni, Mosse, Andamento, Commento finale, Tutor e Approfondimenti conservano la posizione e i calcoli durante il cambio scheda. Archivio nella voce Partite. Drill separa catalogo e sessione. Sotto i 1100 px la barra laterale si riduce a icone; sotto i 680 px diventa una barra in basso con Allenamento, Gioca, Rivedi, Puzzle e **Altro** per le voci restanti, e il layout torna a una colonna. La scacchiera è dimensionata sull’altezza della finestra, così resta interamente visibile senza scorrere: il titolo della pagina sta nella barra superiore con **Importa PGN**, e nelle pagine con scacchiera il sottotitolo è omesso. L’esito di Puzzle e Blunder prevention compare in cima al pannello di destra. Dai 1500 px di larghezza la scacchiera cresce ancora e il pannello di destra si riduce fino a un minimo di circa 380 px.
- **Interfaccia:** barre giocatore con pezzi catturati, vantaggio di materiale e orologio che conta in avanti il tempo di riflessione (nessun conto alla rovescia). Una barra verticale bianco/nero a sinistra della scacchiera mostra la valutazione Stockfish della posizione visualizzata, come su chess.com: in Gioca (anche scorrendo le mosse) e in Rivedi usa una valutazione rapida (30.000 nodi, `GET /api/games/{id}/evaluation?ply=N`) quando non c’è un’analisi salvata; nei Puzzle compare solo dopo la conclusione, per non anticipare la soluzione. Si nasconde dall’ingranaggio in alto a destra (**Barra di valutazione**), ma solo in Gioca e nei Puzzle: in Rivedi resta sempre visibile. Il pulsante **⇅ Inverti** in alto (o il tasto F) capovolge la scacchiera in Gioca, Rivedi, Puzzle, Drill e Blunder prevention; la scelta vale per la sessione e non viene salvata. **Gioca da qui col Bianco/Nero** (sotto la scacchiera in Rivedi e mentre in Gioca scorri le mosse già giocate) avvia una nuova partita contro Maia dalla posizione mostrata, intitolata con il numero della partita di partenza («Dalla partita #35, mossa 20 del Nero»; dai Puzzle «Puzzle dalla partita #35, …»): giochi il colore in basso, quindi si sceglie il lato invertendo la scacchiera; il livello è quello della partita di origine (per le partite importate, quello selezionato in Gioca) e il titolo indica partita e mossa di partenza. Le posizioni già concluse non sono disponibili. Lo stesso pulsante compare in **Puzzle** (anche durante **↺ Riprova da capo**), nei **Problemi** e in **Blunder prevention**, ma solo dopo che l’esercizio è chiuso (risolto o soluzione mostrata), così non si possono provare mosse contro Maia prima del tentativo che conta per il ripasso: la partita parte dalla posizione iniziale dell’esercizio (nei Problemi, quella dopo la mossa dell’avversario), col colore che deve muovere, al livello selezionato in Gioca. Sempre a esercizio chiuso, **↺ Riprova da capo** (anche nei Problemi) riporta la scacchiera alla posizione iniziale per rigiocarla: Stockfish verifica le mosse con lo stesso criterio (nei Problemi la verifica avviene nel browser sulla soluzione nota), ma la pratica non viene registrata e non cambia ripassi né rating. In partita la barra è un aiuto: le mosse giocate con la barra visibile restano comunque nelle statistiche delle decisioni. Il riepilogo della partita, ispirato a Chesskit, affianca i due lati in un’unica tabella: **Precisione** (formula di Lichess: deriva dalla probabilità di vittoria stimata persa a ogni mossa, con più peso ai momenti tesi; non è un Elo, e le mosse giocate dopo un suggerimento sono escluse), **Prestazione stimata** (il livello Lichess rapid e classical, fra 600 e 2600, che spiega meglio quella precisione, con l’intervallo dell’80%: su una sola partita è molto largo, la stima sulle ultime 10 partite contro Maia è in **Progressi**; servono almeno 10 mosse non obbligate, vedi [docs/elo-partita.md](docs/elo-partita.md#prestazione-stimata-dalla-precisione)), quota di scelte senza perdite rilevanti e conteggi per classe (★ scelta di Stockfish, ✓ buona scelta, ?! imprecisione da 0,80, ? errore rilevante da 1,80, ?? errore grave da 3,00 o che concede o manca un matto in 1–2 mosse, □ mossa obbligata). Seguono il mini‑grafico cliccabile, con un pallino colorato su ogni imprecisione ed errore (il clic apre la mossa), le prime tre scelte di Stockfish nella posizione mostrata con valutazione dal lato del Bianco, e l’elenco mosse a due colonne; il simbolo compare anche sulla casa d’arrivo della mossa giocata. Le note su metodo e limiti sono raccolte nei riquadri ⓘ apribili. In Rivedi ← e → scorrono le posizioni quando il focus non è in un campo. La scacchiera mostra sempre la posizione prima della mossa in esame: l’elenco evidenzia quella mossa e il contatore sotto la scacchiera la nomina, con il numero di mossa, uguale per Bianco e Nero (per esempio «16. Bb3 · mossa 16 / 21»); dopo l’ultima mossa indica «Fine».

- **Suggerisci mossa:** in Gioca e nelle sessioni Drill, quando tocca a te, mostra la prima scelta di Stockfish (freccia blu, calcolata dal server) e la prima scelta di Maia al livello della partita (freccia rossa, calcolata da Maia sul server), con le mosse scritte sotto la scacchiera. Il suggerimento sparisce dopo la mossa. La mossa giocata dopo un suggerimento viene registrata come assistita (`assistedPlies`), segnata con 💡 in Rivedi ed esclusa dalle statistiche sulla qualità delle decisioni; annullando la mossa il segno viene rimosso.
- **Annulla ultima mossa:** in Gioca e Drill ritorna alla tua ultima decisione, togliendo anche la risposta di Maia o interrompendola se ancora in preparazione. Nei Drill conserva la sequenza iniziale. Disponibile anche dopo la conclusione; PGN importati e copie archiviate restano in sola revisione.
- **Cambio di livello durante la partita:** in Gioca, se nel pannello scegli un livello diverso da quello della partita in corso contro Maia o lo Sperimentale, compare **Applica … a questa partita** (`POST /api/games/{id}/level`). Il motore gioca subito al nuovo livello, e l’intera partita vale come giocata a quel livello: intestazione, titolo predefinito, PGN (`OpponentElo`), soglia di abbandono, analisi e statistiche usano il nuovo valore; il livello precedente non viene conservato. Non vale per Drill e partite contro Stockfish.
- **Ricomincia partita:** in Gioca, accanto ad Annulla ultima mossa, dopo una conferma riporta la partita alla tua prima decisione (`POST /api/games/{id}/reset`): tolte tutte le mosse, resta solo la prima mossa del motore se giochi col Nero; nelle partite contro Stockfish resta il tentativo di partenza. Come per l’annullamento, analisi e puzzle già creati restano in una copia archiviata.
- **Decisioni, non Elo:** il riepilogo principale mostra scelte senza perdite rilevanti, errori e vantaggi conservati. La somiglianza con Maia è facoltativa, in un pannello secondario chiuso: il profilo più probabile non indica quanto bene hai giocato, non assegna titoli e non parte automaticamente. Il calcolo rimane compatibile con i dati salvati. Metodo matematico in [docs/elo-partita.md](docs/elo-partita.md).
- **Ritmo Maia:** risposte con attesa variabile di circa 1,2–3,2 secondi, comprendente il tempo di inferenza, e breve animazione del pezzo. Il caricamento iniziale del modello può richiedere più tempo. Lo stesso ritmo vale nei Drill; il cambio di sezione annulla le risposte ancora in preparazione.
- **Gioca:** bianco, nero o colore casuale contro il vero modello Maia3 del sito; livello predefinito 600, con scelte rapide (600–2300) o cursore 600–2600, mosse legali e salvataggio automatico. Durante la partita, sotto il titolo «Mosse della partita» compaiono il nome dell'apertura e se sei ancora in teoria o ne sei uscito, e dopo quale mossa; le mosse di teoria sono in corsivo grigio ([docs/aperture.md](docs/aperture.md)). Aprendo Gioca riprendi la partita in corso; se l’ultima partita aperta è già finita, o non è una partita da giocare (per esempio un PGN importato), trovi invece la scacchiera nella posizione iniziale con il pannello pronto e **Inizia partita**, mentre la partita resta in **Rivedi**. Se hai scelto Bianco o Casuale puoi anche muovere subito un pezzo: la prima mossa avvia la partita col Bianco, con livello e motore del pannello. Finché l’analisi automatica della partita appena conclusa è in corso, la scacchiera e **Inizia partita** restano in attesa. Sotto la scacchiera, durante una partita in corso, ci sono **Nuova partita** (per prima e in evidenza; usa livello, colore e motore scelti nel pannello e chiede conferma se la partita in corso non è finita), **Annulla ultima mossa**, **Ricomincia partita**, **Suggerisci mossa** e **Abbandona partita**. Puoi trascinare i pezzi con mouse o touch oppure usare due clic; le promozioni si scelgono cliccando l’immagine del pezzo. La mossa compare subito sulla scacchiera, senza attendere il server: un pezzo trascinato resta dove lo lasci, mentre con due clic scivola dalla casa di partenza; se il server rifiuta la mossa, il pezzo torna al suo posto. A fine partita un riquadro sotto la scacchiera dice com’è finita (scacco matto, stallo, materiale insufficiente, ripetizione, regola delle 50 mosse o abbandono) e chi ha vinto; il re sotto scacco è sempre evidenziato in rosso, anche nella posizione di matto.
- **Rivedi:** revisione passo passo di entrambe le parti. Ogni posizione confronta mossa giocata, scelta Stockfish e mossa più probabile di Maia al livello selezionato, con probabilità e varianti. Le frecce e il selettore delle mosse mostrano la scacchiera prima della decisione. Sopra l'elenco delle mosse c'è il **nome dell'apertura** (codice ECO e nome del catalogo Lichess), che segue la posizione mostrata; le mosse di teoria sono in corsivo grigio e il pulsante **Teoria fino a… / Fuori teoria dopo…** porta all'ultima posizione di teoria ([docs/aperture.md](docs/aperture.md)). Restano importazione/esportazione PGN e momenti critici personali. Per vecchie analisi, ricalcolare per includere tutte le mosse.
- **Drill:** aperture (sette famiglie con 63 linee: Partita italiana, Difesa scandinava, Difesa russa, Sistema London, Difesa siciliana, Difesa Caro-Kann, Gambetto di donna; **Contro Maia** parte dalla fine della linea scelta, **Ripassa la linea** ti fa giocare le mosse di teoria dalla posizione iniziale, con ripasso dilazionato e posto nel piano di oggi, vedi [docs/aperture.md](docs/aperture.md#drill-delle-aperture-e-ripasso-delle-linee)), finale di torre, posizioni delle proprie partite e **Fine della teoria** (fino a tre, dall'ultima posizione di teoria delle tue aperture da curare o più giocate, vedi [docs/aperture.md](docs/aperture.md#il-tuo-repertorio)), mostrate con un’anteprima della posizione; 3–12 decisioni contro Maia e revisione dedicata.
- **Puzzle:** errori personali (da 1,80 in su, o matti mancati: le imprecisioni restano in Rivedi), alternative verificate, tentativi, indizi, soluzione e ripassi distanziati. Sulla scacchiera è evidenziata l’ultima mossa dell’avversario, quella che ha portato alla posizione (serve, per esempio, a riconoscere una presa en passant); dopo un tentativo sbagliato, quando la scacchiera torna alla posizione iniziale, l’evidenziazione torna su quella mossa. Ogni puzzle ha un **codice breve**, mostrato nel pannello e nell’elenco «Da ripassare»: numero della partita, numero della mossa e colore che muove (B o N), per esempio **#35-20N**. Per segnalare un puzzle basta citarlo. A puzzle risolto, il confronto con le frecce (la tua soluzione in verde, la mossa giocata in partita in bianco, la prima scelta di Maia in rosso) riporta accanto a ciascuna mossa il punteggio di Stockfish, sulla scala oggettiva dell’app, e la migliore per Stockfish quando è diversa dalla tua. Il punteggio della mossa di partita viene dall’analisi della partita, quello della tua soluzione dalla verifica del tentativo. A puzzle chiuso, accanto alla **variante di riferimento**, **Mostra** la riproduce da sola su una scacchiera in una finestra (lo stesso vale nel giudizio di posizione dell'Allenamento di oggi). Fra i puzzle da ripassare si parte da quelli mai mostrati, poi da quelli visti meno di recente: aprire un puzzle senza rispondere lo sposta in fondo, così all'apertura non ricompaiono sempre gli stessi. **Chiedi un indizio** dà fino a cinque indizi a scala, ricavati da Stockfish e Maia: prima il tipo di mossa da cercare (uno scacco, una cattura o una promozione; una mossa tranquilla che prepara una minaccia; una profilassi contro l'idea migliore dell'avversario; il miglioramento di un pezzo), poi il **motivo tattico** quando si riconosce (forchetta, inchiodatura, infilata, attacco di scoperta, pezzo intrappolato o indifeso), poi, con **Un altro indizio**, **la mossa che tenta**: quella che Maia giocherebbe più spesso al tuo livello invece della soluzione, con il motivo per cui non funziona e **Mostra** per vederne la confutazione; poi le **mosse candidate**, la soluzione nascosta fra una o due mosse sbagliate da considerare; infine il pezzo che muove, evidenziato sulla scacchiera. Ogni puzzle in cui chiedi un indizio o la soluzione registra il tipo di soluzione mancata, base delle **Lacune ricorrenti** in Progressi ([docs/lacune-studio.md](docs/lacune-studio.md)). Se rigiochi una mossa sbagliata che avevi già provato in una sessione precedente sulla stessa posizione, compare **Idea già provata** con la risposta che la confuta, e il puzzle torna entro un giorno finché l'idea non sparisce dalle ultime 3 sessioni.
- **Problemi:** problemi tattici da partite reali del database Lichess, per fasce di rating, con rating personale e stima Maia per livello. Vedi [Problemi da partite reali](#problemi-da-partite-reali).
- **Trova un’alternativa:** quando tutte le mosse ti sembrano perdenti, **Qui mi sento bloccato** (in Gioca) o **Qui mi sentivo bloccato** (in Rivedi, anche su partite di Maia online) segna il momento senza aiuti oppure apre una ricerca guidata su una scacchiera separata. Prima rispondi a due domande brevi (che cosa temi, quali mosse hai considerato); poi cerchi da solo una mossa che tenga la partita, con aiuti progressivi solo su richiesta. Stockfish accetta più alternative, non solo la prima scelta. Dopo la soluzione racconti che cosa l’ha resa convincente; la posizione torna in ripasso, con posizioni analoghe e controesempi verificati. Vedi [Trova un’alternativa](#trova-unalternativa).
- **Diagnosi prima della soluzione:** in Puzzle, Problemi e Blunder prevention, chiedendo la soluzione compaiono poche domande rapide (valutazione, minaccia temuta, candidata scartata e, facoltativa, «Cosa ti bloccava?», con l'opzione «candidate inconcludenti»); le mosse già provate e respinte contano da sole fra le candidate. Stockfish le confronta con la posizione e distingue soluzione non vista o scartata, valutazione pessimista o ottimista, minaccia non vista o fantasma. Dice anche che tipo di mossa era la soluzione: forzante, tranquilla con una minaccia, profilassi o miglioramento posizionale, con la spiegazione e il modo di cercarla; è il caso tipico delle posizioni di vantaggio in cui nessuna candidata sembra concludere. L'andamento, con le soluzioni non viste per tipo, è in Progressi. Si può saltare. Vedi [`docs/diagnosi-errori.md`](docs/diagnosi-errori.md).
- **Studio:** sezione separata con sei schede: Flashcard, Quiz, Esame di prova, Impara da una partita, Chiedi al tutor e Quaderno. Vedi [Studio](#studio).
- **Commento finale:** in Rivedi, su richiesta e dopo l’analisi Stockfish, DeepSeek riassume andamento della partita, punti riusciti e priorità di allenamento collegati alle posizioni. Solo al clic invia l’andamento delle valutazioni e fino a sei posizioni con le varianti, senza nomi dei giocatori; il commento viene salvato finché partita e analisi non cambiano.
- **Tutor DeepSeek:** spiegazioni e piano dopo la revisione Stockfish, con riflessione del giocatore e collegamenti agli esercizi. Vedi `docs/tutor-deepseek.md`.
- **Partite:** archivio delle ultime 50 partite, ciascuna con un numero univoco (**#12**) per indicarla senza ambiguità. Lo stesso numero compare nel titolo di Rivedi («Rivedi la partita #12») e in ogni allenamento che cita la partita di origine: «DALLA TUA PARTITA #12» in Puzzle e Blunder prevention, e «#12 · titolo» in Trova un’alternativa, nel piano di oggi, nelle posizioni personali dei Drill e in Studio. Il numero segue l'ordine di creazione, non cambia e non viene riusato; le partite esistenti sono numerate per data al primo avvio. Per ogni partita esito, apertura (codice ECO e nome), colore, qualità delle decisioni (se analizzate), numero di mosse e data; filtri per esito e anteprima della posizione finale al passaggio del mouse. **↓ PGN** su ogni riga scarica la singola partita; **Esporta PGN (N)** scarica in un unico file tutte le partite elencate con il filtro attivo (endpoint `GET /api/games/pgn?ids=…`, tempi inclusi).
- **Visualizza:** calcolo a mente. Una posizione di una tua partita, le mosse successive scritte ma non giocate sulla scacchiera, e una domanda esatta sulla posizione a cui portano (che pezzo c'è in una casa, quanti pezzi attaccano un pezzo, quante catture ci sono, se il re è sotto scacco, se è matto, quale mossa è legale). La linea parte da 2 semimosse e cresce fino a 8 con le risposte giuste. Vedi [docs/visualizzazione.md](docs/visualizzazione.md).
- **Mossa per mossa:** *Ragionamento mossa per mossa*, lezioni guidate da partite commentate in *Logical Chess: Move by Move* di Chernev, separate dagli esercizi delle tue partite. Dieci posizioni (sviluppo, minacce, difesa, ricerca di un piano), ciascuna con una domanda, tre indizi progressivi e la mossa da giocare sulla scacchiera; contano come giuste la mossa della partita e le alternative coerenti con l'obiettivo. Dopo la risposta, **l'idea** del libro (con partita e pagina) e la **valutazione di Stockfish** compaiono in due pannelli distinti, e la lezione segnala quando non coincidono. Ripasso distanziato proprio, con gli intervalli del piano di allenamento. **Segui la partita**: nove partite del libro (1, 2, 3, 6, 7, 10, 12, 14, 24) dall'inizio alla fine, dalla parte di chi vince (quattro col Nero, cinque col Bianco); indovini ogni mossa del tuo colore, quelle dell'avversario si giocano da sole con una nota e il giudizio del motore, e alla fine vedi quante mosse hai trovato al primo tentativo. Dopo ogni lezione, **Continua la partita →** riprende da lì la stessa partita. Vedi [docs/lezioni-libro.md](docs/lezioni-libro.md).
- **Progressi:** prestazione stimata sulle ultime 10 partite analizzate contro Maia (livello Lichess con intervallo dell’80%, vedi [docs/elo-partita.md](docs/elo-partita.md#prestazione-stimata-dalla-precisione)), evidenze iniziali, variazione degli errori rispetto al blocco precedente, temi in barre orizzontali, piano base di 25 minuti, storico degli esami di prova e diagnosi degli errori per categoria. **Lacune ricorrenti** mostra i gruppi di posizioni che risolvi al primo tentativo molto meno spesso del previsto: tipo di soluzione nei Puzzle, tema Lichess nei Problemi, finali con poco materiale come ipotesi. Sotto, **Quando l’indizio non basta** dice dopo quale indizio il tentativo successivo è ancora sbagliato, ed **Errori che ripeti** elenca le mosse sbagliate rigiocate nella stessa posizione in sessioni diverse. Per una lacuna confermata propone un **percorso di studio**: lezione con una tua posizione sbagliata, serie a tema in salita, serie mista senza etichetta, ripasso a distanza di giorni. Vedi [docs/lacune-studio.md](docs/lacune-studio.md). **Il tuo repertorio** raggruppa le tue partite dalla posizione iniziale per apertura (famiglia del catalogo Lichess) e colore: partite, punteggio, quota di decisioni senza perdite nelle 20 semimosse dopo la teoria, e dopo quante tue mosse arriva in media il primo errore; da 3 partite un'apertura con punteggio sotto il 40% o 20 punti sotto la tua media dopo la teoria è **da curare**. Ogni apertura porta a **Rivedi dove finisce la teoria** e **Allena da lì**, un drill dalla stessa posizione ([docs/aperture.md](docs/aperture.md#il-tuo-repertorio)). Aiuti e ripetizioni immediate non gonfiano i successi indipendenti.

I Puzzle personali compaiono dopo aver analizzato una partita contenente errori rilevanti. Per cominciare senza partite, utilizzare il catalogo Drill o importare un proprio PGN.

## Motori e dati

Maia3 non è una CNN: è la generazione Transformer descritta nel paper Chessformer. Si usa l'artefatto ONNX pronto del sito ufficiale, senza addestramento. Dal 30 ottobre 2026 gira solo sul server (`backend/maia.py`, onnxruntime): l'interfaccia chiede le previsioni a `POST /api/maia/predict`, che raccoglie in un'unica richiesta quelle fatte nello stesso momento e ricorda le posizioni già chieste. Il browser non scarica più il modello (circa 46 MB) né il runtime WebAssembly: l'interfaccia compilata pesa circa 1,4 MB. Vedi [docs/maia-server.md](docs/maia-server.md). Stockfish 19 gira in WSL.

Il catalogo delle aperture è `backend/data/openings.tsv`, generato dal catalogo Lichess (CC0) con `scripts/build_openings.py`. Le partite restano in `data/coach.sqlite3`; i problemi importati con `make puzzles` in `data/lichess_puzzles.sqlite3`, in sola lettura; gli asset sono in `models/maia3` e `vendor/stockfish`. Maia e Stockfish funzionano localmente. Il tutor DeepSeek opzionale richiede una chiave e invia i dati selezionati al servizio solo quando richiesto. Salvare la cartella `data` a server fermo per il backup; a server acceso usare il backup SQLite.

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

Prove Python (`tests/conftest.py`) e prove del browser impostano `CHESS_COACH_DISABLE_AUTH=1`, così le credenziali di `.env` non le bloccano; il login è verificato da `tests/test_auth.py` e `web/tests/login.spec.ts`. Le prove del browser usano Chromium di sistema (`/usr/bin/chromium`), il vero Maia e dati temporanei su una porta separata. Le prove Python verificano Stockfish, legalità, versioni, esercizi e registrazione dei progressi.

Le richieste Maia di gioco, revisione ed Elo condividono una coda: non vengono eseguite contemporaneamente sulla stessa sessione ONNX. Gli output vengono verificati anche nella dimensione e nella valutazione; in caso di numeri non validi il worker viene ricreato e la stessa inferenza ritentata una volta. Un errore persistente interrompe il calcolo senza salvare punteggi parziali. Le prove di recupero usano anche un worker simulato per iniettare errori numerici riproducibili.

## Dove estendere il progetto

| Percorso | Responsabilità |
|---|---|
| `web/src/engine/maia.ts` | Richieste a Maia sul server (a lotti) e scelta della mossa in Gioca |
| `backend/maia.py` | Maia3 sul server, unico punto di esecuzione: codifica, inferenza a lotti, `POST /api/maia/predict` ([scheda](docs/maia-server.md)) |
| `backend/engine.py` | Confine Stockfish e prospettiva delle valutazioni |
| `backend/main.py` | API, persistenza, analisi, Puzzle e piano iniziale |
| `backend/drills.py` | Catalogo e preparazione delle posizioni Drill |
| `web/src/Drills.tsx` | Sessione di pratica contro Maia |
| `docs/drill-puzzle-personalizzati.md` | Analisi del sito e progetto evolutivo del tutor |
| `backend/study.py` | API della sezione Studio: flashcard, quiz, esami, pacchetto partita, domande al tutor, quaderno |
| `web/src/study/` | Interfaccia della sezione Studio |
| `backend/alternatives.py`, `web/src/FindAlternative.tsx` | Trova un’alternativa: episodi di blocco, verdetti, aiuti progressivi, ripetizioni e casi analoghi |
| `backend/auth.py`, `web/src/Login.tsx` | Login con credenziali da `.env` e cookie di sessione firmato |
| `deploy/` | Unit systemd e virtual host nginx dell’istanza pubblica |

Questo è un prototipo funzionante ed estendibile. Non include ancora un modello calibrato delle competenze, o un generatore tattico a più mosse; le verifiche su posizioni nuove si limitano ai casi analoghi e ai controesempi di Trova un’alternativa, scelti fra le partite analizzate e i problemi importati. L'analisi individua fino a tre momenti critici per partita con budget limitato; i temi sono indicativi. Il piano attuale è semplice e trasparente, non un tutor autonomo completo.

Progetto indipendente, senza affiliazione a Maia Chess. Attribuzioni e licenze in `THIRD_PARTY.md`; sorgenti applicativi GPL-3.0, artefatti esterni con le rispettive condizioni.

Per fermare l'istanza in background: `make stop`. Il vecchio `python3 scripts/stop.py` resta disponibile per compatibilità.



## Aspetto della scacchiera

L'installazione sul PC usa il tema **Green** e i pezzi **Neo** richiesti, scaricati dai server pubblici di Chess.com e conservati localmente. Le immagini sono escluse da Git e conservano i diritti originali. Su un nuovo clone puoi installarle con `python3 scripts/install_chesscom_theme.py`, poi ricompilare il frontend. In assenza delle immagini sono disponibili una scacchiera CSS e pezzi Unicode di riserva.

Il menu della scacchiera, l’ingranaggio in alto a destra, cambia tema (Verde, Legno, Blu; gli ultimi due sono colori CSS senza immagini) e attiva o disattiva i suoni delle mosse, sintetizzati nel browser senza file audio. La scelta resta salvata nel browser. I font Inter e Fraunces (licenza SIL OFL 1.1) sono inclusi nel bundle tramite i pacchetti `@fontsource-variable`: l’interfaccia non contatta servizi di font esterni.

L'icona dell'applicazione (un cavallo con guantoni e caschetto da sparring) sta in `web/public`: `favicon.ico` (16, 32 e 48 pixel), `icon-192.png` e `icon-512.png` per `manifest.webmanifest`, che permette di aggiungere SparringMate alla schermata Home del telefono, e `apple-touch-icon.png` (180 pixel, con fondo pieno perché iOS arrotonda da solo gli angoli). Le icone non richiedono il login.

## Configurazione del tutor

`python3 scripts/configure_deepseek.py` configura la chiave con input nascosto. La credenziale rimane in `.secrets/deepseek.json`, esclusa da Git. La spiegazione viene salvata nel database con l'analisi a cui si riferisce. Dettagli sui dati inviati, sul modello e sui limiti in `docs/tutor-deepseek.md`.


## Esportare PGN e tempi

**Esporta PGN** è disponibile in Gioca, Rivedi e nelle sessioni Drill, anche a partita in corso. **Includi tempi** aggiunge i dati registrati a ciascuna mossa. In Gioca, anche **↓ Salva PGN** in testa al riquadro «Mosse della partita» scarica la partita, con i tempi. I file riportano risultato, nomi, data, posizione iniziale e apertura (`ECO`, `Opening`, se il PGN importato non le aveva già); l'importazione conserva anche i nomi originali, il risultato dichiarato e il controllo del tempo.

Le partite libere non hanno un conto alla rovescia: si registra il tempo attivo per mossa con l'annotazione PGN `[%emt h:mm:ss]`. In Gioca l'orologio di ciascun lato somma i tempi registrati e, per chi ha il tratto, scorre ogni secondo durante il turno; si ferma con la partita conclusa o mentre scorri le mosse già giocate. Contro Stockfish e il motore sperimentale scorre solo il tuo, perché le loro risposte arrivano dal server senza un tempo registrato. Il conteggio si sospende lasciando il pannello di gioco o nascondendo la scheda; il tempo di Maia comprende inferenza e attesa visibile. Il turno in corso viene recuperato dopo un normale ricaricamento nella stessa scheda. I dati delle mosse confermate restano nel database, anche dopo il riavvio. Un turno il cui inizio non è stato osservato rimane senza tempo; le mosse delle vecchie partite non ricevono valori inventati.

Nei PGN importati si conservano sia `[%clk ...]` (tempo residuo sull'orologio) sia `[%emt ...]` (durata della mossa), quando presenti. Disattivare Includi tempi esclude queste annotazioni dal download senza cancellare i dati. Annullare una mossa rimuove anche i relativi tempi; un'eventuale copia di revisione conserva la linea originale con i suoi tempi.


## Studio

La voce **Studio** raccoglie gli strumenti che trasformano le partite analizzate in esercizi di richiamo, separati da Gioca e Rivedi. Da **Rivedi → Decisioni**, **Studia questa partita** apre direttamente il pacchetto della partita. Le partite di confutazione contro Stockfish restano escluse.

- **Flashcard:** ogni lezione di **Spiega motivo** (Puzzle e Blunder prevention) diventa una scheda, salvo che la verifica più profonda abbia accettato la mossa; altre schede si creano dal pacchetto di una partita o dalle risposte del tutor. Il fronte mostra la posizione e una domanda; dopo **Mostra risposta** (tasto Spazio) compaiono la lezione e le frecce della mossa giocata e di Stockfish. Prima di girarla puoi anche giocare sulla scacchiera la mossa che sceglieresti, se vuoi: la scheda si gira e Stockfish la giudica con il punteggio oggettivo, accanto alla mossa di allora (la migliore compare solo se la tua non basta). La mossa non tocca il calendario: la valutazione del ricordo (tasti 1–4) decide il prossimo ripasso: *Di nuovo* dopo 10 minuti, poi 1 giorno, 3 giorni e intervalli crescenti con fattore di facilità in stile SM-2. Una scheda non ancora scaduta non si può rivalutare.
- **Quiz:** fino a cinque domande sulle tre decisioni più costose di una partita: la mossa migliore, la risposta più forte dell’avversario dopo il tuo errore e la valutazione della posizione. Ogni opzione sbagliata è controllata da Stockfish (perde almeno 1,50 rispetto a quella corretta; la tua mossa di allora può perdere meno); la domanda sulla valutazione è omessa vicino alle soglie di ±1,00. Conta solo la prima risposta.
- **Esame di prova:** 6–10 posizioni dai tuoi puzzle, con temi alternati e preferenza per quelle non viste negli ultimi 3 giorni, tempo limite di 8–20 minuti, nessun indizio e nessun riscontro fino alla consegna. Il criterio è quello dei puzzle (meno di 0,70 di perdita). Allo scadere del tempo l’esame si chiude da solo. Non modifica i ripassi; i risultati compaiono anche in **Progressi**, con un esame consigliato ogni 14 giorni.
- **Impara da una partita:** per ogni errore o imprecisione mostra mossa giocata, variante di Stockfish e risposta avversaria, con i collegamenti a Puzzle, Blunder prevention, Drill da qui, partita contro Stockfish con la tua mossa, domanda al tutor e una flashcard con la tua lezione.
- **Chiedi al tutor:** domande libere su una posizione (dal pacchetto, dal quaderno o incollando una FEN); muovere un pezzo sulla scacchiera prepara la domanda «Perché non …?». Le mosse citate, anche in notazione italiana (C, A, T, D, R) o UCI, vengono analizzate da Stockfish. Con DeepSeek configurato il tutor riceve solo quelle varianti; una risposta che cita mosse di pezzo o catture assenti dalle varianti viene scartata e sostituita dai fatti di Stockfish. Senza DeepSeek la risposta è costruita dalle sole varianti.
- **Quaderno:** errori e imprecisioni delle partite analizzate, raggruppati per tema, con le tue lezioni e i tre esempi più costosi per tema. **Esporta PGN annotato** (`GET /api/study/notebook.pgn`) scarica un capitolo per esempio: mossa giocata con perdita e lezioni come commento, variante di Stockfish come alternativa.

Verifiche dedicate: `tests/test_study.py` e `web/tests/study.spec.ts`.

## Problemi da partite reali

La sezione **Problemi** (nel menu **Altro** sul telefono, link diretto `?section=problems`) propone problemi tattici tratti da partite reali, presi dal [database dei puzzle di Lichess](https://database.lichess.org/#puzzles) (CC0). Va installata una volta:

```bash
make puzzles               # 3.000 problemi per fascia, circa 7 MB
make puzzles PER_BAND=5000
```

Lo script (`scripts/import_lichess_puzzles.py`) legge il file compresso in streaming senza salvarlo, tiene solo problemi con popolarità almeno 80, almeno 200 tentativi e deviazione del rating fino a 90, e si ferma quando tutte le dieci fasce sono piene (da “Fino a 800” a “Oltre 2500”): di solito in pochi secondi. Il file nuovo sostituisce il precedente solo a importazione completata. `--file` usa un CSV già scaricato. Dopo l'importazione la sezione funziona offline.

La prima mossa è quella dell'avversario, quasi sempre l'errore da punire: la scacchiera la mostra, poi tocca a te. La verifica avviene sul server mossa per mossa, quindi la soluzione non arriva al browser prima della fine; come su Lichess, qualsiasi matto è accettato anche se diverso da quello salvato. La fascia **Adattiva** sceglie problemi entro 100 punti dal tuo rating personale, che parte da 1200 e cambia una sola volta per problema (formula Elo, fattore K decrescente): al primo errore, alla richiesta della soluzione o alla soluzione pulita. Saltare prima di muovere non lascia traccia. Si può filtrare per tema. **Chiedi un indizio** dà fino a cinque indizi per mossa: il tipo di mossa (forzante, tranquilla con una minaccia, profilassi, miglioramento), il motivo tattico preso dai temi Lichess, la mossa che tenta (la scelta naturale di Maia al tuo livello, confutata da Stockfish), le mosse candidate (la soluzione fra una o due mosse sbagliate) e il pezzo che muove, evidenziato sulla scacchiera; come su Lichess, con un indizio il problema conta come non risolto per il rating. Se in Progressi parte un **percorso di studio**, la sezione apre prima la lezione e poi i problemi del percorso; **Problemi liberi** lo mette da parte senza abbandonarlo. A fine problema compaiono rating, temi, apertura, collegamento alla partita originale e la **stima Maia**: la probabilità che Maia, ai livelli 800–2300, giochi l'intera soluzione al primo colpo. Il rating del problema è calcolato da Lichess sui tentativi di chi risolve, non è l'Elo dei giocatori della partita. [Metodo, fonti e limiti](docs/problemi.md).

## Blunder prevention

**Come si leggono i punteggi.** In tutta l'app il punteggio è oggettivo: positivo se è avanti il Bianco, negativo se è avanti il Nero, chiunque muova. Quello che guadagna uno lo perde l'altro. Perdere 1,20 significa, per il Bianco, scendere di 1,20 (da 0,00 a −1,20); per il Nero, salire di 1,20 (da 0,00 a +1,20). Un matto si scrive «matto del Bianco in 3» o «matto del Nero in 3». Vedi [docs/giudizio-mosse.md](docs/giudizio-mosse.md).

La sezione **Blunder prevention** propone le posizioni delle tue partite analizzate prima di un blunder: una mossa che, rispetto alla migliore, ti costa almeno 20 punti di punteggio atteso (la stessa misura di **Valuta la posizione**: per esempio dal 55% al 35%), oppure concede un matto forzato. Dall'11 novembre 2026 si misura così, in punti e non in pedoni: vicino alla parità servono circa 2,20 di perdita, mentre da +8 a +7 non cambia niente e una vittoria buttata in patta è un blunder. Prima la regola chiedeva di scendere sotto −2,00 perdendo almeno 2,00. Un matto vale come ±6,00, la stessa franchigia del resto dell'app. Lo scopo è non ripetere l'abbaglio: è accettata qualsiasi mossa diversa da quella della partita che non sia a sua volta un blunder secondo la stessa misura. Non serve la prima scelta di Stockfish: vicino alla parità anche una mossa che perde 2,00 va bene. Le posizioni già perse e le mosse obbligate vengono escluse, e ogni candidato è ricontrollato prima del primo tentativo. Dal 29 ottobre 2026 restano solo gli **abbagli**, cioè gli errori che normalmente non faresti. Maia sul server, al livello della partita, deve giocare quella mossa meno del 25% delle volte, e la confutazione deve essere elementare (matto in 1–2, oppure almeno 2 pedoni persi entro 4 semimosse) o facile da trovare per l'avversario. Gli errori tipici del livello e quelli con confutazioni da calcolare si allenano nei Puzzle; il riquadro **Solo abbagli, non lacune** ne riporta il numero. Come nei Puzzle, fra le posizioni da ripassare si parte da quelle mai mostrate, poi da quelle viste meno di recente. Dal menu si apre subito la prima posizione; le regole e il riquadro sugli abbagli sono note apribili accanto alla scacchiera, e la pagina di riepilogo compare solo se non ci sono posizioni o le hai completate tutte.

I tentativi e i ripassi sono separati dai Puzzle. Dopo una scelta corretta o la richiesta di un esempio, puoi confrontare il vecchio errore, aprire la partita originale e passare alla posizione successiva. I retry e gli aiuti non gonfiano i successi al primo tentativo. Le analisi già presenti alimentano il catalogo automaticamente; per altre partite usa **Analizza partita**. [Criteri e limiti](docs/blunder-prevention.md).

In **Puzzle** e **Blunder prevention**, la mossa tentata viene mostrata subito e, se sbagliata, annullata lentamente dopo una breve pausa. Il pannello **Tentativi sbagliati** conserva gli errori della posizione con valutazione e perdita rispetto alla migliore alternativa. **Spiega motivo** richiede a DeepSeek una spiegazione basata sulle varianti Stockfish salvate; le spiegazioni vengono conservate per evitare richieste ripetute. Serve la configurazione DeepSeek già usata dal tutor. La spiegazione si apre in un pannello flottante che resta fermo mentre la pagina scorre: si trascina dalla barra del titolo, si ridimensiona dall’angolo e ricorda la posizione. **Gioca … contro Stockfish** apre in Gioca una partita che parte subito dopo il tentativo sbagliato: Stockfish risponde a piena forza (400.000 nodi per mossa), **Annulla ultima mossa** torna alla tua ultima scelta senza mai togliere il tentativo, e **Torna al puzzle** riporta all’esercizio. Queste partite compaiono nell’archivio e si possono analizzare, ma non generano puzzle né posizioni di Blunder prevention e non entrano nei Progressi. Nei Puzzle una mossa è rifiutata quando perde 0,70 o più rispetto alla migliore di Stockfish. Le nuove evidenze vengono registrate da questa versione; i tentativi storici senza valutazioni dettagliate rimangono conservati nei dati originali.


## Trova un’alternativa

Per le posizioni in cui ogni mossa sembra perdere. Come iniziare:

1. Durante una partita, quando tocca a te, premi **Qui mi sento bloccato**. **Segna e continua** salva il momento senza aiuti e lascia la partita com’è. **Aiutami a ragionare** apre l’esercizio nella pagina di Gioca, su una scacchiera separata: la partita aspetta e il tempo di riflessione continua a contare.
2. Oppure, in **Rivedi**, porta la scacchiera sulla posizione e premi **Qui mi sentivo bloccato**. Funziona anche con le partite importate da Maia online.
3. Rispondi alle due domande, anche con «Non ne vedo nessuna», e muovi sulla scacchiera la mossa che proponi.
4. Se serve, chiedi un aiuto alla volta: domanda sulla minaccia, direzione della ricerca, pezzo da osservare, mossa suggerita (con la previsione della risposta), spiegazione completa.
5. Dopo la soluzione rispondi alle due domande finali. La ripetizione viene programmata in **Allenamento**; **Cerca una posizione analoga e un controesempio** prepara casi nuovi verificati.

Ogni mossa riceve uno di quattro verdetti: alternativa valida, giocabile con una concessione, non risolve il problema, verdetto non affidabile. Durante la ricerca non compaiono valutazioni numeriche. Le soglie sono configurabili con `SPARRINGMATE_ALTERNATIVE_THRESHOLDS`.

Gli aiuti chiesti durante la partita rendono assistita quella decisione; la sola segnalazione no. **Gioca … nella partita** applica la mossa trovata solo se la partita è ancora in quella posizione.

La sezione è sotto **Altro → Trova un’alternativa**, con gli episodi da esaminare, quelli pronti oggi, quelli in programma e quelli completati. In **Progressi** trovi:

- l’autonomia sulle posizioni nuove;
- l’aiuto necessario;
- le difficoltà più frequenti;
- la ricorrenza della stessa idea nelle partite;
- i risultati contro Maia online per livello e cadenza.

Posizioni nuove e ripetizioni sono sempre conteggiate a parte. [Regole, dati e limiti](docs/trova-alternativa.md).

## Tattica, posizione e strategia

La revisione e le spiegazioni DeepSeek distinguono conseguenze tattiche, cambiamenti posizionali e piano strategico. Gli indicatori confrontano la posizione prima della mossa, dopo la scelta e dopo l'alternativa Stockfish: sono fatti descrittivi, non una scomposizione del punteggio NNUE. Il saldo materiale è separato dalla valutazione e i casi non spiegabili vengono segnalati come causa da approfondire. La guida è disponibile anche in Puzzle, Blunder prevention e Drill; i Progressi distinguono i tipi di evidenza senza diagnosticare carenze da pochi esempi. [Review, confronto con altri sistemi e limiti](docs/strategy-tactics-review.md).

**Perché è un errore.** Per ogni mossa che perde almeno 0,80, il riepilogo di Rivedi (selezionando la mossa), la revisione passo passo, il commento ai Puzzle e Blunder prevention mostrano in cima una frase in parole semplici: per esempio «Qxe5+ prende un pedone, ma la donna in e5 non è difesa: 3… Nxe5 la cattura». I motivi riconosciuti sono pezzo in presa, difesa tolta, minaccia non parata, linea aperta, forchetta o attacco doppio, infilata, pezzo intrappolato, attacco di scoperta, inchiodatura, promozione, matto subito o mancato, occasione mancata (la mossa non perde niente, ma la migliore vinceva materiale), re esposto e svantaggio di posizione. Ogni motivo è confermato da un controllo sulla scacchiera e dalla variante di Stockfish; le linee non si fermano a metà di uno scambio (se la mossa successiva di Stockfish è una cattura o uno scacco la linea prosegue); se nessun motivo è verificato non inventa una causa: scrive **Deriva dalla linea di Stockfish**, mostra la linea e il tasto **Mostra** la riproduce in una finestra, da sola o con ← →. **Guarda la variante sulla scacchiera** riproduce mossa per mossa la confutazione e la linea migliore. Nessun LLM: è deterministico e gratuito. [Dettagli](docs/spiegazione-errori.md).

## Andamento della valutazione

In **Rivedi → Andamento** il grafico mostra la valutazione Stockfish iniziale e dopo ogni mossa dei due colori. Sopra lo zero è favorito il Bianco, sotto il Nero, indipendentemente dall'orientamento della scacchiera. Il punteggio è espresso in unità di pedone: non è Elo né un conteggio del materiale. I matti sono indicati separatamente con rombi ai bordi e non ricevono un valore numerico.

Cliccando un punto, usando le frecce della tastiera sul grafico o scegliendo una posizione dall'elenco si aggiorna la scacchiera. **Tutte le valutazioni** apre anche la tabella. Il grafico riutilizza le valutazioni salvate e si aggiorna al termine dell'analisi. Per vecchie analisi incomplete, **Completa il grafico** ricalcola tutte le mosse; i segmenti mancanti non vengono interpolati. Nei Drill la curva parte dalla prima posizione analizzata, dopo la preparazione iniziale. La scala verticale si adatta alla partita e le valutazioni rimangono stime alla profondità di analisi raggiunta.

## Analizzare una posizione con Lichess

Il tasto **Analizza con Lichess**, sotto la scacchiera in Gioca, Rivedi, Blunder prevention, Puzzle e Drill, apre una finestra su lichess.org con la posizione attualmente mostrata e lo stesso orientamento. Funziona anche quando si rivede una mossa precedente, la soluzione di un esercizio o il vecchio errore in Blunder prevention. Quando è disponibile la cronologia (Gioca, Rivedi, Drill) trasferisce l'intera partita come PGN e apre l'analisi sulla posizione mostrata; nei Puzzle e in Blunder prevention trasferisce solo la FEN. Se la partita supera il limite di lunghezza del collegamento Lichess, il pannello offre di copiare il PGN da importare a mano. Le mosse provate su Lichess non modificano la partita locale. Il browser può aprire una scheda invece di una finestra; se blocca la popup è disponibile un collegamento alternativo.

## Analisi automatica e origine degli esercizi

Quando una mossa conclude una partita locale (matto o patta), Stockfish avvia automaticamente l'analisi dopo aver salvato la mossa. La schermata finale resta aperta e mostra l'avanzamento; l'analisi prosegue sul server anche chiudendo il browser. Riaprendo la partita si recupera il lavoro in corso, senza avviarne una seconda copia. Al termine, le posizioni adatte alimentano Puzzle e Blunder prevention. L'analisi può essere ricalcolata manualmente; le partite importate o interrotte restano analizzabili con il comando dedicato.

In ogni Puzzle e posizione di Blunder prevention, il riquadro **Dalla tua partita** mostra titolo, data di archiviazione e numero/colore della mossa. **Rivedi questa mossa nella partita** apre la revisione esattamente prima della decisione originale. Il riferimento è disponibile anche per gli esercizi già salvati e segue l'eventuale copia conservata quando si annullano mosse di una partita analizzata.

## Abbandonare una partita

Durante il gioco, **Abbandona partita** è disponibile sotto la scacchiera, anche mentre Maia pensa. Dopo la conferma viene registrata una sconfitta per il tuo colore, viene fermata la risposta di Maia e si avvia l'analisi automatica delle mosse giocate. Risultato e motivo restano salvati al ricaricamento e nel PGN esportato. La partita abbandonata resta consultabile, ma non accetta altre mosse o annullamenti. Se abbandoni prima della prima mossa, viene salvato il risultato senza avviare un'analisi vuota.

Anche il motore può abbandonare, come farebbe una persona, ma solo se accetti: quando la partita è palesemente persa per il suo livello, come farebbe un giocatore di quella forza (Stockfish a 30.000 nodi gli dà la soglia del livello o peggio, o un matto contro, nel numero di suoi turni consecutivi richiesto, dopo il minimo di semimosse: a 2000 e oltre −7,00 per 3 turni dopo 20 semimosse, a 600 −15,00 per 5 turni dopo 40, in proporzione in mezzo; a 1300 −11,00 per 4 turni dopo 30), al posto della mossa successiva Maia (o lo Sperimentale) chiede, in un riquadro sopra la scacchiera, «Maia ha manifestato l’intenzione di abbandonare. Accetti?»: finché non rispondi il motore resta fermo. **Accetta l’abbandono** chiude la partita: il riquadro di fine partita mostra «Maia abbandona · Hai vinto», la vittoria è salvata con `termination = engine_resign`, nel PGN compare `[Resignation "Black"]` (o `"White"`) e parte l'analisi automatica. **Continua a giocare** fa giocare al motore la sua mossa e la proposta non si ripete per le 20 semimosse successive. La proposta resta in attesa anche ricaricando la pagina; **Annulla ultima mossa** la ritira. Non vale per Drill e partite contro Stockfish. Soglie in `backend/main.py` (`resign_rule`: `RESIGN_CP`, `RESIGN_TURNS`, `RESIGN_MIN_PLY` per i livelli forti, le stesse con `_WEAK` per i deboli, `RESIGN_STRONG_ELO`, `RESIGN_WEAK_ELO`, `RESIGN_RETRY_PLIES`). Fino al 4 novembre 2026 la regola era unica (−7,00, 3 turni, 20 semimosse): a 600 Maia chiedeva di abbandonare già alla semimossa 21 con un pezzo in meno, in 12 partite su 29; risposta con `POST /api/games/{id}/resign-offer` (`accept` vero o falso).

### Puzzle: ripasso e confronto dopo la soluzione

La lista e il contatore dei puzzle da ripassare diminuiscono solo dopo un primo tentativo corretto senza indizi. Errori, soluzioni mostrate e successi dopo tentativi sbagliati mantengono il puzzle in scadenza. Una nuova sessione permette di riprovarlo; dopo un errore occorre attendere quattro ore per una nuova verifica indipendente. Un puzzle in cui ripeti una mossa sbagliata di una sessione precedente non va oltre le 24 ore e non viene ritirato finché l'idea non sparisce dalle ultime 3 sessioni. La pratica anticipata non promuove il ripasso e non cancella lo storico. Prossimo puzzle evita quelli già conclusi nella sessione di navigazione.

**Un puzzle per posizione.** Se ripeti lo stesso errore in un'altra partita (stessa posizione, anche arrivandoci con un altro ordine di mosse; contano pezzi, tratto, arrocchi ed en passant, non i contatori delle mosse), non nasce un puzzle nuovo: quello esistente torna subito da ripassare, la serie ripartita da zero, e nel pannello compare **↻ Errore ripetuto in N partite**. Rianalizzare la stessa partita non conta come ripetizione. **Puzzle imparati:** dopo 3 soluzioni indipendenti di fila (primo tentativo senza aiuti, alla scadenza) il puzzle esce dalla rotazione: non compare più nella lista, nel contatore, nel piano di oggi e fra le posizioni personali dei Drill, ma resta nello storico e nell'esame di prova. Rientra se ripeti l'errore in una partita. Le posizioni sono in `exercise_sources` (partita e semimossa di ogni occorrenza); `exercises.retired` vale `mastered` o `duplicate`. Al primo avvio dopo l'aggiornamento (5 novembre 2026) i doppioni già presenti sono accorpati nel primo puzzle della stessa posizione e i puzzle con 3 o più successi di fila sono considerati imparati. **Puzzle superati dalla regola:** a ogni avvio escono dalla rotazione (`retired = 'obsolete'`) i puzzle la cui mossa di partita, rigiudicata con la regola attuale (franchigia di ±600 e Matto mancato, vedi [docs/giudizio-mosse.md](docs/giudizio-mosse.md)), non è più un errore: per esempio i puzzle creati prima del 3 novembre 2026 in posizioni già perse con entrambe le mosse, come 10.Qe4 della partita #50 (Qf1 −7,08, Qe4 −9,11). Lì la mossa di partita veniva accettata come soluzione. Allo stesso modo, dal 6 novembre 2026 i puzzle nascono solo dagli errori da 1,80 in su e dai matti mancati, e quelli nati da imprecisioni (da 0,80 a 1,80) escono dalla rotazione.

**Puzzle nuovi, pochi al giorno.** Un puzzle mai tentato entra nella lista «Da ripassare» solo entro il limite delle nuove posizioni di **Organizza la settimana** (3 al giorno, salvo modifiche), contando i puzzle tentati per la prima volta nella giornata; entrano prima quelli con la perdita maggiore, e un puzzle nuovo già aperto mantiene il suo posto. Sotto la lista una nota dice quanti sono in attesa. Così un arretrato di puzzle nuovi non copre i ripassi. **Filtri:** sopra la lista, **Fase** (Apertura fino alla mossa 12, Finale quando restano al massimo 4 pezzi oltre a re e pedoni, altrimenti Mediogioco) e **Tema**, con il numero di puzzle per voce; valgono anche per il puzzle aperto all'inizio e per **Prossimo puzzle**. La fase compare anche nell'elenco.

Dopo una risposta corretta, la propria mossa rimane visibile brevemente, poi viene mostrata la posizione iniziale: freccia bianca per la mossa della partita originale, rossa per la prima scelta di Maia al livello della partita. Il pulsante consente di tornare alla propria soluzione. Il confronto non anticipa suggerimenti durante il tentativo.

## Importare Maia e pianificare gli allenamenti

**Importa PGN** accetta testo con più partite o più file, fino a 20 partite e 1 MB per operazione. Riconosce il colore umano contro Maia, conserva intestazioni e tempi presenti, distingue i duplicati tramite ID Maia e può avviare automaticamente l’analisi delle nuove partite. Gli errori vengono mostrati per singola partita. Non è una sincronizzazione dell’account: lo storico Maia provato senza autenticazione restituisce 403; usa Export → PGN sul sito e incolla il testo qui.

**Allenamento** propone prima i richiami scaduti, poi un numero limitato di posizioni nuove: in alto l'avanzamento del giorno e il pulsante del prossimo ripasso, sotto la coda e la striscia dei prossimi sette giorni. Nel riquadro richiudibile **Organizza la settimana** imposti minuti, limite delle nuove posizioni e giorni della settimana. La durata è stimata a due minuti per posizione. Puzzle e Blunder prevention usano intervalli di 4 ore, 1, 3, 7, 14, 30, 90 e 180 giorni; errori o aiuti azzerano la progressione. Un puzzle sbagliato resta in scadenza, ma il richiamo indipendente successivo attende quattro ore. Riaprirlo prima è pratica e non aumenta la padronanza. La lista giornaliera evita di proporre due volte la stessa posizione come puzzle e prevenzione.

Impostazioni, verifiche e scadenze sono salvate in SQLite; il calendario usa Europe/Rome e non invia notifiche esterne. Le prove anticipate non fanno avanzare l’obiettivo giornaliero. Il calendario misura il richiamo di posizioni già viste, non ancora il trasferimento delle abilità alle nuove partite.

La [guida pratica](docs/training-guide.html) si apre da **Allenamento → Apri la guida** in una popup con indice navigabile, impaginazione per telefono e stampa/PDF. È scaricabile in HTML per la lettura offline; se il browser blocca la popup, compare un collegamento per aprirla in una nuova scheda. Spiega importazione, calendario e strumenti di Studio e contiene tutorial adattati al lavoro contro Maia per Aimchess, MoveTrainer e Noctie. Documentazione ufficiale verificata il 6 ottobre 2026; le aree personali dei servizi esterni non sono state provate con l’account dell’utente. Il sorgente resta in `docs/training-guide.md`; per rigenerare l’HTML usa `pwsh -File scripts/build_training_guide.ps1` (PowerShell 7, nessuna dipendenza aggiuntiva).

Verifiche dedicate: `tests/test_batch_import.py`, `tests/test_training_schedule.py` e `web/tests/training-plan.spec.ts`, oltre alle regressioni di Puzzle, Blunder prevention, analisi automatica e collegamenti Lichess.

## Qualità delle decisioni e valutazione delle minacce

**Rivedi → Decisioni** e il riepilogo dopo la partita mostrano solo le decisioni non obbligate del giocatore, esclusa l'apertura preimpostata dei drill. Soglie operative: perdita <80 centesimi senza peggioramento rilevante; 80–179 imprecisione; ≥180 errore rilevante, che nel riepilogo di Rivedi diventa errore grave (??) da 300. La perdita si calcola con una **franchigia**: ogni valutazione è limitata a ±600 centesimi e ogni matto vale ±600, perché oltre quella soglia la partita è decisa e un margine più grande non cambia nulla (da +18 a +12, o da −12 a −18, la perdita è 0). Mancare un matto in 1 o 2 mosse è un **matto mancato** (#?), una categoria a sé contata a parte, anche se la posizione resta vinta. La stessa regola vale per Puzzle, pratica libera, diagnosi ed Esame di prova (accettata una perdita sotto 70 che non manchi un matto in 1–2); le analisi già salvate sono ricalcolate alla lettura, gli esercizi già creati restano. Dettagli e limiti in [Giudizio delle mosse](docs/giudizio-mosse.md). Vantaggio conservato significa valutazione ≥150 prima e dopo la propria mossa, non conversione dell'intera partita. I matti mantengono il segno separato dalla valutazione numerica. Questi indicatori dipendono dal budget Stockfish e non sono Elo.

**Progressi** separa partite e drill e confronta fino a 10 sessioni recenti con le 10 precedenti, con denominatori espliciti. È un confronto descrittivo: avversari e difficoltà non sono controllati. Le analisi obsolete e le copie conservate dopo annullamento non vengono conteggiate.

**Valuta la posizione** (voce del menu, sotto «Altro» sul telefono; ci portano anche **Valuta una posizione** in Allenamento e in Progressi) campiona tutte le categorie di valutazione, non solo errori o posizioni recuperabili. Si registra giudizio, sicurezza, minaccia temuta, impressione di partita già persa e familiarità prima di mostrare valutazione e variante. Le risposte sono persistenti e non modificabili; la stessa posizione non viene proposta nuovamente come nuova. Gli esercizi non vengono presi da sparring ancora in corso. Le posizioni ricordate sono escluse dagli indicatori di primo incontro. “Allarme di sconfitta non confermato” significa impressione di posizione persa con valutazione Stockfish ≥−100 centesimi; non è una diagnosi psicologica né una garanzia di facilità. Le fasce ±1 e ±3 sono convenzioni didattiche. Dopo la risposta, **Da dove vengono i punti** scompone il punteggio di Stockfish dal punto di vista di chi muove: materiale sulla scacchiera (pedone 1, cavallo e alfiere 3, torre 5, donna 9), materiale alla fine della variante (quello che la linea guadagna è il colpo da trovare, già contato dal motore), punteggio atteso corrispondente (curva logistica di Lichess) e il resto, che viene da sicurezza del re, attività, pedoni passati e iniziativa. Il punteggio misura le probabilità di vincere, non i pedoni: due pedoni puliti senza compenso valgono spesso +4 o più. Lo stesso riquadro compare nel risultato della diagnosi «Cosa vedevi?» di Puzzle, Problemi e Blunder prevention (`backend/points.py`). Queste verifiche sono separate dai ripassi puzzle e non avanzano il calendario automaticamente.

API locali: GET `/api/games/{id}/decision-quality`, GET `/api/learning-progress`, POST `/api/position-judgments/next`, POST `/api/position-judgments/{id}`. La stessa domanda sulla valutazione e sulla minaccia compare anche prima di mostrare una soluzione: vedi [Diagnosi prima della soluzione](docs/diagnosi-errori.md). Evidenza Stockfish congelata al momento della proposta; tabella SQLite `position_judgments`. Il tutor rispetta il ragionamento riferito dal giocatore e non deduce emozioni o omissioni dalle sole mosse.

## Modello sperimentale di mosse umane

Il laboratorio locale in [`experiments/human-policy`](experiments/human-policy/README.md)
addestra un piccolo Transformer su partite pubbliche Lichess rapid. Input:
posizione e rating del giocatore al tratto; output: prime 5 mosse con probabilità
e probabilità residua delle altre. GPU RTX 4050 supportata con ambiente Python
separato, download iniziale limitato, checkpoint riprendibili e rapporto per
fascia di rating. È un prototipo non calibrato.
Procedura e limiti: [scheda tecnica](docs/human-policy.md).

### Giocare contro il motore sperimentale

Solo in **Gioca**, sul PC e anche sull’istanza pubblica (lì lo installa e lo avvia `make deploy`, vedi [`deploy/SERVER.md`](deploy/SERVER.md)). Puzzle, Blunder prevention, tutor e stima del
profilo restano su Maia e Stockfish.

1. Avvia il servizio, in un terminale a parte: `make experimental` (porta 8044,
   checkpoint attivo del ciclo mensile in `data/cycles/ledger.json`, oggi `2026-08`; un altro con `CHECKPOINT=...`).
2. Attiva l'opzione in `.env`: `SPARRINGMATE_EXPERIMENTAL_ENGINE=http://127.0.0.1:8044`.
   Il file viene riletto a ogni richiesta: non serve riavviare SparringMate, e
   togliendo la riga il selettore scompare.
3. Nel pannello **Nuova partita** compare **Motore: Maia | Sperimentale**, con lo
   stato del servizio e l'avviso «Livello Elo non ancora calibrato». Maia resta
   il predefinito.

Motore e versione del modello sono fissati all'avvio della partita: il cambio
vale per la partita successiva, e quella in corso resta salvata (con la solita
conferma). Lo storico mostra «Contro Sperimentale (versione)» e il PGN riporta
`OpponentEngine`, `OpponentEngineVersion`, `OpponentElo` e `MoveSelection`. Se il
servizio non risponde o restituisce dati non validi, la partita si ferma con un
messaggio e **Riprova**: non si passa mai a Maia di nascosto. Dettagli:
[scheda del motore sperimentale](docs/motore-sperimentale.md).



### Scelta del motore locale — 24 ottobre 2026

`make experimental` carica l'ultimo modello accettato nel registro del laboratorio,
verificandone pesi e rapporto. Attualmente è il ciclo agosto, 20.000 passi totali,
specializzato 600–1500. Per confrontare la versione precedente:
`make experimental CHECKPOINT=runs/monthly/2026-09/best.pt`.
La selezione avviene all'avvio del servizio; una nuova sessione di training non
cambia i pesi di un servizio già attivo.

In Gioca, «Partita attuale» indica il motore fissato nella partita (la versione
esatta è nel menu dell’ingranaggio, sotto «Versione del motore»); «Prossima
partita» indica la scelta che verrà applicata premendo Inizia/Nuova partita.
La preferenza Maia/Sperimentale viene ricordata dopo una ricarica. Un servizio
indisponibile non cambia automaticamente la preferenza in Maia.

### Ricerca sullo sparring partner umano

Il laboratorio offre un [banco di prova tattico](experiments/human-policy/documentazione/TATTICA.md)
per distinguere accuratezza sulle mosse umane e gestione delle minacce.
Gli esperimenti non modificano il motore selezionato per giocare.

La [guida alla sperimentazione del motore umano](experiments/human-policy/documentazione/SPERIMENTAZIONE-GUIDA.md) spiega risultati, limiti e confronto con distillazione.
