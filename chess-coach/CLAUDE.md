# SparringMate — istruzioni di progetto

Allenamento scacchistico personale: backend FastAPI + SQLite (`backend/`), interfaccia React/TypeScript con Vite (`web/src`), Stockfish via python-chess, Maia (ONNX) nel browser. Il repository git parte da `/opt/generic_projects`: questa cartella è una sua sottocartella. Il manuale è `README.md`; le schede tecniche per area stanno in `docs/`.

## Comandi

```bash
make start | status | restart | stop | logs   # servizio locale su http://localhost:8033
make build                                    # ricompila l'interfaccia (web/dist)
.venv/bin/python -m pytest tests -q           # prove backend
cd web && npm run build && npx playwright test [tests/<file>.spec.ts]
make deploy                                   # pubblica su https://sparringmate.u-s.it
make puzzles PER_BAND=3000                    # importa i problemi Lichess
make experimental                             # servizio del motore sperimentale (porta 8044, solo PC)
```

- Le prove Playwright avviano da sole un server sulla porta 8011, con dati temporanei e `CHESS_COACH_DISABLE_AUTH=1` e `CHESS_COACH_DISABLE_LLM=1`, e usano `/usr/bin/chromium`. Prima va fatto `npm run build`: il server di prova serve `web/dist`.
- `tests/test_static_cache.py` viene saltato se l'interfaccia non è compilata.
- Variabili d'ambiente: `CHESS_COACH_DATA` (cartella dei dati), `STOCKFISH_PATH`, `SPARRINGMATE_USER`/`SPARRINGMATE_PASSWORD` (login, anche da `.env`), `DEEPSEEK_API_KEY`/`DEEPSEEK_MODEL` (tutor), `SPARRINGMATE_EXPERIMENTAL_ENGINE` (URL del motore sperimentale, anche da `.env`; senza, il selettore in Gioca non compare), `SPARRINGMATE_ALTERNATIVE_THRESHOLDS` (JSON con le soglie di «Trova un’alternativa», vedi `docs/trova-alternativa.md`).
- La suite Playwright avvia anche `tests/fixtures/fake_policy_service.py` sulla porta 8012, al posto del motore sperimentale.

## Produzione

- `make deploy` esegue `scripts/deploy.sh`: compila, sincronizza con rsync su `root@sparringmate.u-s.it:/opt/sparringmate`, riavvia e controlla la salute. Dettagli in `deploy/SERVER.md`.
- Il server a volte va in timeout su SSH: l'utente può lanciare `make deploy` dal proprio terminale.
- **Non leggere né modificare il database di produzione senza un'autorizzazione esplicita dell'utente** (dati in `/opt/sparringmate/data`).
- Le migrazioni dello schema (`ALTER TABLE ... ADD COLUMN` quando la colonna manca) si applicano da sole all'avvio del servizio.
- Le pagine HTML sono servite con `Cache-Control: no-cache`; i file in `/assets/` hanno un hash nel nome e sono immutabili. Se dopo un deploy l'interfaccia sembra vecchia, controlla prima questi header.

## Trappole note

- Nella suite Playwright completa, `evaluation-chart.spec.ts`, `refutation.spec.ts`, `puzzle-flow.spec.ts`, `training-plan.spec.ts` e `undo-rating.spec.ts` a volte falliscono, ma passano se eseguiti da soli.
- `experiments/` (ricerca locale: in git solo il codice; dati, pesi e `.venv`, diversi GB, sono esclusi dal suo `.gitignore`) è esclusa dal deploy, quindi in produzione il motore sperimentale non esiste: se `make deploy` resta fermo su «Sincronizzo», cerca nuove cartelle pesanti non escluse in `scripts/deploy.sh`.
- `docs/training-guide.html` si genera da `docs/training-guide.md` con `pwsh -File scripts/build_training_guide.ps1`. Se pwsh non è installato, l'HTML va aggiornato a mano con lo stesso contenuto.
- Nelle prove, `exercises` e `prevention_positions` hanno `UNIQUE(game_id, ply)`: per creare più esercizi della stessa partita servono ply diversi.
- I problemi Lichess importati sono un campione ordinato per ID: gli ID iniziano tutti per "0".
- Le valutazioni e le classificazioni didattiche (diagnosi, Blunder prevention, Puzzle) le decide Stockfish con regole fisse; il tutor DeepSeek interpreta soltanto.

## Convenzioni

- Codice compatto, nello stile dei file vicini; commenti in inglese, testi dell'interfaccia e documentazione in italiano.
- Ogni funzione nuova ha prove backend (pytest) e, quando tocca l'interfaccia, una prova Playwright.
- Aggiorna `README.md` e la scheda in `docs/` dell'area modificata nello stesso commit.
