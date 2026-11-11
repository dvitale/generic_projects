# Aperture: nome e uscita dalla teoria

Ogni partita riceve il nome dell'apertura e l'ultima mossa di teoria. Li calcola il server
(`backend/openings.py`) a ogni lettura della partita, senza nulla di salvato nel database: anche le partite vecchie
li hanno.

## Da dove vengono

Il catalogo è [`lichess-org/chess-openings`](https://github.com/lichess-org/chess-openings) (CC0, pubblico
dominio): circa 3.900 linee con codice ECO, nome e mosse, fissate al commit indicato nella prima riga di
`backend/data/openings.tsv`. Il file si rigenera con:

```bash
.venv/bin/python scripts/build_openings.py
```

Lo script rigioca ogni linea con python-chess e salva la posizione finale in formato EPD (la FEN senza i contatori
delle mosse), più le posizioni intermedie che la linea attraversa, senza nome. I nomi restano in inglese, come
su Lichess.

## Le regole

- Le posizioni della partita si confrontano con quelle del catalogo, non le sequenze di mosse: un ordine diverso
  che porta alla stessa posizione (una trasposizione) riceve lo stesso nome. L'en passant conta solo se la presa
  è davvero possibile, come nelle EPD di Lichess.
- **Nome dell'apertura**: quello dell'ultima posizione della partita che ha un nome nel catalogo. In Rivedi il nome
  segue la scacchiera: è quello dell'ultima posizione con un nome raggiunta fino a lì.
- **Uscita dalla teoria**: l'ultima posizione della partita che sta nel catalogo, con o senza nome. Esempio:
  1.e4 e5 2.Cf3 Cc6 3.Ab5 a6 4.Aa4 Cf6 5.h3 è «C70 Ruy Lopez: Morphy Defense» (il nome arriva a 3…a6), ma la
  teoria continua fino a 4…Cf6, che sta su molte linee con un nome; 5.h3 è la prima mossa fuori.
- Nessuna posizione riconosciuta (per esempio una partita da una posizione di finale): nessun nome.

## Dove compare

- **Partite**: codice ECO e nome sotto il titolo di ogni riga (campo `opening` di `GET /api/games`, con `eco`,
  `name`, `bookPlies`).
- **Rivedi**: riga sopra l'elenco delle mosse, con il nome della posizione mostrata e il pulsante **Teoria fino a…**
  o **Fuori teoria dopo…**, che porta all'ultima posizione di teoria; le mosse di teoria sono in corsivo grigio
  (campo `opening` di `GET /api/games/{id}`, con anche `positions`, le posizioni con un nome e la loro semimossa).
- **Gioca**, nella partita in corso: sotto il titolo «Mosse della partita», il nome della posizione mostrata e, sotto,
  «In teoria» o «Fuori teoria dopo…»; le mosse di teoria sono in corsivo grigio. Si aggiorna a ogni mossa, perché
  ogni risposta del server porta la partita con il campo `opening` ricalcolato.
- **PGN esportato**: intestazioni `ECO` e `Opening`, se il PGN importato non ne aveva già.

## Limiti

È un catalogo di nomi, non un libro di aperture completo: una linea di teoria che nessun nome raggiunge risulta
«fuori teoria» prima del dovuto, e le varianti molto profonde non ci sono. L'uscita dalla teoria è quindi una
regola fissa e verificabile, non il giudizio di un teorico.

## Il tuo repertorio

In **Progressi → Il tuo repertorio** (`GET /api/openings/repertoire`, `openings.repertoire`) le tue partite dalla
posizione iniziale sono raggruppate per **famiglia** (la parte del nome prima dei due punti: «Sicilian Defense»,
«Ruy Lopez») e per colore. Drill (l'apertura è preimpostata), partite contro Stockfish e copie di revisione sono escluse.

Per ogni famiglia:

- **partite** e **punteggio** delle partite finite, dal tuo lato (vittoria 1, patta ½);
- **dopo la teoria**: la quota delle tue decisioni senza perdite rilevanti (perdita sotto 80 centesimi, la stessa
  soglia di Decisioni) nelle `AFTER_BOOK` = 20 semimosse dopo l'ultima posizione di teoria, solo nelle partite
  analizzate. Le mosse di teoria non contano: lì si gioca a memoria;
- **primo errore**: in media, alla quantesima tua mossa dopo la teoria arriva la prima perdita di almeno 80
  centesimi, nelle partite che ne hanno una;
- **stato**: con meno di `WATCH_MIN` = 3 partite «poche partite» (nascoste finché non premi «Mostra tutte»);
  da 3 in su **da curare** se il punteggio è sotto `WEAK_SCORE` = 40% oppure la quota dopo la teoria è almeno
  `WEAK_DROP` = 20 punti sotto la tua media su tutte le famiglie.

Ogni famiglia porta alla posizione in cui finisce la teoria nella tua partita più recente con quell'apertura
(**Rivedi dove finisce la teoria**) e a un drill da lì (**Allena da lì**).

Limiti: una partita conta per il punteggio anche se è stata decisa molto dopo l'apertura; una famiglia unisce
varianti molto diverse (l'elenco `variations` le riporta); le soglie sono da verificare sui dati reali dopo
qualche settimana d'uso.

## Drill dalla fine della teoria

Il drill `opening:<id partita>` riparte dall'ultima posizione di teoria di quella partita, con le stesse mosse
precedenti e lo stesso colore, contro Maia, per il numero di decisioni scelto. Il catalogo dei drill propone fino
a tre di queste posizioni, una per famiglia: prima le aperture da curare, poi le più giocate.

## Varietà d'apertura di Maia

`scripts/measure_opening_variety.py [partite] [livello] [semimosse]` fa giocare Maia contro sé stessa, con gli stessi
semi in ogni modalità di scelta delle mosse, e conta le famiglie d'apertura raggiunte. Su 300 partite e 16
semimosse, con la regola in vigore fino al 1° novembre 2026 (Bilanciata e Solida a temperatura 1 e top-p 0,9 fino
alla mossa 8):

| Livello | Completa | Bilanciata / Solida | Tutte le mosse fino alla mossa 8 |
|---|---|---|---|
| 1100 | 55 | 36 | 55 |
| 1500 | 54 | 42 | 54 |
| 1900 | 62 | 46 | 62 |

Tagliare l'ultimo 10% delle mosse in apertura perdeva da un quinto a un terzo delle famiglie, come nello studio di
Mobile Maia. Ora vale la sua regola: Bilanciata e Solida usano l'intera distribuzione di Maia fino alla mossa 5,
poi la propria (`OPENING_MOVES`, `OPENING` in `backend/maia.py`; vedi [verifica-maia.md](verifica-maia.md)).

Con la regola nuova, a 1500 (300 partite, 16 semimosse): Completa 54 famiglie, Bilanciata 54, Solida 54, contro
le 42 di Bilanciata e Solida con la regola precedente.

Lo script misura solo la varietà, non la forza. Mobile Maia ha misurato anche quella: a 1600 la sua impostazione
(tutte le mosse fino alla mossa 5, poi temperatura 1 e top-p 0,95) ha fatto il 60,7% dei punti contro la scelta su
tutte le mosse. Dopo la mossa 5 le nostre modalità sono diverse dalla sua, quindi quel dato non vale tale e quale.

## Drill delle aperture e ripasso delle linee

Dall'11 novembre 2026, in **Drill → Aperture**, ci sono sette famiglie: Partita italiana, Difesa scandinava, Difesa russa
(Petroff), Sistema London, Difesa siciliana, Difesa Caro-Kann e Gambetto di donna, con 63 linee in tutto
(`backend/opening_lines.py`).

### Da dove vengono le linee

La scelta segue il catalogo dei drill di Maia Chess per queste famiglie (frontend `CSSLab/maia-platform-frontend`,
commit `91c45f3`, file `src/constants/maia_openings_expanded.json`, esaminato l'11 novembre 2026). Ci sono in più le
linee che ricorrono nelle tue partite: Damiano 3…Cxe4 con 4.De2 nella Russa (11 partite su 14), Paris Defense e
Anti-Fried Liver nell'Italiana, Valencian e Gubinsky-Melts nella Scandinava, Tartakower nella Caro-Kann. Sono state
aggiunte anche le risposte di teoria a due linee dubbie: 5…Ca5 (Polerio) contro la Fried Liver e la Stafford
accettata con 5.d3. Le mosse sono fatti scacchistici, ricontrollati qui. I testi di Maia (licenza GPL-3) non sono
copiati: le descrizioni sono nostre. Il nome di ogni linea è quello del catalogo Lichess (CC0, `openings.tsv`) quando
la posizione finale ne ha uno, senza il prefisso della famiglia. Le poche posizioni senza nome hanno un nome
descrittivo, per esempio «London System, 3.e3» o «Damiano Variation, 4.Qe2».

### Come funziona un drill di Maia Chess

Lo si ricava dal codice (`useOpeningDrillController.ts`):

1. La linea scelta è **già giocata sulla scacchiera**. Il giocatore non deve ricordare le mosse di libro: parte dalla
   fine della linea, col colore scelto.
2. Si giocano poi le mosse scelte contro Maia. Per le prime 6 semimosse (`DRILL_BOOK_SAMPLING_MAX_PLIES`) Maia
   risponde pescando, con i loro pesi, le mosse di un libro di partite umane del livello scelto. Il libro sta su un
   servizio privato del loro server (`play/get_book_moves`); poi Maia usa la propria rete.
3. Alla fine Stockfish classifica le mosse, e Maia stima il livello che spiega meglio le scelte.

### I due modi in SparringMate

- **Contro Maia** (`POST /api/drills/line:<linea>/start`) fa come Maia Chess. La linea è sulla scacchiera e continui
  tu, con livello, colore e numero di mosse delle impostazioni. È un Drill normale: annulla, suggerimento,
  revisione delle sole decisioni giocate dopo la linea, e alla fine la valutazione del drill (sotto). Le risposte di Maia sono quelle di Gioca: fino alla mossa 5
  Maia usa tutta la sua distribuzione, addestrata su partite umane, al posto del libro privato di Maia Chess.
- **Ripassa la linea** (`/api/opening-lines/sessions`) mette alla prova la memoria della teoria, cosa che Maia Chess
  non fa:
  - parti dalla posizione iniziale e giochi le mosse del tuo colore;
  - una mossa è di libro se porta a una delle posizioni che le linee selezionate raggiungono da lì, quindi conta la
    posizione, non l'ordine delle mosse;
  - una mossa fuori dal libro non viene giocata: l'errore è registrato una volta per posizione, con tutte le mosse
    provate, e compare la mossa di teoria;
  - **Mostra la mossa di teoria** è un aiuto e conta come tale.

  L'avversario risponde subito dal libro. Se il ripasso arriva dal piano, cioè da una linea in scadenza, va verso
  quella linea. Altrimenti sceglie fra le mosse di libro con un peso per ciascuna. Il peso è la somma, sulle linee che
  passano da quella mossa, di 1, più 2 per ogni tua partita che ha raggiunto la fine della linea, più 3 se la linea è
  da ripassare o era stata sbagliata. Il ripasso finisce dove finisce la linea, che
  può poi proseguire contro Maia (**Continua contro Maia da qui**). In **Linee del ripasso** scegli quali linee
  l'avversario può giocare. Ci sono solo quelle che nessun'altra linea prolunga: la scelta resta nel browser.

### La valutazione del drill

Dall'11 novembre 2026 il drill segue anche la fine di un drill di Maia Chess (`DrillPerformanceModal.tsx`,
`useOpeningDrillController.ts`).

- **Durata**: da 3 a 20 tue mosse, 10 predefinite, o **Senza limite** (`target` 0 in `POST /api/drills/{id}/start`).
  Su Maia Chess è un cursore da 5 a 20 più ∞, con 10 iniziali.
- **Traguardo**: compare «Traguardo raggiunto (10/10 mosse). Prolunga il drill o termina con la valutazione.».
  **Prolunga il drill** toglie il limite; **Termina e valuta** chiude il drill e apre la valutazione, ed è disponibile
  anche prima del traguardo, quando tocca a te (`POST /api/games/{id}/drill/target`: 0 prolunga, il numero attuale
  di decisioni chiude). Chiudere il drill avvia subito l'analisi Stockfish (`queue_analysis` automatica), come la
  fine di una partita.
- **Valutazione del drill** (`web/src/DrillReview.tsx`), sulle sole tue mosse dopo la linea, senza le mosse
  obbligate e quelle giocate dopo un suggerimento:
  - **replica** con avanti, indietro e **Riproduci** (una semimossa ogni 0,9 secondi);
  - **andamento della valutazione**: probabilità di vittoria del Bianco, con un punto per ogni tua mossa colorato
    secondo la classe; cliccando si va alla posizione. Sotto, la valutazione a inizio e fine drill;
  - **precisione** (formula di Lichess, come in Rivedi), quota **senza perdite rilevanti** e conteggi per classe,
    con il giudizio di Maia Chess: da 90% «Ottima prova», da 70% «Buona prova», sotto «Questa apertura va allenata
    ancora», più il numero di errori gravi e matti mancati;
  - **decisioni critiche**: fino a 5, in ordine di gioco, fra imprecisioni, errori, errori gravi e matti mancati,
    con la perdita e la mossa migliore;
  - **somiglianza con Maia**: il confronto di Rivedi (`RatingPanel`, stesso metodo `maia3-drill-match-v2` del
    drill ufficiale) parte da solo. Servono almeno 10 tue decisioni non obbligate: con meno, lo dice e non calcola;
  - **Rigioca la stessa linea** (stessa linea, colore e livello, durata delle impostazioni), **Prossimo drill** e
    **Rivedi nel dettaglio**.

Differenze rimaste da Maia Chess:

- Le soglie delle classi sono quelle di SparringMate (imprecisione da 0,80, errore da 1,80, errore grave da 3,00 sulla
  scala con la franchigia), non le loro: là un errore grave è una perdita di almeno 10 punti di probabilità di
  vittoria e un'imprecisione di 5.
- La «mossa eccellente» di Maia Chess (rara per Maia e almeno 5 punti sopra la media pesata da Maia) non c'è: qui la
  classe più alta è la scelta di Stockfish.
- La loro precisione è la quota di mosse buone o eccellenti; qui è la formula di Lichess. La quota di Maia Chess
  corrisponde a **Senza perdite rilevanti**.
- Il loro livello Maia non ha un minimo di mosse; qui servono 10 decisioni.

### Ripasso dilazionato

Ogni linea completata ha uno stato per colore (`opening_line_reviews`).

- Senza errori né aiuti avanza di un livello sugli intervalli dei Puzzle: 4 ore, 1, 3, 7, 14, 30, 90 e 180 giorni.
- Con un errore o un aiuto torna al livello 0 e rientra dopo 4 ore.
- Un ripasso fatto prima della scadenza è pratica e non cambia il calendario.

Ogni ripasso entra in `training_reviews` (tipo `line`), quindi conta nelle verifiche di oggi. Le linee già ripassate
almeno una volta tornano nel piano come **Ripasso linea**. Quelle mai ripassate non vengono prescritte: il catalogo
si apre da Drill.

In `GET /api/opening-lines?color=w|b`, per ogni linea:

- `met` è il numero di tue partite col colore scelto che ne hanno raggiunto la posizione finale. Contano le partite
  dalla posizione iniziale, esclusi drill, partite contro Stockfish e copie, e solo le prime 40 semimosse.
- `games` è lo stesso conteggio per la posizione di partenza della famiglia.

## Prossimi passi

Nessuno in corso per le aperture.
