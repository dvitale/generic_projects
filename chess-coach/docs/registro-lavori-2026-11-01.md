# Registro dei lavori del 1° novembre 2026

Il resoconto copre il lavoro fatto dopo il commit `7058859` (indizi a scala, lacune, percorsi di studio). Per ogni
operazione riporta che cosa è cambiato, perché, dove e con quali prove. Nulla di questo lavoro è ancora in un commit.
Le schede tecniche di ogni area restano la fonte per i dettagli: qui ci sono le decisioni e il percorso.

## Fonti

- **Paper Queen**: Bhaskar, Cheng, Chen, «Language Models that Play Chess and Explain Their Moves», arXiv
  2610.03695, letto per intero, appendici comprese. Le idee riprese vengono soprattutto dall'appendice D: spiegazioni
  a modello costruite da Stockfish, senza LLM. Le cinque idee utili sono elencate in
  [PLAN-indizi-puzzle.md](PLAN-indizi-puzzle.md).
- **Mobile Maia**: app Android libera (`Dash1971/maia-chess-android`), con il sito `mobilemaia.org` e le sue ricerche.
  Da qui vengono:
  - il catalogo delle aperture Lichess abbinato per posizione;
  - la regola di varietà nelle prime 5 mosse;
  - la misura delle «famiglie d'apertura»;
  - le probabilità di Maia sulle mosse di un pezzo.

## Operazioni

### 1. Linee che non si fermano a metà di uno scambio (idea 2 del paper)

- **Cosa:** `Evaluator.settle` in `backend/engine.py`. Se alla fine della linea di Stockfish la mossa successiva è
  una cattura o uno scacco, la linea si allunga di 2 semimosse, al massimo 6 volte, con 10.000 nodi per ogni
  controllo. Si applica alla mossa migliore e a quella giocata, in `compare` e `compare_candidates`. I testi di
  `explain.py` mostrano ora la linea intera, non più le prime 9 semimosse. `expected()` (punteggio atteso, curva di
  Lichess) è passata da `alternatives.py` a `engine.py`, perché ora serve a più moduli.
- **Perché:** una linea troncata a metà di uno scambio faceva sembrare persa una figura che veniva poi ripresa, o
  nascondeva la perdita vera.
- **Prove:** `tests/test_explain.py`. Nella posizione con Bxc6 la linea si allunga a 3 semimosse; una linea
  tranquilla resta invariata.
- **Scheda:** [spiegazione-errori.md](spiegazione-errori.md).

### 2. La mossa che tenta (idea 1 del paper)

- **Cosa:** `diagnosis.tempting`. Maia, al livello del rating del giocatore, propone le sue tre mosse più probabili.
  La prima che non è la soluzione, che verrebbe scelta da almeno il 10% dei giocatori e che perde almeno 10 punti di
  punteggio atteso diventa un livello d'indizio, con **Mostra** per vederne la confutazione. Il motivo dell'errore è
  citato solo se non rivela la soluzione (`explain.SAFE_MOTIFS`); altrimenti l'indizio confronta a parole l'esito
  delle due mosse.
- **Perché:** spesso chi resta bloccato su un puzzle sta considerando proprio la mossa naturale sbagliata. Dirgli
  perché non funziona aiuta più che indicargli il pezzo da muovere.
- **Prove:** `tests/test_diagnosis.py`, con Maia simulata, copre:
  - il testo per Qg8+;
  - il caso dello stallo;
  - la mossa rara, che non dà indizio;
  - Maia assente, che non dà indizio.

  In `tests/test_gaps.py` la mossa che tenta è disattivata, perché lì il Maia vero ne trovava una e cambiava il
  numero di indizi. `web/tests/study-path.spec.ts` prova la finestra **Mostra**.

### 3. Test instabile Qd4/Qg4: cause e correzione

- **Cause trovate:**
  - nella posizione Qd4 e Qg4 valgono quasi uguale (circa +10) e minacciano entrambe Qxg7#;
  - Stockfish gira con `Threads=2`, che non è deterministico;
  - la tabella hash resta fra una ricerca e l'altra, quindi l'esito dipende dall'ordine delle prove.
- **Correzione:** la prova accetta Qd4 o Qg4 e continua a verificare il tipo di mossa. Il motore non è cambiato:
  renderlo riproducibile (un solo thread e hash svuotata a ogni ricerca) rallenterebbe le analisi. Questa scelta
  resta aperta.

### 4. Mosse del pezzo in Rivedi

- **Cosa:** in Rivedi un clic su un pezzo di chi muove mostra, su ogni casa raggiungibile, la probabilità che Maia
  scelga quella mossa. Il colore viene dal giudizio di Stockfish:
  - verde: la mossa migliore;
  - grigio: buona;
  - arancio: imprecisione, da 5 punti di punteggio atteso persi;
  - rosso: errore, da 10 punti.

  Il bordo blu segna la prima scelta di Maia. La funzione si spegne con l'interruttore «Mosse del pezzo».
- **Dove:**
  - `backend/piece_moves.py`: `POST /api/review/piece-moves`, una sola ricerca MultiPV con `Evaluator.rank`;
  - `web/src/pieceOdds.ts`;
  - `Board.tsx`, modalità `inspect`.
- **Perché:** l'idea viene da una schermata in stile Maia. Mostra insieme la mossa naturale e il suo costo.
- **Prove:** `tests/test_piece_moves.py` (Qxg2 è un errore; 422 su una casa senza un pezzo che può muovere) e
  `web/tests/piece-odds.spec.ts`.
- **Correzione lungo la strada:** l'etichetta «Mosse del pezzo · Maia e Stockfish» andava a capo e faceva fallire
  `move-review.spec.ts`; è stata accorciata.
- **Scheda:** [mosse-del-pezzo.md](mosse-del-pezzo.md).

### 5. Nome dell'apertura e uscita dalla teoria

- **Cosa:**
  - il catalogo `lichess-org/chess-openings` (CC0), fissato al commit `712a58b`, è salvato in
    `backend/data/openings.tsv` da `scripts/build_openings.py`;
  - `backend/openings.py` confronta le posizioni, non le sequenze di mosse, così riconosce le trasposizioni;
  - il nome compare nella lista Partite, in Rivedi e in Gioca, dove segue la posizione mostrata, e nel PGN
    esportato (intestazioni `ECO` e `Opening`);
  - le mosse di teoria sono in corsivo grigio.
- **Decisione:** il catalogo dà un nome solo ad alcune posizioni; per esempio 4. Ba4 Cf6 nella Spagnola non ne ha
  uno. Contare la teoria solo fino all'ultimo nome avrebbe anticipato l'uscita. Per questo il file contiene anche le
  4.117 posizioni intermedie delle linee con nome: la teoria finisce all'ultima posizione della partita che compare
  nel catalogo.
- **Correzioni lungo la strada:**
  - un nome lungo tagliava «fuori teoria dopo…» in Gioca: ora sta su una seconda riga;
  - il pulsante in Rivedi era troppo alto: ora è una pillola compatta.
- **Prove:**
  - `tests/test_openings.py` copre i nomi, la teoria che continua dopo 4…Cf6, la trasposizione 1. Cf3 Cc6 2. e4 e5
    3. Ab5 e le partite senza nome;
  - lista, partita e PGN, dove valgono le intestazioni importate;
  - `web/tests/openings.spec.ts` prova Partite, Rivedi e Gioca.
- **Scheda:** [aperture.md](aperture.md).

### 6. Il tuo repertorio e i drill dalla fine della teoria

- **Cosa:**
  - In Progressi, **Il tuo repertorio** (`GET /api/openings/repertoire`, `openings.repertoire`) raggruppa le
    partite per famiglia d'apertura e colore. Per ognuna mostra:
    - partite e punteggio;
    - la quota di decisioni senza perdite nelle 20 semimosse dopo la teoria;
    - dopo quante mosse arriva in media il primo errore.

    Un'apertura è «da curare» se ha almeno 3 partite e un punteggio sotto il 40%, oppure una quota dopo la teoria
    di 20 punti sotto la media del giocatore.
  - Nei Drill, `opening:<id partita>` riparte dall'ultima posizione di teoria; il catalogo dei drill ne propone
    fino a tre.
- **Perché:** il nome dell'apertura serve se dice dove si perde. L'uscita dalla teoria è il punto in cui finisce
  la memoria e comincia il gioco.
- **Verifica sui dati locali:** su una copia del database locale, non su quello di produzione, sono uscite 16
  famiglie; Philidor, Petrov e Queen's Pawn sono risultate da curare.
- **Prove:** `tests/test_openings.py` (raggruppamento, giudizio, posizione d'uscita, endpoint, drill) e
  `web/tests/openings.spec.ts` (il pannello e «Allena da lì»).

### 7. Varietà d'apertura di Maia e nuova regola

- **Misura:** `scripts/measure_opening_variety.py` fa giocare Maia contro sé stessa con gli stessi semi in ogni
  modalità e conta le famiglie d'apertura nelle prime 16 semimosse. Su 300 partite per livello, con la regola di
  allora (temperatura 1 e top-p 0,9 fino alla mossa 8):

  | Livello | Completa | Bilanciata / Solida | Tutte le mosse fino alla mossa 8 |
  |---|---|---|---|
  | 1100 | 55 | 36 | 55 |
  | 1500 | 54 | 42 | 54 |
  | 1900 | 62 | 46 | 62 |

  Il taglio dell'ultimo 10% delle mosse in apertura perdeva da un quinto a un terzo delle famiglie.
- **Decisione dell'utente:** adottare la regola di Mobile Maia. Bilanciata e Solida usano l'intera distribuzione di
  Maia (temperatura 1, top-p 1) fino alla mossa 5; poi vale la regola della modalità. Il valore viene da
  `OPENING_MOVES` e `OPENING` in `backend/maia.py`.
- **Misura della regola nuova** (1500, 300 partite): Completa, Bilanciata e Solida arrivano tutte a 54 famiglie,
  contro le 42 di Bilanciata e Solida con la regola precedente.
- **Prove:** `tests/test_maia.py`. Fino alla mossa 5 anche la mossa più rara (g4, 5%) è possibile; dalla 6 vale il
  taglio della modalità.
- **Schede:** [verifica-maia.md](verifica-maia.md) e [aperture.md](aperture.md).

### 8. Mosse candidate come indizio (idea 4 del paper)

- **Cosa:** `diagnosis.candidates`. L'indizio nasconde la soluzione fra una o due mosse sbagliate da considerare,
  prese in quest'ordine:
  1. la mossa che tenta;
  2. le quattro migliori di Stockfish;
  3. le sei più probabili di Maia.

  Ognuna deve perdere almeno 10 punti di punteggio atteso rispetto alla soluzione, misurati in una sola ricerca. Le
  mosse sono in ordine alfabetico, perché la posizione nell'elenco non dica nulla. Vale nei Puzzle (in
  `exercises.solution`) e nei Problemi.
- **Correzioni lungo la strada:**
  - avevo scritto una prova con una posizione illegale, con il re nero già sotto scacco, e Stockfish si chiudeva;
  - un'altra prova si aspettava candidate da Stockfish in una posizione dove tutte le sue mosse vincono. Giustamente
    il risultato è «nessuna candidata», e la prova ora lo verifica.
- **Prove:** `tests/test_diagnosis.py` e `web/tests/study-path.spec.ts`, dove il livello si inserisce prima di
  «Dove guardare».

### 9. Motivo solo quando conta (idea 5 del paper)

- **Cosa:** `explain.UNIQUE` = 0,05. Nelle spiegazioni di Rivedi la mossa migliore è presentata come «il colpo»
  («Con Rxa8+ vincevi una torre») solo se stacca di almeno 5 punti di punteggio atteso le altre scelte di Stockfish
  (`stockfishCandidates`), esclusa la mossa giocata. Altrimenti il testo dice «Quasi altrettanto buona era …: non
  c'era un solo colpo da trovare». `insights.VERSION` è passato a 7, così le spiegazioni salvate si ricalcolano
  alla lettura.
- **Perché:** quando più mosse vanno bene, indicarne una come «la» soluzione insegna una cosa falsa.
- **Prove:** `tests/test_explain.py`. Si controllano tre casi: una rivale vicina, una lontana e la mossa giocata,
  che non conta mai come rivale.

### 10. Motivo tattico nei Puzzle delle tue partite

- **Cosa:** `diagnosis.motif`. Nei Puzzle delle tue partite la soluzione è la risposta all'ultima mossa
  dell'avversario. Per questo `explain.refutation`, la stessa verifica delle spiegazioni degli errori, la legge dal
  lato dell'avversario. Riconosce sei temi Lichess:
  - forchetta;
  - inchiodatura;
  - infilata;
  - attacco di scoperta;
  - pezzo intrappolato;
  - pezzo indifeso.

  La linea deve vincere almeno 2 punti di materiale. Il motivo diventa un indizio «Motivo», come nei Problemi, e
  una chiave `theme:<tema>` delle lacune ricorrenti. Gli esercizi già classificati lo ricevono alla lettura
  successiva, oppure in background, senza nuove ricerche di Stockfish.
- **Correzione lungo la strada:** nella prima posizione di prova Stockfish preferiva Rxa1+, perché la torre era
  davvero indifesa, e il riconoscimento rispondeva correttamente «pezzo indifeso». La prova ora usa una posizione
  dove c'è solo la forchetta.
- **Prove:** `tests/test_diagnosis.py` copre `motif`, l'indizio via API e la chiave delle lacune.
- **Limite:** deviazione, adescamento e pezzo sovraccarico non sono riconosciuti.

### 11. Visualizzazione (idea 3 del paper, prima versione)

- **Cosa:** la nuova sezione **Visualizza** (`backend/visualization.py`, `web/src/Visualization.tsx`) mostra:
  - una posizione di una tua partita dopo la 16ª semimossa;
  - le mosse successive, scritte ma non giocate sulla scacchiera;
  - una domanda esatta sulla posizione finale.

  Le domande possibili sono:
  - quale pezzo c'è in una casa;
  - quanti pezzi attaccano un pezzo;
  - quante catture legali ci sono;
  - se il re è sotto scacco;
  - se è matto;
  - quale mossa è legale.

  La risposta resta sul server finché il giocatore non sceglie. La linea parte da 2 semimosse: cresce di una dopo
  3 risposte giuste di fila e cala di una dopo un errore, fra 1 e 8.
- **Correzioni lungo la strada:**
  - nella domanda «quale mossa è legale» la risposta giusta era in una notazione diversa dalle altre: ora tutte
    usano `Re1-d1`;
  - il plurale «bianci» è diventato «bianchi».
- **Prove:**
  - `tests/test_visualization.py`: la regola della lunghezza, 300 domande generate e verificate una per una contro
    la scacchiera, l'API (409 senza partite, risposta unica);
  - `web/tests/visualization.spec.ts`.
- **Limite:** i risultati non alimentano ancora le lacune ricorrenti.
- **Scheda:** [visualizzazione.md](visualizzazione.md).

### 12. Titoli di «Gioca da qui» senza «Da Da»

- **Segnalazione:** una scheda Puzzle mostrava «Da Da Allenamento con Maia 600 · 2. · 20.».
- **Causa:** ogni «Gioca da qui» aggiungeva «Da … · mossa» al titolo intero della partita di partenza, che poteva
  essere già nata allo stesso modo.
- **Correzione:** il titolo cita la partita di partenza con il suo numero: «Dalla partita #35, mossa 20 del Nero» e
  «Puzzle dalla partita #35, mossa 20 del Nero». Se il numero manca, al suo posto c'è il titolo tra virgolette.
- **Prove:** `web/tests/play-from.spec.ts` e `web/tests/puzzle-flow.spec.ts`.
- **Non fatto:** i titoli già salvati restano com'erano. La partita non registra da quale partita è nata, quindi non
  si possono ricostruire; e ogni modifica ai dati di produzione richiede l'autorizzazione esplicita dell'utente.

### 13. «Mostra» sulla variante di riferimento

- **Cosa:** accanto alla «Variante di riferimento» dei Puzzle chiusi e del giudizio di posizione nell'Allenamento di
  oggi c'è **Mostra**. Apre la stessa finestra con la scacchiera animata usata per la mossa che tenta (`ShowLine`).
- **Prove:** `web/tests/puzzle-flow.spec.ts`. La finestra si apre, la donna arriva in g7 e la finestra si chiude con
  Esc.

## Prove eseguite

| Suite | Comando | Esito |
|---|---|---|
| Backend completa | `.venv/bin/python -m pytest tests -q` | 237 passate, ultimo giro dopo tutte le modifiche |
| Visualizzazione | `pytest tests/test_visualization.py` | 3 passate |
| Maia e avversari, dopo la nuova regola | `pytest tests/test_maia.py tests/test_opponents.py` | 34 passate |
| Playwright completa | `npx playwright test` | 104 passate, 5 fallite (vedi sotto) |
| Playwright, ripetute da sole | i 5 file falliti più `play-from`, `puzzle-flow` e `visualization` | 18 su 18 passate |

Le 5 prove fallite nel giro completo erano:
- `evaluation-chart`;
- `pgn-export`;
- `training-plan`;
- `undo-rating`;
- `puzzle-flow`.

Tutti questi file sono nell'elenco delle prove già note come instabili in `CLAUDE.md`. Durante quel giro giravano
anche la misura su Maia, che occupava la CPU, e una ricompilazione dell'interfaccia. Eseguite da sole sono passate
tutte.

La suite Playwright completa non è stata rifatta dopo le ultime modifiche (regola d'apertura, titoli, **Mostra**
sulla variante di riferimento). Sono state eseguite solo le prove dei file toccati, tutte passate.

## Note per il commit

- Nell'albero ci sono anche modifiche che non fanno parte di questo lavoro e vanno escluse:
  - `experiments/human-policy/*`;
  - `docs/human-policy.md`.
- `tests/test_review_loss.py` ha solo una riga vuota in più in fondo: resta fuori dal commit.
- Documentazione aggiornata:
  - `README.md` e `CLAUDE.md` (il comando `scripts/build_openings.py`);
  - [aperture.md](aperture.md), [visualizzazione.md](visualizzazione.md) e [mosse-del-pezzo.md](mosse-del-pezzo.md),
    nuove;
  - [diagnosi-errori.md](diagnosi-errori.md), [problemi.md](problemi.md), [lacune-studio.md](lacune-studio.md),
    [spiegazione-errori.md](spiegazione-errori.md), [drill-puzzle-personalizzati.md](drill-puzzle-personalizzati.md),
    [verifica-maia.md](verifica-maia.md) e [PLAN-indizi-puzzle.md](PLAN-indizi-puzzle.md).

## Aperto

- Verificare le soglie delle lacune sui dati reali: serve leggere il database di produzione, con l'autorizzazione
  dell'utente.
- Collegare i risultati della visualizzazione alle lacune ricorrenti (lacuna di calcolo o lacuna tattica).
- Decidere se rendere Stockfish riproducibile (un thread, hash svuotata), al prezzo di analisi più lente.
- Decidere se «Causa da approfondire» (`unclear`) debba seguire lo stesso criterio delle altre cause.
