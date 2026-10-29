# Maia sul server

Data: 29 ottobre 2026. `backend/maia.py` esegue sul server lo stesso Maia3 del browser: stesso file ONNX, stessa codifica della posizione, stessa tabella delle mosse. Serve ai calcoli a lotti che il browser farebbe lentamente o che non devono dipendere da una pagina aperta (selezione delle posizioni, stime per livello). Il gioco in Gioca e nei Drill resta nel browser.

## Uso

```python
from backend.maia import maia
maia.available()                                   # modello e onnxruntime presenti?
maia.predict(fen, 1500, 1500)                      # come maia.predict() di web/src/engine/maia.ts
maia.predict_many([(fen, 800, 800), (fen, 2200, 2200)])   # a lotti di 32, risultati nello stesso ordine
```

Il risultato ha le chiavi del browser: `moves` (UCI e probabilità, ordinate), `whiteExpectedScore`, `whiteOutcome`. Nelle posizioni senza mosse legali il modello non viene chiamato. La sessione si carica alla prima richiesta, non all'avvio del servizio. Le esecuzioni sono serializzate da un lock.

Il modello si legge da `web/public/maia3/maia3_simplified.onnx` (scaricato da `scripts/install.sh`, escluso da git, copiato da `make deploy`), oppure da `MAIA_MODEL_PATH`. `MAIA_THREADS` limita i thread di calcolo (0, il predefinito, li usa tutti). `/api/health` riporta `maiaServer: disponibile | assente`.

Il primo uso è il filtro degli abbagli di Blunder prevention ([docs/blunder-prevention.md](blunder-prevention.md#abbagli-e-lacune)).

## Fedeltà al browser

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
