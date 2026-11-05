# Ragionamento mossa per mossa

La sezione **Mossa per mossa** è una raccolta di lezioni guidate tratte da partite commentate in un libro:
*Logical Chess: Move by Move* di Irving Chernev (Batsford, edizione in notazione algebrica). Comprende 10 lezioni su
singole posizioni e 5 partite da seguire per intero, **separate** dagli esercizi generati dalle tue partite: non
entrano nella coda di Allenamento di oggi e hanno un ripasso proprio. Il formato è stato provato sulla prima partita e
sulle lezioni, poi esteso a blocchi di partite intere.

## Come funziona una lezione

- Vedi la posizione, la sequenza di mosse che la precede (`1.e4 e5 2.Nf3 …`), chi muove e una domanda in italiano
  sull'obiettivo: sviluppare con una minaccia, difendere sviluppando, prevenire una minaccia, ritirare un pezzo
  attaccato, attaccare su una colonna, sostenere una catena di pedoni, sfruttare una casa debole, trovare un piano.
- Tre **indizi** progressivi, uno alla volta su richiesta.
- Giochi la mossa sulla scacchiera. L'esito dipende dalla **lezione**, non dal motore:
  - **Partita**: la mossa giocata nella partita del libro;
  - **Valida**: un'alternativa coerente con l'obiettivo della lezione (per esempio 3.Bb5 accanto a 3.Bc4);
  - **Sensata**: una mossa ragionevole che però risponde a un'altra domanda (2…Nf6 non difende e5);
  - **Debole**: una mossa che il libro o l'analisi sconsigliano, con il motivo;
  - **Fuori lista**: qualsiasi altra mossa legale, giudicata soltanto dal motore.

  Solo *Partita* e *Valida* contano come risposta giusta.
- Dopo la mossa compaiono due pannelli **distinti**:
  - **L'idea**: la mossa della partita, una spiegazione originale e, in breve, il ragionamento che il libro propone,
    con partita e pagina;
  - **Stockfish**: la valutazione della tua mossa (punteggio oggettivo, come in tutta l’app: positivo se è avanti il
    Bianco, negativo se è avanti il Nero), la migliore per il motore, le
    prime linee e una tabella con tutte le mosse previste dalla lezione, ciascuna con giudizio, nota e valutazione.
    Il giudizio del motore usa le regole comuni del progetto (`review_loss`, franchigia di ±600, «Matto mancato»; vedi
    [giudizio-mosse.md](giudizio-mosse.md)). Quando libro e motore non coincidono la lezione lo dice: in
    von Scheve–Teichmann il libro loda 4…Qe7, Stockfish preferisce 4…Nf6 (circa 0,8 pedoni di differenza).
- Sulla scacchiera la mossa della partita viene giocata; le frecce mostrano la tua mossa e la prima scelta del motore,
  quando sono diverse da quella della partita.
- Dopo ogni lezione, **Continua la partita →** apre «Segui la partita» nella stessa partita, alla mossa successiva
  da indovinare, senza ripartire dalla prima mossa.

## Segui la partita

Il libro commenta ogni mossa di partite intere: questa modalità le ripercorre dall'inizio alla fine. Si gioca sempre
dalla parte di chi vince, perché molte mosse del perdente sono proprio quelle che il libro critica e indovinarle non
insegnerebbe nulla.

| Partita | Colore | Mosse da indovinare | Lezioni collegate | Tema |
|---|---|---|---|---|
| 1 · von Scheve–Teichmann, Berlino 1907 | Nero | 17 | lc-02, lc-04, lc-05 | Sviluppo rapido e attacco contro un arrocco indebolito |
| 2 · Liubarski–Soultanbeieff, Liegi 1928 | Nero | 16 | lc-06, lc-07 | Pedoni all'assalto contro h3 e colonna g aperta |
| 10 · Tarrasch–Eckart, Norimberga 1889 | Bianco | 17 | lc-08 | La catena d4–e5 e il sacrificio in g6 |
| 14 · Tarrasch–Mieses, Berlino 1916 | Bianco | 20 | lc-09 | La coppia degli alfieri e l'inchiodatura del cavallo f6 |
| 24 · Capablanca–Mattison, Karlsbad 1929 | Bianco | 20 | lc-10 | Sviluppo completo, poi le combinazioni |

- Indovini ogni mossa del tuo colore. Quelle dell'avversario si giocano da sole, ciascuna con una nota e il
  giudizio di Stockfish (per esempio, nella partita 1, 12.Nd2: errore, meglio Qd3 o Qf3).
- Per ogni mossa: una domanda e due indizi; alternative previste con lo stesso giudizio delle lezioni (*Partita*,
  *Valida*, *Sensata*, *Debole*, *Fuori lista*). Le mosse che sono anche lezioni (tabella sopra) usano la domanda e i
  tre indizi della lezione.
- Le partite che non finiscono con il matto sulla scacchiera (abbandono) hanno una nota finale con la minaccia che
  ha deciso.
- Dopo la risposta la scacchiera mostra la mossa della partita, che si gioca comunque: la partita prosegue sempre.
  Gli stessi due pannelli delle lezioni: l'idea (nota originale e, in breve, l'argomento del libro) e Stockfish
  (la tua mossa, quella della partita, la migliore).
- Si parte da 1.e4 oppure da una lezione con **Continua la partita →**: in quel caso il punteggio conta solo le mosse
  da lì alla fine, e il migliore resta quello dei percorsi completi.
- **Punteggio**: conta solo la prima risposta a ogni mossa; *trovata* se è la mossa della partita o un'alternativa
  valida, *senza indizi* se non ne hai chiesti. **Riprova questa mossa** è pratica. Un percorso interrotto si
  riprende dall'elenco; **Ricomincia** ne apre uno nuovo. I percorsi non toccano il ripasso delle lezioni.

Dove libro e motore non coincidono, la mossa lo dice. Nella partita 1 (analisi verificata anche a profondità 30 circa):

- **8…Ba7**: il libro loda il Nero che non prende a5, temendo 9.Rxa5 Bxa5 10.Qa4+. Per Stockfish 8…Nxa5 vinceva un
  pedone: dopo 10.Qa4+ b5! 11.Qxa5 bxc4 il Nero sta meglio. Ha ragione il libro su 8…Bxa5, che perde un pezzo (9.d5).
- **13.gxh3**: per il libro è obbligata; Stockfish preferisce 13.Qf3, che perde comunque un pedone.
- **17…Bxf2**, l'ultima mossa: il libro dice che non c'era scampo, ma 18.Bxf7+! Ke7 19.Bg5+ Kf8 20.Bf4! porta la
  posizione all'incirca in parità. Il Bianco abbandonò senza vederla. Per Stockfish era decisiva 17…Qh3+, accettata
  come *Valida*.

Nelle altre partite:

- **5…Qe7** (partita 2): il libro la loda perché difende e5 sviluppando; per Stockfish 5…exd4 e 5…d6 erano un po'
  più precise (circa mezzo pedone).
- **16.Qh3** (partita 14): per il libro è la mossa vincente; Stockfish preferisce 16.Qg3, di circa un pedone, ma il
  Bianco resta in netto vantaggio in entrambi i casi.
- Le mosse dell'avversario hanno la nota nel testo e il giudizio del motore accanto: per esempio 12.hxg4 nella
  partita 2, quasi obbligata per il libro, mentre per Stockfish 12.g3 o 12.a4 tenevano la parità.

Tutte le posizioni delle partite sono state confrontate con i diagrammi del libro: per la partita 1 i sei diagrammi
(dopo 7.a4, 9.h3, 10…Nxe5, 11…Qxe5, 15…Ng4, 17.Kh1), per le partite 2, 10, 14 e 24 tutti quelli che la pagina
riporta, da 4 a 12 per partita.

## Ripasso

Stessi intervalli del piano di allenamento (`training_schedule.INTERVAL_HOURS`: 4 ore, 1, 3, 7, 14 giorni…). Conta
solo la risposta data quando la lezione è **nuova** o **in scadenza**:

- giusta e **senza indizi**: la lezione passa al passo successivo;
- sbagliata, o giusta con almeno un indizio: torna al passo 0 e si ripresenta dopo 4 ore.

Le risposte date prima della scadenza (anche con **Riprova**) sono pratica e non cambiano il calendario. L'elenco
mostra per ogni lezione *Nuova*, *Da ripassare*, *Da rifare* o *Ripasso N* con la data; **Inizia** propone prima i
ripassi in scadenza, poi le lezioni nuove nell'ordine del libro, che parte dalle idee più semplici.

## Il campione

| Lezione | Partita (n. nel libro) | Pagina | Mossa | Tema |
|---|---|---|---|---|
| lc-01 | von Scheve–Teichmann (1) | 12 | 2.Nf3 | Sviluppo con minaccia |
| lc-02 | von Scheve–Teichmann (1) | 13 | 2…Nc6 | Difendere sviluppando |
| lc-03 | von Scheve–Teichmann (1) | 13 | 3.Bc4 | Sviluppo dell'alfiere |
| lc-04 | von Scheve–Teichmann (1) | 13 | 3…Bc5 | La casa più efficace |
| lc-05 | von Scheve–Teichmann (1) | 14 | 4…Qe7 | Prevenire la minaccia (libro ≠ motore) |
| lc-06 | Liubarski–Soultanbeieff (2) | 21 | 7…Nb8 | Ritirata del cavallo |
| lc-07 | Liubarski–Soultanbeieff (2) | 22 | 12…Rg8 | Attacco sulla colonna aperta |
| lc-08 | Tarrasch–Eckart (10) | 62 | 6.c3 | Sostenere la catena di pedoni |
| lc-09 | Tarrasch–Mieses (14) | 83 | 11.Nc6 | Sfruttare una casa debole |
| lc-10 | Capablanca–Mattison (24) | 163 | 12.Rab1 | Un piano con le torri |

## Dati e verifiche

- `backend/data/logical_chess.json`: fonte, partite, lezioni (mosse dalla posizione iniziale in SAN, FEN, domanda,
  indizi, mosse previste con giudizio e nota, spiegazione, idea del libro, nota sul disaccordo) e il blocco `engine`.
  Testi originali: il libro è citato solo con partita e pagina.
- `scripts/build_lessons.py [--depth 22]`: rigioca ogni lezione e controlla FEN, legalità e SAN canonica delle mosse
  previste e che la mossa della partita sia una sola; poi Stockfish, a profondità fissa, scrive le prime 5 linee e la
  valutazione di ogni mossa prevista. Va rieseguito dopo ogni modifica alle lezioni (circa un minuto).
- `backend/lessons.py`, `validate`: gli stessi controlli, eseguiti anche da `tests/test_lessons.py`.
- Una mossa fuori lista viene valutata dal vivo (`LIVE_NODES`, segnata come «analisi rapida»).
- `walks` nello stesso file: le partite di «Segui la partita», con colore, risultato, nota finale e, per ogni mossa,
  SAN, pagina, nota; per le mosse da indovinare domanda, due indizi, alternative, idea del libro, nota sul disaccordo,
  oppure il riferimento a una lezione (`lesson`), che deve avere la stessa posizione e la stessa mossa.
  `scripts/build_lessons.py` vi scrive l'analisi di ogni mossa: profondità 20, al massimo 8 secondi per ricerca
  (vicino a un matto Stockfish può non raggiungere la profondità). `--only-walks` salta le lezioni; `--walk <id>`
  (ripetibile) analizza solo le partite indicate e lascia invariata l'analisi delle altre: circa un quarto d'ora a partita. `validate_walks` controlla legalità, SAN canonica,
  coerenza con le lezioni e analisi.

## Come sono state ricostruite le posizioni

Il PDF è una scansione con testo OCR in cui le figurine dei pezzi sono lette male (`lDf3`, `tt:Jf3`, `'ii'e7`).
`scripts/extract_book_games.py book.pdf cartella` (richiede PyMuPDF, fuori dai requisiti del progetto) estrae il
testo per pagina e ricostruisce la linea principale di ogni partita: per ogni riga che inizia con il numero di mossa
atteso, python-chess sceglie l'unica mossa legale compatibile con casa d'arrivo, tipo di pezzo e cattura; le forme
OCR delle figurine si imparano dalle mosse non ambigue. Le mosse che restano ambigue o illeggibili sono elencate
come `flags`, e la partita si ferma lì; le etichette delle traverse dei diagrammi (`5`, `4 3`) vengono ignorate.

Le mosse che l'OCR non risolve si leggono a mano nel testo (`book.txt`) e si passano come terzo argomento, un file
JSON per partita: `{"10": {"10...": "Nd8", "14": "Bxg6"}}` (mossa 14 del Bianco, mossa 10 del Nero). Una mossa
corretta viene giocata quando tocca a lei, anche se l'OCR non ha una riga per quella mossa.

Il risultato è una bozza. Ogni posizione è stata confrontata con i diagrammi del libro (pezzi, turno, arrocchi) e il
commento è stato riletto. Le correzioni servite finora: in Tarrasch–Eckart 10…Nd8 (lo script aveva scelto 10…Rd8,
ma il testo dice «protegge il pedone e6») e 12…Nxf6 (non Rxf6), più 14.Bxg6 e 15.Qxg6+ illeggibili; in
Tarrasch–Mieses 18.Qh6 (l'OCR legge «b6») e 19.Re3; in Capablanca–Mattison 12…Qa3, 18…e5 e 19…Na6, mancanti nel
testo e lette sui diagrammi.

## Limiti e prossimi passi

- Cinque partite su 33. Le altre si aggiungono a blocchi di 4–5: ricostruzione con `scripts/extract_book_games.py`
  e `fixes.json`, confronto con tutti i diagrammi, testi originali, poi `scripts/build_lessons.py --only-walks --walk
  <id>`.
- Le alternative accettate sono scelte a mano: una mossa buona per il motore ma estranea all'idea resta «Sensata».
- Diritti: la prova è per uso personale con riferimenti al libro e testi originali. Per un rilascio pubblico vanno
  verificati i diritti su testo e diagrammi.

## API

- `GET /api/lessons`: percorso, fonte, lezioni con stato (`new`, `due`, `waiting`), passo e scadenza, `next`,
  conteggi e `intervalHours`.
- `GET /api/lessons/{id}`: posizione, mosse precedenti, domanda, indizi, mosse legali, partita con citazione e se la
  risposta conterà per il ripasso (`counts`). Non contiene la soluzione.
- `POST /api/lessons/{id}/answer` con `{"move": "d8e7", "hints": 1}`: posizione dopo la mossa della partita
  (`fenAfter`, `playedUci`), la partita da seguire che prosegue da lì (`walk`: id e mossa), esito, giudizio e nota, mossa della partita,
  spiegazione, idea del libro, mosse previste con valutazioni, analisi del motore e nuovo stato del ripasso. 422 per
  una mossa illegale, 404 per una lezione sconosciuta.
- `GET /api/lesson-walks`: partite da seguire, con percorso in corso, ultimo e migliore.
- `POST /api/lesson-walks/{id}/start`, facoltativo `{"ply": 9}` per partire da quella mossa: nuovo percorso; risponde con la prima mossa da indovinare: posizione, mosse
  precedenti, mosse dell'avversario appena giocate (nota e giudizio del motore), domanda, indizi. Senza soluzione.
- `GET /api/lesson-walks/{id}/runs/{run}[?ply=N]`: la mossa successiva del percorso, o quella indicata. 409 se il
  percorso è concluso e non si indica la mossa.
- `POST /api/lesson-walks/{id}/answer` con `{"run": …, "ply": 1, "move": "e7e5", "hints": 0}`: esito, mossa della
  partita, nota, analisi, posizione dopo la mossa, punteggio; all'ultima mossa anche risultato e nota finale. 422 per
  una mossa illegale o che non tocca al giocatore.
- Tabelle: `lesson_walk_runs` (percorsi: mossa di partenza `first_ply`, prossima mossa, risposte, trovate, senza indizi) e `lesson_walk_answers`.
- Tabelle: `lesson_progress` (passo, scadenza, tentativi) e `lesson_attempts` (ogni risposta, con indizi e se è
  contata).
