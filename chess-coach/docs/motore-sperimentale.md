# Motore sperimentale in Gioca

Data: 23 ottobre 2026. Descrive come SparringMate usa, in **Gioca**, il modello addestrato in
`experiments/human-policy` come alternativa a Maia, per confrontarli giocando.

## Perimetro

- Solo **Gioca**, sul PC e sull'istanza pubblica. Puzzle, Blunder prevention, tutor, stima del profilo e analisi restano
  invariati: Stockfish valuta la partita come sempre e le previsioni Maia nell'analisi restano
  etichettate «Maia».
- «Gioca da qui» (Rivedi, Puzzle, Blunder prevention) avvia sempre una partita contro Maia.
- In produzione `make deploy` copia solo ciò che serve al servizio: il codice, i `best.pt` accettati in `runs/monthly/`
  con la loro `verification.json` e `data/cycles/ledger.json` (circa 20 MB; niente dati di addestramento né
  `.venv`). Sul server crea un ambiente solo CPU da `requirements-serve.txt`, avvia
  `sparringmate-experimental.service` (checkpoint `latest`, porta 8044) e, se manca, aggiunge
  `SPARRINGMATE_EXPERIMENTAL_ENGINE=http://127.0.0.1:8044` al `.env`. Togliendo la riga il selettore scompare.

## Componenti

| Parte | File | Ruolo |
|---|---|---|
| Servizio | `experiments/human-policy/serve.py` | Carica un checkpoint una volta, ascolta solo su 127.0.0.1 |
| Adattatore | `backend/opponents.py` | Stato del servizio, verifica delle risposte, estrazione della mossa |
| API | `backend/main.py` | `GET /api/opponents`, `POST /api/games` con `engine`, `POST /api/games/{id}/policy-move` |
| Interfaccia | `web/src/OpponentChoice.tsx` | Selettore, stato del servizio, avviso di calibrazione |

Il servizio usa l'ambiente Python del laboratorio (PyTorch), separato da quello dell'app; l'app
comunica con lui solo via HTTP.

### Contratto del servizio

- `GET /health` → `engine`, `version`, `step`, `ratingBounds`, `ratingSystem`, `calibrated: false`.
  La versione è `<cartella della run>-step<passo>-<prime 12 cifre dello SHA256 dei pesi>`: un altro
  checkpoint è sempre un'altra versione.
- `POST /predict` con `fen`, `elo` e `context` (`gameId`, `ply`, `playerColor`) → `engine`, `version` e
  **tutte** le mosse legali con la loro probabilità. Nessun troncamento alle prime cinque.

## Attivazione reversibile

`SPARRINGMATE_EXPERIMENTAL_ENGINE=http://127.0.0.1:8044`, nell'ambiente o in `.env`. Il valore viene
letto a ogni richiesta: si attiva e si disattiva senza riavviare l'app. Senza l'opzione `GET /api/opponents`
risponde `{"enabled": false}`, il selettore non compare e la creazione di una partita sperimentale
risponde 409. Con l'opzione attiva ma il servizio spento, il selettore mostra «Servizio non disponibile»
e il pulsante per iniziare resta disattivato solo per lo Sperimentale.

## Una partita

1. **Avvio.** `POST /api/games` con `engine: "experimental"` interroga `/health` (2 s al massimo), controlla
   che il livello rientri nei rating del training (oggi 600–2596; il cursore si limita a 600–2500) e salva
   nella partita `engine`, `engine_version` e `move_selection`. Per Maia il modello lo registra il server
   (`MODEL_VERSION` in `backend/maia.py`: `maia3_simplified.onnx@official-browser-2026-09-23`).
2. **Risposta.** Dopo la stessa pausa di presentazione usata per Maia (1,2–3,2 s, prima della richiesta:
   un turno annullato non registra nulla), il browser chiama `policy-move`. Se la partita è palesemente
   persa per il motore (vedi «Abbandonare una partita» nel README), il server registra una proposta di
   abbandono, che il giocatore accetta o rifiuta, senza interrogare il servizio. Altrimenti chiede la
   distribuzione al servizio (10 s al massimo) e la scarta se la versione non è quella fissata all'avvio,
   se le mosse non coincidono esattamente con quelle legali o se le probabilità non sono finite, non
   negative e con somma 1 (±0,001).
3. **Scelta della mossa.** Estrazione casuale secondo le probabilità del modello, sull'intera
   distribuzione (`sample-full-distribution`, la modalità predefinita di Maia; le altre modalità di Maia, vedi
   [verifica-maia.md](verifica-maia.md), non si applicano allo Sperimentale). Il server genera un seme
   a 63 bit; le mosse sono ordinate per UCI prima dell'estrazione, quindi seme e distribuzione bastano a
   ripetere la scelta.
4. **Registrazione.** `move_choices` ha una voce per semimossa: per le risposte sperimentali motore,
   versione, modalità, seme e probabilità della mossa scelta; per Maia motore, versione e modalità
   (l'estrazione avviene nel browser e il seme non è registrato). Annullare una mossa taglia anche queste
   voci; la copia conservata prima dell'annullamento le mantiene.
5. **Errori.** Servizio spento, timeout, risposta non valida o versione cambiata: 503 con un messaggio
   in italiano, nessuna mossa registrata, pulsante **Riprova**. Non c'è mai un passaggio automatico a Maia.
   Il browser non può inviare mosse dell'avversario per una partita sperimentale (409).

## Storico e PGN

`GET /api/games` e la partita riportano `engine`, `engineLabel` («Maia», «Sperimentale») ed
`engineVersion`. L'archivio mostra «Contro Sperimentale (versione)». Il PGN chiama l'avversario
«Sperimentale 1300» o «Maia 1300» e aggiunge `OpponentEngine`, `OpponentEngineVersion`, `OpponentElo` e
`MoveSelection`. Le partite create prima di questa versione non hanno motore registrato e restano
partite contro Maia.

## Limiti

- Il livello Elo del modello sperimentale non è calibrato: è il rating Lichess rapid usato in training,
  non una forza di gioco verificata. L'interfaccia lo dice accanto al selettore.
- Il modello vede solo la posizione: niente storia delle mosse, orologio o rating dell'avversario.
- Il confronto con Maia si fa giocando; non esiste ancora una misura automatica di somiglianza.

## Verifiche

```bash
.venv/bin/python -m pytest tests/test_opponents.py -q
cd experiments/human-policy && .venv/bin/python -m pytest -q test_serve.py
cd web && npm run build && npx playwright test tests/experimental-engine.spec.ts
```

Le prove backend usano `tests/fixtures/fake_policy_service.py`, che ha lo stesso contratto HTTP e
simula guasti (servizio spento, mosse illegali o mancanti, probabilità errate, versione cambiata). Coprono
anche promozione, fine partita, annullamento, PGN, storico e la riproducibilità del seme. La suite
Playwright avvia lo stesso servizio finto sulla porta 8012. `test_serve.py` controlla il servizio vero
con un checkpoint generato al momento. Il 23 ottobre 2026 una partita completa contro il checkpoint
`2026-09-step10000-a5408f29595d` ha richiesto circa 0,05 s per mossa su CPU, con promozione e patta in un
finale.


## Correzione di avvio e selezione — 24 ottobre 2026

`make experimental` e `serve.py` usano per default `latest`: il campo
`active_month` nel registro locale, non il mese cronologicamente maggiore.
Si verificano stato completato, percorso nel laboratorio, SHA256 dei pesi,
accettazione e SHA256 del rapporto. Se la verifica fallisce l'avvio si ferma;
non viene caricato silenziosamente un vecchio modello. `CHECKPOINT=<percorso>`
resta disponibile per un confronto esplicito. Nessun aggiornamento dei pesi
durante il funzionamento del servizio.

Gioca mostra il motore della partita corrente accanto alla scacchiera e la
versione nei dettagli. Il selettore è dichiaratamente quello della prossima
partita; una differenza genera un messaggio esplicito. La preferenza è salvata
nel browser e non viene sostituita se il servizio non è disponibile. Una nuova
versione del servizio con range più stretto aggiorna il livello selezionato
entro i limiti ammessi. Lo storico e le partite già aperte restano coerenti
con il motore/versione fissati all'inizio.

Verifica: test del resolver in `test_serve.py`, test backend `test_opponents.py`,
Playwright `experimental-engine.spec.ts` (chiamata policy-move, persistenza,
differenza tra motore attuale e prossimo, cambio versione e indisponibilità).
