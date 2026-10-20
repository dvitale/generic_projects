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
