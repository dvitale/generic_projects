# Ciclo mensile del laboratorio — 21 ottobre 2026

Questa procedura è esclusa da gioco, analisi, interfaccia e deploy di SparringMate.
Qualsiasi integrazione richiede una nuova conferma dell'utente.

## Avvio e ripresa

Da `/opt/generic_projects/chess-coach/experiments/human-policy`:

```bash
make cycle MONTHS=2026-09 CYCLE_STEPS=10000
make cycle-status
make month-status MONTH=2026-09
```

Lo stesso comando riprende un ciclo interrotto. Per elaborare più mesi, indicare
una lista separata da virgole, distinta e in ordine cronologico. Sono ammessi
solo archivi realmente pubblicati da Lichess; non è stato programmato alcun
download di mesi successivi a settembre. Il ciclo si ferma al primo errore.
Non usa scheduler, servizi dell'app o credenziali personali.

Ctrl+C/SIGTERM durante il training richiede un checkpoint dopo il batch.
Durante il campionamento conserva l'ultima transazione completata; al riavvio
rilegge il flusso compresso fino al punto salvato. Non è un accesso casuale al PGN.

## Campione distribuito sull'intero mese

- Lettura dell'intero `.pgn.zst` in streaming, senza PGN decompresso su disco.
- Filtro: standard rated rapid, 600–2600, nessun titolo BOT, risultato presente
  nel movetext e data coerente con il mese. Rating provvisori non identificabili.
- Prima selezione deterministica per hash della partita: circa una su 64;
  una su 16 quando almeno uno dei giocatori è nella fascia 600–1199.
- Fino a 8 posizioni per partita. Il rating è quello del giocatore al tratto.
- Capacità massima di un milione di posizioni; quote separate per split,
  giorno, fascia di 200 punti e fase. Le fasce rare possono lasciare quote vuote.
  All'interno delle quote si conservano le priorità hash più piccole, non
  semplicemente le prime partite del mese.
- Fase approssimata: apertura entro mossa 10, finale con materiale totale
  non pedonale di al massimo 13 punti, mediogioco altrimenti. Non è una diagnosi
  strategica del motore; serve soltanto a distribuire il campione.
- Split deterministico per partita 80/10/10. Non è uno split per giocatore.
- Checkpoint di estrazione ogni 10.000 partite scorse, SQLite limitato a circa
  2 GiB per file, controllo dello spazio fisico e virtuale durante l'estrazione.

## Verifica fissa e memoria

Dal primo mese si congelano fino a 10.000 posizioni di validation e 10.000 di
test, scegliendole fra quelle non presenti nel train del primo mese. Questo
mantiene nel training le aperture comuni, invece di escluderle tutte perché
ricompaiono anche nelle partite di verifica. I mesi successivi non modificano
questi file. Il test viene conservato
senza valutarlo durante il ciclo. Le chiavi delle posizioni del holdout vengono
usate solo per escludere duplicati dai dati di training e replay.

Il confronto mensile separato sui suoi split originari può contenere
posizioni apprese nel mese stesso o in mesi anteriori: il riferimento principale è la validation
fissa, mai usata come bersaglio di training. I giocatori possono ricomparire
in split diversi; l'assenza di questa sovrapposizione non è garantita.

La memoria conserva fino a 100.000 posizioni train selezionate per priorità
hash dall'unione dei mesi passati. Con memoria non vuota, il campionamento
assegna il 20% di probabilità alla memoria e l'80% al mese corrente. È una
proporzione attesa, non un numero rigido in ogni batch. Le fasce di rating
vengono pesate moderatamente all'interno di ciascun gruppo.

## Training e criterio di accettazione

- Modello tiny, batch 64, massimo 10.000 passi aggiuntivi per mese.
- Valutazione ogni 1.000 passi; arresto dopo 3 verifiche senza un miglioramento
  NLL di almeno 0,001. Si conserva il checkpoint con la migliore NLL.
- Da un mese al successivo si preservano pesi, AdamW e contatore globale.
  Il campionamento viene reinizializzato sul nuovo dataset. La ripresa nello
  stesso mese conserva invece anche RNG e stato del campionatore.
- I fingerprint di dataset, validation, replay e checkpoint padre impediscono
  di riprendere silenziosamente con dati diversi.
- Il primo checkpoint deve avere NLL finita e migliore della policy uniforme.
- I successivi non devono peggiorare la NLL globale di oltre 0,03 né perdere
  oltre 5 punti percentuali di top-1 globale o nelle fasce 600–799, 800–999,
  1000–1199, quando la fascia contiene almeno 100 posizioni di verifica.

Queste soglie sono protezioni esplorative, non una certificazione statistica
di superiorità o di forza Elo. La selezione ripetuta sulla validation può
adattarsi a quel campione; il test separato serve per una verifica futura.
Un mese respinto non diventa il modello attivo e il suo archivio resta disponibile.

## Rimozione e spazio

La rimozione riguarda esclusivamente il file mensile dal nome previsto,
dopo la registrazione atomica di un ciclo completato. Prima della rimozione
si ricontrollano gli hash di checkpoint, rapporto di verifica, holdout, memoria
e archivio grezzo. File simbolici al posto del singolo archivio vengono rifiutati.
I checkpoint e campioni dei due mesi più recenti restano conservati; per i mesi
precedenti restano manifest e rapporti. Budget dei dati/checkpoint del ciclo:
8 GiB, oltre al download mensile; riserva minima sul disco host: 10 GiB.

Per questo PC gli archivi grezzi sono conservati su Windows, in
`C:\Users\dante\Documents\Codex\SparringMate-lab\archives`, collegata alla
cartella `data/monthly` del laboratorio. La copia parziale è stata migrata con
verifica SHA256. Questo permette di recuperare realmente lo spazio Windows
quando si rimuove un archivio, evitando la crescita progressiva del disco virtuale WSL.
Campioni, memoria e checkpoint restano in Debian. L'archivio Windows è escluso da Git.

## File di stato

- `data/cycles/status.json`: fase corrente o errore.
- `data/cycles/ledger.json`: mesi accettati e checkpoint attivo.
- `data/cycles/fixed.sqlite`: validation/test congelati.
- `data/cycles/replay.sqlite`: memoria train compatta.
- `data/cycles/months/<mese>.progress.json`: avanzamento dell'estrazione.
- `runs/monthly/<mese>/plan.json`: configurazione immutabile del training.
- `runs/monthly/<mese>/progress.json`: checkpoint migliore e arresto anticipato.
- `runs/monthly/<mese>/verification.json`: confronto finale e decisione.
- `data/monthly/<mese>.cleanup.json`: prova della rimozione dell'archivio.

## Verifiche eseguite

Le prove usano PGN sintetici con mosse legali per controllare due mesi consecutivi,
la continuità dell'ottimizzatore, il replay, l'immutabilità del holdout, la ripresa
dell'estrazione, il rifiuto di regressioni e i blocchi alla cancellazione.
Queste prove verificano il procedimento; non rappresentano un training sui mesi
reali. Il download reale va completato e verificato prima di eseguire quel training.
