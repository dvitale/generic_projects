# Distillazione: confronto pilota

Per una spiegazione orientata agli obiettivi di gioco, iniziare da
[SPERIMENTAZIONE-GUIDA.md](SPERIMENTAZIONE-GUIDA.md).

## Procedura

`distillation.py` usa il campione già preparato da `tactical_lab.py` e il
checkpoint verificato di agosto. Le posizioni train vengono campionate in modo
deterministico: 80% dal mese e 20% dal replay. Sono esclusi i giochi e le FEN
della validation e le posizioni note di diagnosi. La validation completa viene
usata per il confronto umano; un sottoinsieme separato è etichettato anche con
Maia per misurare la distanza delle distribuzioni. Il test finale non è valutato.

L'insegnante è `models/maia3/maia3_simplified.onnx`, usato localmente tramite il
codice Maia dell'applicazione in un processo separato. Non si invocano servizi
Internet. L'insegnante riceve solo la posizione corrente e due rating uguali:
il rating avversario reale non è presente nel dataset. Non ha la storia dei 64
mezzi tratti di Cloverb o l'orologio. Non è dimostrato identico a maiachess.com.

Ogni output contiene tutte le mosse legali e le loro probabilità. Sono verificati
legalità, unicità, corrispondenza col vocabolario dello studente, finitezza e
normalizzazione. Le etichette sono associate all'identità dell'esempio, salvate
a batch e riutilizzate dopo interruzione. I tre modelli usano gli stessi esempi e
un nuovo AdamW inizializzato identicamente; cambia solo il peso dell'insegnante:

- `human`: 0% insegnante, 100% mossa umana;
- `mixed`: 50% insegnante, 50% mossa umana;
- `teacher`: 100% insegnante.

La loss è `(1-alpha) * cross_entropy_mossa + alpha * cross_entropy_teacher`.
Le posizioni con liste di mosse di lunghezza diversa vengono riempite solo
all'interno del batch; il riempimento ha probabilità zero e non entra nella loss.
Non si introduce Stockfish nel training o nel comportamento a tempo di gioco.

## Avvio e stato

```bash
cd /opt/generic_projects/chess-coach/experiments/human-policy
make test-distillation
make distillation-pilot
make distillation-status
```

Il budget predefinito è esplorativo: 2.000 posizioni train, 400 posizioni del
campione validation per il confronto con l'insegnante, 100 passi per variante,
batch 64, 2 thread per Maia, GPU CUDA per lo studente. La validation umana usa
tutte le 6.877 posizioni della fascia 600–1500. Il budget può essere cambiato
con i parametri di `distillation.py --help`, usando una **nuova** directory di
output il cui nome inizi con `distillation-` sotto `runs/`.

Il programma controlla gli hash di dati, checkpoint, modello e mappatura Maia,
codice dell'insegnante e codice del pilota. Se cambiano parametri o sorgenti,
rifiuta di riprendere quella directory. Un blocco impedisce due avvii sullo
stesso output. L'etichettatura riprende dall'ultimo batch scritto; ogni braccio
completato è conservato. Un braccio interrotto prima del checkpoint finale
riparte dall'inizio, con lo stesso seed, non da metà ottimizzatore.

## Risultati e limiti

`manifest.json` e `selection.json` documentano le condizioni. `teacher-labels.json`
contiene le probabilità sulle mosse legali. `human.pt`, `mixed.pt`, `teacher.pt`
sono candidati separati e compatibili con la policy sperimentale; **non** sono
checkpoint accettati né vengono caricati automaticamente. `comparison.json` e
`RAPPORTO.md` contengono top-k, NLL, divergenza dall'insegnante e confronto
tattico sul piccolo campione usato nel pilota precedente.

La divergenza più bassa indica soltanto maggiore somiglianza all'insegnante. Le
perdite in centipawn sono valutazioni di Stockfish, non materiale necessariamente
perso, e non sono percentuali di partite perse. Il caso personale della donna è
già noto; non misura generalizzazione. La validation è stata già usata per lo
sviluppo dei checkpoint precedenti. Il campione tattico è piccolo e stratificato.

Prima di selezionare un nuovo avversario occorrono un test indipendente, partite
complete con colori e seed variati, una valutazione esplicita per fascia bassa,
misure di tempo e verifiche sui diritti dei pesi derivati. Nessuna promozione,
modifica del ledger mensile o avvio del servizio di gioco avviene nel pilota.
