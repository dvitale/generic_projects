# SparringMate: il motore umano sperimentale

Documento per seguire l'esperimento senza conoscere il codice. Aggiornato il 1° novembre 2026.

## Perché esiste

Vuoi un avversario che produca situazioni di allenamento credibili e ti aiuti a
individuare e correggere gli errori che commetti contro Maia online. Il motore
sperimentale prova a prevedere una mossa umana data una posizione e un rating.
Il numero impostato, per esempio 600, non è ancora una forza di gioco calibrata.

Il risultato importante è migliorare nelle tue partite, non vincere contro un
modello che regala spesso i pezzi. Il modello è un avversario: l'analisi, gli
esercizi e le spiegazioni del tutor sono altre funzioni di SparringMate.

## Come lavora

La rete riceve la posizione e il rating del giocatore al tratto; assegna una
probabilità a ogni mossa legale. Il sistema estrae una mossa secondo quelle
probabilità. Per questo una mossa meno probabile può essere giocata; anche la
prima scelta può essere sbagliata. Non c'è un filtro Stockfish nella rete.

La versione del ciclo di agosto ha circa 865.000 parametri e usa mosse di
partite rapid Lichess. Il dataset conserva la FEN e il rating del giocatore al
tratto, ma non necessariamente l'intera storia, i tempi o il rating avversario.
Una FEN isolata non ricostruisce la storia delle ripetizioni.

## Cosa abbiamo fatto e cosa abbiamo imparato

| Prova | Risultato | Che cosa significa |
|---|---|---|
| Due cicli mensili, settembre e agosto 2026 | Il secondo è stato specializzato sui rating 600–1500; sulla stessa validation di 6.877 posizioni la prima scelta coincide con la mossa umana nel 37,81%, contro 35,22% della versione precedente | Un progresso nella previsione su quel campione; non una stima Elo o una garanzia di gioco migliore |
| Pilota tattico | Tre brevi varianti hanno mantenuto o migliorato la previsione umana, senza risolvere il problema delle minacce | Altro training e semplici mappe di attacco non sono bastati in quella prova |
| Partite di confronto | La variante con mappa degli attacchi ha ottenuto una patta e tre sconfitte contro il riferimento | Quattro partite sono solo una diagnosi preliminare |
| Confronto con Maia online | Nella posizione del tuo matto Maia mostrava circa 81,2% per la mossa vincente e il modello sperimentale circa 35,7% | La rete può riconoscere un matto ma assegnargli probabilità troppo bassa |
| Donna in presa | Nella posizione esaminata Maia online indicava circa 19,7% per la cattura che perde la donna; lo sperimentale 36,6% | Anche Maia può proporre quell'errore; la probabilità differiva nella posizione osservata |

Le percentuali online provengono dalla schermata di analisi, non da molte partite
replicate. Una singola prova con posizione FEN ha prodotto il matto. I confronti
non dimostrano che i modelli ricevano sempre la stessa storia o gli stessi input.
Maggiori dettagli e limiti: [RISULTATI-TATTICA.md](RISULTATI-TATTICA.md) e
[CICLO-MENSILE.md](CICLO-MENSILE.md).

## Proposta: imparare anche da Maia, tramite distillazione

Oggi il modello studente impara principalmente dalla singola mossa effettivamente
giocata nella partita umana. Nella distillazione un modello insegnante assegna
probabilità alle mosse legali: lo studente impara da queste probabilità e/o dalla
mossa umana. Dopo l'addestramento resta una sola rete a scegliere le mosse;
non si aggiunge un correttore tattico in partita.

La prima prova confronterà tre varianti, partendo dallo stesso checkpoint e usando
gli stessi esempi, passi, batch, seed e ottimizzatore iniziale:

| Variante | Obiettivo | Domanda |
|---|---|---|
| A — umana | Solo la mossa umana registrata | Quanto migliora con altro training normale? |
| B — mista | 50% mossa umana, 50% distribuzione dell'insegnante | I due segnali insieme migliorano il risultato? |
| C — insegnante | Solo distribuzione dell'insegnante | Quanto riesce lo studente ad approssimare l'insegnante? |

Il 50% è una scelta iniziale da confrontare, non una proporzione dimostrata.
L'insegnante iniziale previsto è il modello Maia ONNX già presente localmente in
SparringMate. Riceve la FEN e due rating. Il nostro dataset conserva solo quello
del giocatore al tratto: per il primo pilota impostiamo anche il rating avversario
allo stesso valore e registriamo l'assunzione. L'insegnante locale non è stato
dimostrato identico al sito maiachess.com. Perderemmo inoltre il contesto storico
non presente nel dataset. Nessuna partita personale viene inviata online.

La distribuzione viene conservata per **tutte** le mosse legali, senza troncarla
alle prime 16 o 32. La corrispondenza delle mosse viene controllata per bianco,
nero, promozione, arrocco ed en passant. Un'etichetta non valida blocca la prova.
L'insegnante può insegnare anche i propri errori: la mossa umana rimane un
termine separato nel confronto, e nessuna variante viene promossa automaticamente.

## Come stabilire se è utile

- **Corrispondenza umana:** top-1/top-3/top-5 e NLL sulla stessa validation,
  anche per fasce, in particolare 600–799. I numeri non sono Elo.
- **Somiglianza all'insegnante:** differenza fra le distribuzioni sulle stesse
  mosse legali. I risultati online osservati restano un confronto distinto.
- **Tattica:** probabilità dei gravi errori, matti immediati e catture vantaggiose;
  la tua posizione della donna è un caso noto, non un test indipendente.
- **Gioco:** confronto successivo in più partite, colori alternati e seed diversi.
  Nessuna affermazione di forza o beneficio didattico da poche partite.
- **Risorse:** tempo per etichettare, tempo e memoria GPU, latenza dello studente.

Si useranno soltanto esempi train controllati contro il holdout congelato. La
validation già usata per selezionare versioni precedenti serve allo sviluppo,
non è un test finale indipendente. Il test finale resta non valutato. Campioni
per partita, fasce di rating e posizioni simili saranno esplicitati nel rapporto.

## Stato e confini

Il pilota vive in `experiments/human-policy`, con dati, cache, log e pesi sotto
`runs/distillation-*`, esclusi da Git. Non modifica il ledger mensile o il
servizio usato in partita, non scarica un nuovo mese e non usa il database di
produzione. I candidati non vengono attivati automaticamente. Prima di
distribuire pesi o codice derivati dall'insegnante occorre verificare le licenze
e la provenienza dei singoli artefatti.

Codice, comandi, test e risultati del pilota verranno descritti in
[DISTILLAZIONE.md](DISTILLAZIONE.md). Un esperimento breve verifica il metodo;
eventuali conclusioni sulla forza richiedono un confronto più ampio.
