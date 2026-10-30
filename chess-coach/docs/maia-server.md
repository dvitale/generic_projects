# Maia sul server

Data: 29 ottobre 2026, aggiornata il 30 ottobre. `backend/maia.py` esegue sul server lo stesso Maia3 del sito ufficiale: stesso file ONNX, stessa codifica della posizione, stessa tabella delle mosse. Dal 30 ottobre 2026 è **l'unico Maia del sito**: le mosse in Gioca e nei Drill, la barra Maia, Suggerisci mossa, Rivedi, Puzzle, Problemi e la somiglianza con i profili Maia chiedono le previsioni al server. Il browser non scarica più modello, worker e runtime WebAssembly.

## Uso

```python
from backend.maia import maia
maia.available()                                   # modello e onnxruntime presenti?
maia.predict(fen, 1500, 1500)                      # come maia.predict() di web/src/engine/maia.ts
maia.predict_many([(fen, 800, 800), (fen, 2200, 2200)])   # a lotti di 32, risultati nello stesso ordine
```

Il risultato ha le chiavi dell'interfaccia: `moves` (UCI e probabilità, ordinate), `whiteExpectedScore`, `whiteOutcome`. Nelle posizioni senza mosse legali il modello non viene chiamato. La sessione si carica alla prima richiesta, non all'avvio del servizio. Le esecuzioni sono serializzate da un lock.

## API per l'interfaccia

`POST /api/maia/predict` con `{"positions": [{"fen", "selfElo", "opponentElo"}, …]}` (da 1 a 64 posizioni) risponde `{"predictions": [...]}` nello stesso ordine; ogni mossa ha anche `san`. Una FEN non valida dà 422, il modello assente 503. Come ogni `/api`, richiede il login.

- **Lotti:** `web/src/engine/maia.ts` raccoglie le richieste fatte nello stesso momento e le spedisce insieme; la somiglianza con i profili Maia chiede tutti i livelli di una decisione in una sola richiesta.
- **Cache:** le ultime 4.096 previsioni restano in memoria (`CACHE`), così scorrere avanti e indietro una partita non ricalcola le stesse posizioni.
- **Precedenza:** le richieste dell'interfaccia passano davanti ai calcoli di sfondo (per esempio la classificazione degli abbagli), che si fermano fra un lotto da 32 e l'altro. Al massimo si aspetta il lotto in corso, meno di un secondo.
- **Mosse di Maia in Gioca e nei Drill:** le sceglie il server con `POST /api/games/{id}/maia-move` (`version`, `revision` e, facoltativo, `elapsed_seconds`, il tempo di riflessione mostrato dalla pagina). Il server ricostruisce la posizione, chiede la previsione al livello della partita e sorteggia con `choose()`, applicando temperatura e top-p della modalità fissata all'avvio (`SELECTIONS`; Bilanciata e Solida più varie fino alla mossa 8). Il seme del sorteggio, la modalità, la versione del modello e la probabilità della mossa vanno in `move_choices`, come per lo Sperimentale. Se la posizione è persa da tre turni, al posto della mossa registra la proposta di abbandono. La pausa di 1,2–3,2 s prima della risposta la fa la pagina, prima della richiesta: un turno annullato non registra nulla.
- **Versione del modello:** la fissa il server alla creazione della partita (`MODEL_VERSION`), non più la pagina.
- **Nell'interfaccia** di Maia restano solo le richieste di previsione da mostrare (barra, frecce, confronti) e i nomi delle modalità. Anche la tabella delle mosse è passata al backend (`backend/data/all_moves_maia3.json`). Senza Maia nel browser non serve più l'intestazione `Cross-Origin-Embedder-Policy`, che il WebAssembly multithread richiedeva: è stata tolta.

## Modello

Il modello si legge da `models/maia3/maia3_simplified.onnx` (scaricato da `scripts/download_assets.py`, escluso da git, copiato da `make deploy`; fino al 30 ottobre stava in `web/public/maia3`), oppure da `MAIA_MODEL_PATH`. `MAIA_THREADS` limita i thread di calcolo (0, il predefinito, li usa tutti). `/api/health` riporta `maiaServer: disponibile | assente`.

Il primo uso è il filtro degli abbagli di Blunder prevention ([docs/blunder-prevention.md](blunder-prevention.md#abbagli-e-lacune)).

## Fedeltà al modello del browser ufficiale

`tests/fixtures/maia_reference.json` contiene, per nove posizioni (arrocchi, en passant, promozioni, Nero al tratto), la codifica prodotta da `encode()` di `maia.ts` in Node e le tre mosse più probabili calcolate dal worker in Chromium (ONNX Runtime Web 1.23.0) a 1500 contro 1500. `tests/test_maia.py` richiede codifica identica e probabilità entro 0,005. Le differenze misurate sono al massimo 0,003. Anche il browser varia di questo ordine fra un'esecuzione e l'altra: è arrotondamento in virgola mobile, non una differenza di modello.

## Versione di onnxruntime

Prove del 29 ottobre 2026 con questo modello:

| Runtime | ENABLE_BASIC / EXTENDED | ENABLE_ALL (predefinito) |
|---|---|---|
| onnxruntime Python 1.20.1, 1.21.1, 1.22.1 | funziona | funziona |
| onnxruntime Python 1.23.2 | funziona | crash (segmentation fault) creando la sessione |
| onnxruntime-node 1.31.1 | funziona (anche `layout`) | crash |

In 1.23.2 il crash sparisce disattivando `NchwcTransformer` oppure `MatmulTransposeFusion`: è la loro combinazione. Le soluzioni adottate sono due, indipendenti:

- `requirements.lock` fissa `onnxruntime==1.22.1`;
- la sessione usa `ORT_ENABLE_EXTENDED`, che evita il crash anche con le versioni più recenti, Node compreso.

Con EXTENDED la velocità è quella di ALL: circa 34 ms a posizione da sola, 26 ms a posizione in un lotto da 32, su 4 core (WSL). Prima di aggiornare onnxruntime, ripetere `tests/test_maia.py`.

## Memoria

Misure con 4 thread, arena di memoria attiva (predefinita), sopra un processo Python con numpy e chess:

| Momento | RSS aggiuntiva |
|---|---|
| import di onnxruntime | circa 10 MB |
| sessione creata | circa 65 MB |
| dopo la prima inferenza | circa 145 MB |
| lotti da 32 | circa 190 MB |
| lotti da 128 | circa 330–355 MB |

Per questo `predict_many` divide in lotti da 32: oltre non guadagna velocità e l'arena continua a crescere. Disattivare l'arena tiene la memoria stabile intorno a 140 MB, ma produce picchi transitori di 650–750 MB con lotti grandi: non conviene. Il backend da solo occupa circa 50 MB, quindi con Maia caricato il servizio arriva a circa 250 MB.
