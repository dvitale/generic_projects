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
