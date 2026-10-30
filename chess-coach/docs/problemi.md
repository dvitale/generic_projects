# Problemi da partite reali

Data: 18 ottobre 2026. Descrive la sezione **Problemi**, la provenienza dei dati e cosa misurano i rating.

## Perché “problemi”

In italiano “problema di scacchi” indicava in origine una composizione artistica (matto in due, studi). Le app usano la parola come traduzione di *puzzle*. Per i problemi tratti da partite il nome più preciso sarebbe “esercizio tattico”.

Nei puzzle di Lichess **chi sbaglia è l’avversario, non chi risolve**. Il campo `FEN` è la posizione prima della mossa dell’avversario. La posizione da mostrare si ottiene applicando la prima mossa di `Moves`, e la soluzione parte dalla seconda. Il generatore sceglie quella mossa quando le probabilità di vittoria del lato che risolve salgono molto. Il problema chiede quindi di punire l’errore.

I **Puzzle** di SparringMate seguono la logica opposta: nascono dalle *tue* decisioni sbagliate e chiedono la mossa che non avevi trovato.

## Da dove vengono

- **Fonte.** [database.lichess.org](https://database.lichess.org/#puzzles), CC0. Al 18 ottobre 2026 il file contiene 6.157.341 problemi, pesa 307 MB compresso (`lichess_db_puzzle.csv.zst`) ed è aggiornato al 2 ottobre 2026.
- **Colonne usate.** `PuzzleId`, `FEN`, `Moves` (UCI), `Rating`, `RatingDeviation`, `Popularity` (da −100 a 100), `NbPlays`, `Themes`, `GameUrl`, `OpeningTags`.
- **Generatore.** [lichess-puzzler](https://github.com/ornicar/lichess-puzzler), AGPL-3.0. Da `generator/generator.py`:
  - la valutazione deve arrivare ad almeno +2, con un salto di probabilità di vittoria superiore a 0,6;
  - sotto +4 chi muove deve essere sotto di materiale;
  - a ogni mossa di chi risolve, la migliore deve superare la seconda di oltre 0,7 in probabilità di vittoria;
  - i matti sono ammessi fino a 15 mosse;
  - le soluzioni da una sola mossa sono escluse, salvo i matti in uno;
  - l’analisi arriva fino a 25 milioni di nodi per posizione.

  SparringMate non include né riproduce quel codice: usa solo i problemi già pubblicati.

## Importazione

`make puzzles` esegue `scripts/import_lichess_puzzles.py`:

- **Lettura.** Scarica il file e lo decomprime in streaming con `zstandard`, senza salvarlo su disco.
- **Filtri.** Tiene i problemi con popolarità ≥ 80, almeno 200 tentativi e deviazione del rating ≤ 90. Pochi tentativi o una deviazione ampia significano una difficoltà poco affidabile.
- **Fasce.** Dieci: fino a 800, poi da 200 punti fino a 2200, 2200–2500, oltre 2500. Si possono richiedere fino a 3000 problemi per fascia (`PER_BAND`).
- **Arresto.** Si ferma quando tutte le fasce sono piene. Con i valori predefiniti legge circa 417.000 righe, impiega circa 5 secondi e scrive 7,1 MB.
- **Ordine del file.** Il CSV è ordinato per `PuzzleId`. Gli ID di Lichess sono stringhe casuali, quindi le prime righe non favoriscono rating, date o temi. Il campione verificato ha medie per fascia coerenti e temi vari.
- **Sostituzione atomica.** Scrive un file temporaneo e lo rinomina solo alla fine, così il server non legge mai un database a metà.
- **Server pubblico.** `make deploy` copia il file sul server se esiste in locale.

## Rating: tre grandezze diverse

| Grandezza | Cosa misura | In SparringMate |
|---|---|---|
| Rating del problema | Difficoltà per chi risolve: Lichess conta ogni tentativo come una partita Glicko-2 fra giocatore e problema | Determina le fasce |
| Elo dei giocatori della partita | Il livello di chi ha giocato la partita originale, non la difficoltà del problema | Non usato: assente dal CSV |
| Stima Maia | Probabilità che Maia, a un dato livello, giochi tutta la soluzione | Mostrata a fine problema |

I rating Lichess non sono Elo FIDE: una fascia va letta come rating dei problemi.

Il **rating personale** parte da 1200 e usa la formula Elo contro il rating del problema. Il fattore K vale 60 per i primi 10 problemi, 40 fino a 30, poi 24. Cambia una volta per problema: al primo errore, alla richiesta della soluzione o alla soluzione pulita. Gli errori successivi e il completamento dopo un errore non lo modificano. Saltare prima della prima mossa non lascia traccia. La fascia **Adattiva** sceglie entro 100 punti dal rating personale e propone prima i problemi non ancora visti.

La **stima Maia** moltiplica, per ciascuna mossa di chi risolve, la probabilità che Maia3 (con entrambi gli Elo uguali al livello) giochi la mossa della soluzione. È calcolata da Maia sul server ai livelli 800, 1100, 1400, 1700, 2000 e 2300. Misura quanto la soluzione sia “naturale” per un umano di quel livello, non quanto sia difficile calcolarla con calma. Non conta i matti alternativi accettati. Il metodo ha precedenti pubblicati: nella sfida FedCSIS 2025 sulla difficoltà dei puzzle, gli organizzatori fornivano probabilità di successo calcolate con Maia-2 e la soluzione vincitrice partiva da un Maia-2 riaddestrato. Prima di usare la stima come classificazione andrebbe confrontata con il rating Lichess su un campione.

## Verifica delle mosse

La verifica avviene sul server, mossa per mossa. Il browser riceve posizione, prima mossa dell’avversario e mosse legali. Soluzione, rating e temi arrivano solo a problema concluso. Come su Lichess, qualsiasi matto è accettato anche se diverso dalla mossa salvata. Una mossa sbagliata viene mostrata e poi annullata, e si può continuare a cercare.

A problema concluso, **↺ Riprova da capo** riparte dalla mossa dell’avversario. La soluzione è ormai nota al browser, che verifica le mosse da solo con la stessa regola (mossa salvata o qualsiasi matto) e gioca le risposte: nulla arriva al server, quindi il rating non cambia. Accanto, **Gioca da qui col Bianco/Nero** avvia una partita contro Maia, al livello selezionato in Gioca, dalla posizione dopo la mossa dell’avversario, col colore che deve risolvere; il titolo è «Problema ‹ID› · ‹mossa›».

## Verifiche ripetibili

```bash
.venv/bin/python -m pytest tests/test_problems.py -q
cd web && npm run build && npx playwright test tests/problems.spec.ts
```

I test usano `tests/fixtures/lichess-puzzles.csv`: 11 problemi reali, uno per fascia più un matto in uno. Le prove del browser importano la fixture nella cartella dati temporanea prima di avviare il server.
