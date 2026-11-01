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

## Prossimi passi

Nessuno in corso per le aperture.
