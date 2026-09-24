# Chess Coach

Applicazione personale locale: Maia3 come sparring partner, Stockfish come verificatore e allenamento dalle proprie partite. Interfaccia italiana, React/TypeScript, FastAPI e SQLite. Installata in WSL Debian in `/opt/generic_projects/chess-coach`.

## Avvio sul PC

```bash
cd /opt/generic_projects/chess-coach
./start.sh
```

Aprire http://localhost:8033 nel browser Windows. Per fermare il server in primo piano: Ctrl+C. Per un'altra porta: `PORT=8001 ./start.sh`.

## Funzioni

- **Gioca:** bianco o nero contro il vero modello Maia3 del sito, livello selezionabile, mosse legali e salvataggio automatico.
- **Rivedi:** importazione PGN, revisione Stockfish, momenti critici, previsioni Maia ed esportazione PGN.
- **Drill:** aperture, finale di torre e posizioni delle proprie partite; 3–12 decisioni contro Maia e revisione dedicata.
- **Puzzle:** decisioni critiche personali, alternative verificate, tentativi, indizi, soluzione e ripassi distanziati.
- **Progressi:** evidenze iniziali e piano base di 25 minuti. Aiuti e ripetizioni immediate non gonfiano i successi indipendenti.

I Puzzle personali compaiono dopo aver analizzato una partita contenente errori rilevanti. Per cominciare senza partite, utilizzare il catalogo Drill o importare un proprio PGN.

## Motori e dati

Maia3 non è una CNN: è la generazione Transformer descritta nel paper Chessformer. Si usa l'artefatto ONNX pronto del sito ufficiale, eseguito nel browser tramite JavaScript/WASM, senza addestramento. Il primo caricamento trasferisce circa 46 MB dal server locale e li conserva nella cache del browser. Stockfish 19 gira in WSL.

Le partite restano in `data/coach.sqlite3`; gli asset sono in `web/public/maia3`, `web/public/ort` e `vendor/stockfish`. Nessuna API di IA a pagamento, invio di partite o account remoto richiesto. Dopo l'installazione i motori funzionano localmente. Salvare la cartella `data` a server fermo per il backup; a server acceso usare il backup SQLite.

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

Le prove del browser usano Chromium di sistema (`/usr/bin/chromium`), il vero Maia e dati temporanei su una porta separata. Le prove Python verificano Stockfish, legalità, versioni, esercizi e registrazione dei progressi.

## Dove estendere il progetto

| Percorso | Responsabilità |
|---|---|
| `web/src/engine/maia.ts` | Tokenizzazione, maschera legale, inferenza browser |
| `backend/engine.py` | Confine Stockfish e prospettiva delle valutazioni |
| `backend/main.py` | API, persistenza, analisi, Puzzle e piano iniziale |
| `backend/drills.py` | Catalogo e preparazione delle posizioni Drill |
| `web/src/Drills.tsx` | Sessione di pratica contro Maia |
| `docs/drill-puzzle-personalizzati.md` | Analisi del sito e progetto evolutivo del tutor |

Questo è un prototipo funzionante ed estendibile. Non include ancora un modello calibrato delle competenze, un generatore tattico a più mosse o verifiche di apprendimento su posizioni nuove. L'analisi individua fino a tre momenti critici per partita con budget limitato; i temi sono indicativi. Il piano attuale è semplice e trasparente, non un tutor autonomo completo.

Progetto indipendente, senza affiliazione a Maia Chess. Attribuzioni e licenze in `THIRD_PARTY.md`; sorgenti applicativi GPL-3.0, artefatti esterni con le rispettive condizioni.

Per fermare l'istanza avviata in background da questa sessione: `python3 scripts/stop.py`. L'arresto attende le eventuali analisi in corso.

