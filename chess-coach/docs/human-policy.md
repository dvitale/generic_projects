# Modello predittivo locale — 20 ottobre 2026

Il modulo è in [`../experiments/human-policy`](../experiments/human-policy/README.md).
Il manuale del modulo contiene configurazione, comandi, provenienza dei dati,
limiti sperimentali e prossime tappe.

- Input: FEN completa e rating Lichess rapid del giocatore al tratto.
- Output: prime 5 mosse legali, probabilità non rinormalizzate e massa residua.
- Rete: Transformer piccolo, condizionamento numerico del rating e bias spaziale.
- Nessuna ricerca nell'albero delle continuazioni e nessun uso del database utente.
- Dataset pubblico: campione limitato dell'archivio standard rated Lichess.
- Le mosse umane costituiscono i bersagli, inclusi gli errori.
- Stato: prototipo da validare; non sostituisce Maia nell'applicazione.

Verifiche: `make test` nella directory del modulo; prove reali brevi con
`make train` e `make resume`. I rapporti delle esecuzioni sono in `runs/`,
esclusi da Git insieme a dataset, librerie e pesi.

## Archivio mensile completo — 21 ottobre 2026

Download autorizzato del settembre 2026: 29.224.520.887 byte compressi.
Il laboratorio offre `make download-month MONTH=2026-09` per avvio/ripresa
e `make month-status MONTH=2026-09` per lo stato. I dati restano in
`experiments/human-policy/data/monthly/`, esclusi da Git e dal deploy.

Il modulo controlla lo spazio fisico Windows oltre a quello virtuale WSL,
mantiene almeno 10 GiB liberi, verifica la ripresa HTTP e il checksum SHA256
ufficiale prima di dichiarare l'archivio completo. Non crea il PGN decompresso
e non avvia automaticamente estrazione o training. Otto nuove prove coprono
download, ripresa, interruzione, spazio insufficiente e checksum errato.

Il trasferimento avviato continua in un processo locale indipendente dalla chat;
lo stato e il log consentono di verificarne l'esito. Nessuna integrazione nell'app.

## Training sequenziale per mesi — 21 ottobre 2026

Il laboratorio ora dispone di `make cycle MONTHS=2026-09 CYCLE_STEPS=10000`
e `make cycle-status`. Il ciclo concatena download verificato, campionamento
distribuito sull'intero mese, training con replay, confronto e rimozione protetta
dell'archivio. Dettagli e limiti in
[`CICLO-MENSILE.md`](../experiments/human-policy/CICLO-MENSILE.md).

Fino a un milione di posizioni per mese, memoria di 100.000 posizioni train,
20% dei campionamenti dalla memoria quando disponibile, validation/test fissi,
checkpoint e campioni dei due mesi più recenti. Il test non viene valutato.
Un nuovo mese conserva pesi e ottimizzatore; una ripresa sullo stesso mese
conserva anche i generatori casuali e richiede gli stessi fingerprint.

La cancellazione richiede qualità accettata e coerenza degli hash di tutti gli
artefatti permanenti; fallimenti o regressioni conservano l'archivio. Gli archivi
grezzi su questo PC sono collegati a una cartella Windows del solo laboratorio,
per recuperare effettivamente lo spazio fisico quando vengono eliminati.

La procedura è stata verificata con due mesi sintetici e prove di interruzione,
replay, holdout e cancellazioni protette. Non rappresenta ancora un risultato
di training sul mese reale completo. Nessuna integrazione in SparringMate.

## Uso in Gioca — 23 ottobre 2026

Il checkpoint del ciclo mensile può rispondere come avversario in Gioca, in alternativa a Maia, tramite
`experiments/human-policy/serve.py` (`make experimental`) e l'opzione
`SPARRINGMATE_EXPERIMENTAL_ENGINE`. Solo sul PC; Puzzle, Blunder prevention, tutor e stima del profilo
restano invariati. Dettagli in [`motore-sperimentale.md`](motore-sperimentale.md).

## Pilota tattico isolato — 24 ottobre 2026

Aggiunti audit della codifica sui dati reali, holdout tattico distinto dalle
posizioni personali note e tre bracci di addestramento controllato. Le etichette
Stockfish sono usate solo per valutazione; il target resta la mossa umana.
Procedura, comandi, ripresa e criteri in [TATTICA.md](../experiments/human-policy/TATTICA.md).
Il servizio di gioco e il registro dei checkpoint accettati non vengono aggiornati.

Esito: [rapporto del primo pilota tattico](../experiments/human-policy/RISULTATI-TATTICA.md).
Tre bracci completati e quattro partite offline; nessun candidato promosso.
