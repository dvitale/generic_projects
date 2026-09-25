# SparringMate

La revisione mostra fino a tre scelte per Stockfish (MultiPV, con valutazione e variante) e Maia (ordinate per probabilità al livello selezionato). Se le mosse legali sono meno di tre, mostra solo quelle disponibili. Le analisi salvate precedentemente si aggiornano con **Aggiorna revisione completa**.

Applicazione personale locale: Maia3 come sparring partner, Stockfish come verificatore e allenamento dalle proprie partite. Interfaccia italiana, React/TypeScript, FastAPI e SQLite. Installata in WSL Debian in `/opt/generic_projects/chess-coach`.

## Avvio sul PC

```bash
cd /opt/generic_projects/chess-coach
./start.sh
```

Aprire http://localhost:8033 nel browser Windows. Per fermare il server in primo piano: Ctrl+C. Per un'altra porta: `PORT=8001 ./start.sh`.

## Funzioni

- **Spazio di lavoro:** scacchiera e pannello affiancati sui monitor grandi; in Rivedi le schede Mosse, Elo, Tutor e Approfondimenti conservano la posizione e i calcoli durante il cambio scheda. Archivio nella voce Partite. Drill separa catalogo e sessione. Su mobile il layout torna a una colonna.

- **Annulla ultima mossa:** in Gioca e Drill ritorna alla tua ultima decisione, togliendo anche la risposta di Maia o interrompendola se ancora in preparazione. Nei Drill conserva la sequenza iniziale. Disponibile anche dopo la conclusione; PGN importati e copie archiviate restano in sola revisione.
- **Elo della partita:** calcolo automatico e risultato visibile in Gioca a partita conclusa; in Rivedi puoi avviarlo anche durante una partita. Confronta tutte le tue decisioni utili con 21 livelli Maia usando il criterio dei Drill ufficiali e mostra il profilo piu compatibile, senza una fascia di precisione arbitraria. Richiede almeno 10 decisioni non obbligate; non equivale a un rating ufficiale. Metodo e limiti in [docs/elo-partita.md](docs/elo-partita.md).
- **Ritmo Maia:** risposte con attesa variabile di circa 1,2–3,2 secondi, comprendente il tempo di inferenza, e breve animazione del pezzo. Il caricamento iniziale del modello può richiedere più tempo. Lo stesso ritmo vale nei Drill; il cambio di sezione annulla le risposte ancora in preparazione.
- **Gioca:** bianco o nero contro il vero modello Maia3 del sito, livello selezionabile, mosse legali e salvataggio automatico. Puoi trascinare i pezzi con mouse o touch oppure usare due clic; le promozioni mantengono la scelta del pezzo.
- **Rivedi:** revisione passo passo di entrambe le parti. Ogni posizione confronta mossa giocata, scelta Stockfish e mossa più probabile di Maia al livello selezionato, con probabilità e varianti. Le frecce e il selettore delle mosse mostrano la scacchiera prima della decisione. Restano importazione/esportazione PGN e momenti critici personali. Per vecchie analisi, ricalcolare per includere tutte le mosse.
- **Drill:** aperture, finale di torre e posizioni delle proprie partite; 3–12 decisioni contro Maia e revisione dedicata.
- **Puzzle:** decisioni critiche personali, alternative verificate, tentativi, indizi, soluzione e ripassi distanziati.
- **Tutor DeepSeek:** spiegazioni e piano dopo la revisione Stockfish, con riflessione del giocatore e collegamenti agli esercizi. Vedi `docs/tutor-deepseek.md`.
- **Progressi:** evidenze iniziali e piano base di 25 minuti. Aiuti e ripetizioni immediate non gonfiano i successi indipendenti.

I Puzzle personali compaiono dopo aver analizzato una partita contenente errori rilevanti. Per cominciare senza partite, utilizzare il catalogo Drill o importare un proprio PGN.

## Motori e dati

Maia3 non è una CNN: è la generazione Transformer descritta nel paper Chessformer. Si usa l'artefatto ONNX pronto del sito ufficiale, eseguito nel browser tramite JavaScript/WASM, senza addestramento. Il primo caricamento trasferisce circa 46 MB dal server locale e li conserva nella cache del browser. Stockfish 19 gira in WSL.

Le partite restano in `data/coach.sqlite3`; gli asset sono in `web/public/maia3`, `web/public/ort` e `vendor/stockfish`. Maia e Stockfish funzionano localmente. Il tutor DeepSeek opzionale richiede una chiave e invia i dati selezionati al servizio solo quando richiesto. Salvare la cartella `data` a server fermo per il backup; a server acceso usare il backup SQLite.

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

Le richieste Maia di gioco, revisione ed Elo condividono una coda: non vengono eseguite contemporaneamente sulla stessa sessione ONNX. Gli output vengono verificati anche nella dimensione e nella valutazione; in caso di numeri non validi il worker viene ricreato e la stessa inferenza ritentata una volta. Un errore persistente interrompe il calcolo senza salvare punteggi parziali. Le prove di recupero usano anche un worker simulato per iniettare errori numerici riproducibili.

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



## Aspetto della scacchiera

L'installazione sul PC usa il tema **Green** e i pezzi **Neo** richiesti, scaricati dai server pubblici di Chess.com e conservati localmente. Le immagini sono escluse da Git e conservano i diritti originali. Su un nuovo clone puoi installarle con `python3 scripts/install_chesscom_theme.py`, poi ricompilare il frontend. In assenza delle immagini sono disponibili una scacchiera CSS e pezzi Unicode di riserva.

## Configurazione del tutor

`python3 scripts/configure_deepseek.py` configura la chiave con input nascosto. La credenziale rimane in `.secrets/deepseek.json`, esclusa da Git. La spiegazione viene salvata nel database con l'analisi a cui si riferisce. Dettagli sui dati inviati, sul modello e sui limiti in `docs/tutor-deepseek.md`.
