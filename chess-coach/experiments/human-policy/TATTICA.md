# Migliorare lo sparring partner — laboratorio tattico

Il programma `tactical_lab.py` confronta varianti del modello umano senza cambiare
il servizio su 8044, il selettore, il database delle partite o il registro dei
checkpoint mensili. Dati, pesi e risultati restano nella cartella ignorata `runs/`.
Non vengono scaricati nuovi archivi né inviati dati a servizi esterni.

## Primo esperimento

```bash
make tactical-pilot
make tactical-status
make test
```

Il comando usa il checkpoint agosto 2026, che è il secondo ciclo di training,
e i campioni locali già conservati. È un confronto deliberatamente congelato;
non segue `latest`. Il programma offre `--help` per sorgenti e budget espliciti.
Per cambiare parametri o codice usare una nuova directory `--output`.

1. Seleziona 60.000 posizioni train senza duplicati: 80% dal mese e 20% dal replay.
   Esclude le partite e le posizioni del holdout principale e le posizioni note
   della diagnosi della donna. Usa solo rating del giocatore al tratto 600–1500.
2. Ricostruisce da FEN pezzi, turno, arrocco, en passant, contatori e mosse legali.
   Controlla i campi salvati e che il target umano sia legale e allineato. Controlla
   anche tutte le 6.877 posizioni della validation di fascia. Il dump PGN grezzo
   non è più presente: questa verifica non ricontrolla i rating contro gli header
   originali; la loro attribuzione al lato giusto è coperta dai test dell'estrattore.
3. Prepara 50 posizioni ordinarie e 50 arricchite in urgenze, entrambe bilanciate
   per fascia di 200 punti; quattro posizioni note della partita e due casi
   sintetici sono separati dai risultati su dati non addestrati.
4. Valuta ogni mossa legale con Stockfish: 12.000 nodi, un thread, hash azzerato
   fra mosse. Un sacrificio di donna che porta a matto verifica che non si usi
   la semplice perdita materiale come definizione di errore.
5. Esegue tre bracci di 500 passi, batch 64, learning rate 0,00003, stessi pesi
   iniziali e nuovo ottimizzatore AdamW: normale; peso ×3 alle urgenze; stesso
   peso ×3 e compito ausiliario con coefficiente 0,2.
6. Confronta tutti i bracci con il modello originale su validation umana completa
   e banco tattico congelato. Diagnostica offline anche temperature 0,8 e 0,6.

Il compito aggiuntivo predice due mappe di attacco (bianco e nero) dalle
rappresentazioni delle 64 caselle. Le etichette derivano dalle regole degli
scacchi e comprendono attacchi geometrici di pezzi inchiodati. **Non sono una
certificazione di sicurezza** e non decidono la mossa da giocare. All'inferenza
rimane solo la policy originale, senza questa testa aggiuntiva.

Le urgenze sono un criterio preliminare di campionamento: scacco o un pezzo
diverso da un pedone sotto attacco geometrico. Non eliminiamo errori umani e
non sostituiamo i target con le mosse di Stockfish. I tre bracci permettono di
separare l'effetto del campionamento da quello del compito ausiliario.

## Come leggere i risultati

`runs/tactical-pilot-v1/RISULTATI.md` riassume il confronto; `comparison.json`
contiene metriche per fascia, temperatura e singola posizione.

- Top-1 e NLL misurano corrispondenza con decisioni umane; non misurano Elo.
- La **massa degli errori gravi** è la somma delle probabilità assegnate a mosse
  che Stockfish valuta peggiori della migliore candidata di almeno 200 centipawn
  e 0,15 di aspettativa WDL, oppure che concedono un matto evitabile. La soglia
  WDL limita la distorsione dei centipawn nelle posizioni già perse o vinte.
- La prima scelta sbagliata misura il problema che rimarrebbe senza estrazione.
- Il tasso degli errori nelle mosse umane di quelle stesse posizioni è un
  riferimento descrittivo, con un solo esempio umano osservato per posizione.
- Stockfish a nodi limitati può sbagliare. Le posizioni decisive richiedono una
  seconda analisi più profonda prima di trarre conclusioni.
- Il campione è piccolo e stratificato: non stima la frequenza degli errori in
  una partita completa e non dimostra forza equivalente a Maia online.

## Decisioni dopo il pilota

Prima di guardare i risultati fissiamo questi segnali esplorativi: NLL umana non
peggiore del riferimento di oltre 0,03; Top-1 non inferiore di oltre un punto
percentuale; riduzione relativa almeno del 10% della massa grave nelle urgenze;
nessun aumento oltre un punto percentuale nel campione ordinario. La partita
nota è una diagnosi, non il criterio di selezione di un vincitore.

Questi segnali non autorizzano automaticamente una promozione. Un candidato
promettente richiede più posizioni tattiche, ulteriori seed di training e partite
complete con colori alternati e apertura comune. Se nessuno supera il pilota,
conserviamo il risultato negativo e rivediamo campionamento o rappresentazione;
non proponiamo il modello come migliorato solo perché ha fatto altro training.

## Ripresa e tracciabilità

`manifest.json` congela parametri, hash di dati, checkpoint, Stockfish e codice.
Sono conservati audit, etichette Stockfish, log e checkpoint dei tre bracci.
Ripetere lo stesso comando riusa le fasi completate: analisi riparte dall'ultima
posizione salvata; un braccio di training interrotto riparte da zero, mentre quelli
completi vengono riutilizzati. Non è una ripresa a metà ottimizzatore.
Non avviare due copie contemporaneamente nella stessa directory.

Le identità del test vengono usate soltanto per escludere sovrapposizioni;
le sue mosse e le prestazioni sul test non vengono valutate. Una validation
già usata per scegliere checkpoint non è un test finale indipendente.

## Diagnosi delle perdite e partite offline

`tactical_report.py` affianca la massa di perdite di almeno 200 e 500 centipawn
alla metrica WDL congelata del pilota. È necessario perché WDL può saturare in
una posizione già sfavorevole e nascondere una successiva perdita di donna.
Il rapporto principale da leggere è `RAPPORTO.md`; `RISULTATI.md` conserva la
misura originale per trasparenza. Il criterio iniziale non viene riscritto.

```bash
.venv/bin/python tactical_report.py --directory runs/tactical-pilot-v1
.venv/bin/python tactical_matches.py \
  --candidate runs/tactical-pilot-v1/focus_aux.pt \
  --stockfish ../../vendor/stockfish/stockfish-linux-x86-64-universal \
  --output runs/tactical-matches-v1
```

Il confronto di partite usa due coppie con colori invertiti, seed riproducibili,
due inizi comuni, rating in ingresso 600 e campionamento completo a temperatura
1. Sono al massimo 160 semimosse aggiuntive per partita; una partita interrotta
al limite resta `*`. Le patte reclamabili vengono considerate patte. Stockfish
valuta gli errori separatamente e non interviene nelle mosse. I PGN, le decisioni
e il riepilogo vengono conservati. Quattro partite sono una diagnosi, non una
dimostrazione di superiorità o una stima Elo. Il candidato non diventa attivo.

## Esito del primo pilota

Il [rapporto congelato del 24 ottobre](RISULTATI-TATTICA.md) include anche il
ricontrollo profondo e quattro partite offline. Nessun candidato è stato promosso.
