# SparringMate Human Policy — prototipo locale

Modello sperimentale che riceve **FEN + rating Lichess rapid del giocatore al
tratto** e restituisce le **5 mosse più probabili**, le rispettive probabilità
e la probabilità complessiva delle altre mosse. `TOP_K` modifica il numero
visualizzato; le probabilità non vengono rinormalizzate sulle sole prime K.

Non esplora continuazioni: considera soltanto le mosse legali nella posizione
attuale (normalmente qualche decina). La rappresentazione teorica comprende
64 × 64 × 5 codici origine/destinazione/promozione, ma la rete calcola il
punteggio solo per i candidati legali.

**Non è ancora un avversario calibrato, non stima l'Elo dell'utente e non
sostituisce il motore attuale di SparringMate.** L'integrazione richiede una
successiva autorizzazione esplicita dell'utente. La prima prova verifica il
procedimento di addestramento; non dimostra qualità scacchistica.

## Hardware rilevato il 20 ottobre 2026

- Windows: Intel Core Ultra 7 155H, 16 core / 22 processori logici, circa 32 GB RAM.
- GPU: NVIDIA RTX 4050 Laptop, 6.141 MiB VRAM rilevati da nvidia-smi.
- Debian WSL2: circa 15 GiB RAM disponibili alla VM, 8 GiB swap.
- Ambiente Python dedicato `.venv/`, separato da quello dell'applicazione.
- PyTorch 2.7.1 con CUDA 12.8; non viene installato un nuovo driver GPU.

## Procedura

Nella directory `/opt/generic_projects/chess-coach/experiments/human-policy`:

```bash
make setup              # librerie GPU, alcuni GB, solo la prima volta
make download           # campione compresso limitato a 32 MiB
make prepare            # scorre al massimo 5.000 partite, seleziona rapid
make test
make train STEPS=100     # prova breve; non è un addestramento completo
make status
make resume STEPS=100    # aggiunge 100 passi al checkpoint corrente
make predict FEN="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" ELO=1000
```

Per il modello più grande:

```bash
make train PRESET=small RUN=runs/small BATCH=16 STEPS=100
make resume PRESET=small RUN=runs/small BATCH=16 STEPS=100
```

`tiny` usa 4 blocchi, dimensione 128; `small` 6 blocchi, dimensione 256.
Entrambi hanno attenzione con bias relativo di file/ranghi: è una base
semplice, **non** l'implementazione del Geometric Attention Bias dinamico
di Chessformer. Il conteggio esatto dei parametri compare nel rapporto.

L'addestramento avviene in primo piano; **Ctrl+C** richiede salvataggio e
arresto dopo il batch. Dopo l'arresto viene calcolato il rapporto di
validazione. Un arresto forzato del sistema conserva l'ultimo checkpoint
periodico, scritto atomicamente ogni 50 passi.

La ripresa conserva rete, ottimizzatore, generatore di campionamento, stato
casuale e contatore. Richiede lo stesso dataset, configurazione e batch size.
Per modificare il dataset dopo una prova, usare una nuova cartella `RUN`.
Non sono previsti processi automatici o addestramenti notturni.

## Dati e prevenzione delle valutazioni fuorvianti

### Archivio mensile completo — 21 ottobre 2026

È disponibile un download separato dell'intero settembre 2026, senza modificare
i campioni e i checkpoint del pilota. Dimensione remota verificata:
**29.224.520.887 byte**, circa 27,22 GiB, 89,6 milioni di partite di tutti i ritmi.
Il download completo non equivale ancora a un dataset rapid pronto per il training.

```bash
make download-month MONTH=2026-09    # avvio o ripresa in primo piano
make month-status MONTH=2026-09
```

- File in `data/monthly/`, esclusi da Git e dalla pubblicazione.
- URL, dimensione, ETag e SHA256 ufficiale fissati nel manifest locale.
- Il file rimane `.part` finché il checksum dell'intero archivio su disco non
  coincide con quello ufficiale. Lo stato `complete` conferma questa verifica.
- Ripresa HTTP dall'ultimo byte scritto, con controllo della risposta del server;
  tentativi automatici limitati dopo errori di rete. Un blocco impedisce due download
  contemporanei dello stesso mese. Ctrl+C conserva il file parziale.
- Controllo dello spazio sia in Debian sia sul disco Windows `/mnt/c`: almeno
  10 GiB devono rimanere liberi. Per una diversa collocazione di WSL specificare
  `--host-disk` con il volume che contiene effettivamente il disco virtuale.
- Stato in `2026-09.status.json`; il trasferimento avviato il 21 ottobre scrive
  anche `2026-09.log` e continua in un processo locale indipendente dalla chat.
  Spegnimento o sospensione possono interromperlo: lo stesso comando lo riprende.
- Nessuna decompressione integrale, estrazione illimitata o nuova sessione di
  training viene avviata automaticamente. L'estrazione successiva dovrà essere
  progressiva, con un limite di spazio e un campionamento distribuito sul mese.

### Campione pilota

- Fonte: archivio pubblico Lichess standard rated, settembre 2026, CC0.
- Il download è un **prefisso limitato** dell'archivio mensile, non un
  campione rappresentativo del mese. Un file già presente non viene sovrascritto.
- Sono accettate partite rapid classificate, senza titolo BOT, con PGN valido
  e risultato finale nel movetext. L'ultimo PGN troncato viene scartato.
- Rating accettati: 600–2600. I rating provvisori non sono identificabili in
  modo affidabile da questi campi: **non sono esclusi**. Nemmeno eventuali
  account non dichiarati come bot possono essere identificati con certezza.
- Massimo 16 posizioni casuali per partita, tratte dall'intera partita.
- La mossa bersaglio è quella umana, senza correzioni Stockfish.
- Il rating associato è quello del giocatore al tratto, non la media dei due.
- Il split 80/10/10 è deterministico per partita: nessuna partita attraversa
  train, validation e test. Il test è conservato e non usato nella prova breve.
- **Non** è ancora un split temporale o per giocatore. Posizioni identiche
  (soprattutto aperture) possono comparire in partite diverse fra i split.
  Questi limiti impediscono di presentare l'accuratezza come generalizzazione.
- L'estrazione è ripetibile e riprendibile: rilegge il prefisso, salta le
  partite già registrate, salva una transazione per partita.
- In train si favoriscono moderatamente le fasce di 200 punti meno frequenti:
  peso `min(4, sqrt(conteggio_fascia_massima / conteggio_fascia))` per esempio.
  Evita di assegnare lo stesso peso totale a fasce con migliaia di esempi e
  fasce con appena dieci. La ripresa richiede lo stesso schema di campionamento;
  i primi checkpoint smoke, creati con lo schema precedente, restano consultabili
  per inferenza ma richiedono una nuova run per il training aggiornato.
- Il rapporto riporta NLL, top-1/3/5, confronto NLL uniforme, calibrazione
  top-1 descrittiva e conteggi per fascia sulla validation. Separa inoltre
  posizioni con mossa obbligata e posizioni con più alternative legali.
- Le probabilità del prototipo non sono ancora calibrate. Il rating richiesto
  deve essere compreso fra minimo e massimo osservati nel train; questa
  verifica non garantisce una copertura sufficiente delle fasce intermedie.

Il dataset conserva solo posizione, rating, codifica, mossa e identificatore
hash della partita. Il risultato, i tempi futuri e le valutazioni del motore
non vengono passati al modello. Gli orologi, il rating avversario e la storia
recente saranno estensioni da misurare separatamente; una FEN isolata non
ricostruisce le ripetizioni precedenti.

## File prodotti (esclusi da Git)

- `data/lichess-prefix.pgn.zst` e metadati con fonte, dimensione e SHA256.
- `data/positions.sqlite` e `data/positions.report.json`.
- `runs/<nome>/last.pt`: checkpoint locale fidato, inclusi stato e ottimizzatore.
- `runs/<nome>/training.jsonl`: andamento della loss.
- `runs/<nome>/report.json`: metriche, velocità e memoria GPU della prova.

## Prossime tappe

1. Ampliare a un campione distribuito su più periodi e verificare la copertura
   della fascia 600–1200; non estrapolare fasce con dati insufficienti.
2. Creare validation temporale e test finale separato per giocatore, con
   diagnostica delle posizioni duplicate. Congelare i manifest prima di allenare.
3. Confrontare tiny/small e Maia-3 5M su identiche posizioni e rating.
4. Misurare calibrazione, probabilità di errori e comportamento in partite
   complete. Stockfish serve per la verifica, non per correggere la policy.
5. Misurare esportazione ONNX/quantizzazione nel laboratorio. Qualsiasi
   integrazione nell'app richiede la successiva conferma dell'utente.

## Pilota e confronto riproducibile

Risultati della prima prova: [RISULTATI-PILOTA.md](RISULTATI-PILOTA.md).
Le metriche complete sono in [reports/pilot.json](reports/pilot.json).

Eseguire dalla cartella del laboratorio; nessun comando avvia o modifica il servizio:

```bash
make prepare DATA=data/pilot.sqlite GAMES=20000
make train DATA=data/pilot.sqlite RUN=runs/tiny-pilot PRESET=tiny BATCH=64 STEPS=1000
make train DATA=data/pilot.sqlite RUN=runs/small-pilot PRESET=small BATCH=64 STEPS=1000
make reference
make test
make benchmark DATA=data/pilot.sqlite OUTPUT=runs/comparison-pilot
```

Le run già esistenti non vengono sovrascritte. Per una nuova prova cambiare i
nomi delle run e passare i nuovi checkpoint a `benchmark.py --tiny ... --small ...`.
Il riferimento Maia-3 5M viene scaricato con revisioni del codice e dei pesi
fissate e SHA256 verificato, in `baselines/` esclusa da Git. Non viene installato
nell'ambiente dell'applicazione. Il suo codice resta nel repository originale
con la propria licenza; non è incorporato nella rete sperimentale.

Il confronto verifica prima la corrispondenza con le probabilità del percorso
UCI ufficiale, compresi Nero, arrocco, en passant e promozioni. Usa poi le stesse
5.233 posizioni di validation per tutti i modelli; salva il manifest, gli hash,
le metriche per fascia, i tempi CPU/GPU e un rapporto `CONFRONTO.md`.
Un secondo confronto elimina le posizioni presenti nel train. L'ablazione
con rating fisso 1500 controlla se il rating reale migliora la previsione.
Il test finale resta non valutato. Maia preaddestrato e i prototipi non hanno
ricevuto la stessa quantità di training: questo è un riferimento pratico,
non una classifica delle architetture neurali.

## Fonti

- https://database.lichess.org/
- https://github.com/CSSLab/maia3
- https://huggingface.co/UofTCSSLab/Maia3-5M
- https://arxiv.org/html/2605.19091v1
- https://pytorch.org/get-started/locally/

Questa rete è un prototipo nuovo; non contiene pesi Maia o codice copiato
dai repository confrontati. Il motore dell'app e i dati personali non vengono usati.
