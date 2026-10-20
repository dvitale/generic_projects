# Diagnosi prima della soluzione

Data: 18 ottobre 2026. Descrive la diagnosi che compare quando chiedi la soluzione in **Puzzle**, **Problemi** e **Blunder prevention**, come viene classificata e dove si leggono i risultati.

## Perché

"Non ho trovato la mossa" può avere cause diverse: la mossa buona non era fra le candidate, oppure l'avevi vista e scartata per un calcolo sbagliato, oppure davi la posizione per persa, o temevi una minaccia che non c'era. Rispondere a tre domande prima di vedere la soluzione permette di separare questi casi e di seguirli nel tempo.

## Il flusso

Il pulsante **Mostra soluzione** (in Blunder prevention **Mostra una mossa sicura**) apre il riquadro **Cosa vedevi?** al posto della soluzione:

1. **Come valuti la posizione?** Le cinque fasce di *Valuta la posizione* (forte svantaggio … forte vantaggio), quanto sei sicuro e, se è la tua impressione, **Mi sembra già persa**.
2. **Quale minaccia temi?** Si indica muovendo un pezzo dell'avversario su una scacchiera dedicata (la stessa posizione con il tratto all'avversario), oppure **Non vedo minacce**. Sotto scacco la domanda non compare.
3. **Quale mossa avevi considerato e scartato?** Facoltativa: si muove sulla scacchiera e si sceglie il motivo (materiale, matto o attacco, calcolo incompleto, altro). Le mosse già provate e respinte nella sessione contano da sole fra le candidate: il riquadro le elenca, la domanda diventa **Quale altra mossa…?** e la scacchiera offre solo le mosse non ancora provate. Il server le legge dai tentativi salvati (nei Problemi, quelli della mossa in corso).

**Confronta e mostra la soluzione** salva la diagnosi e poi mostra la soluzione come prima. **Salta: mostra subito** mostra la soluzione senza diagnosi, ed è sempre disponibile, anche se il server non risponde. **Torna alla posizione** chiude il riquadro e permette di continuare a cercare.

La diagnosi non cambia rating, successi indipendenti né calendario dei ripassi: arriva quando l'esercizio è già fallito o assistito. Una sola diagnosi per sessione; le richieste ripetute restituiscono quella salvata.

## Classificazione

Decide Stockfish con regole fisse, non l'LLM. Il server ricostruisce la posizione dalla sessione aperta (non accetta una FEN dal browser) e analizza a 150.000 nodi per ricerca. Ci sono due assi.

**Ricerca**, sempre una delle due:

| Categoria | Regola |
|---|---|
| Soluzione non vista | Nessuna candidata, oppure la candidata non soddisfa il criterio della modalità. Le mosse provate e respinte compaiono nella spiegazione («Hai provato Qg8+, che non risolve…») ma non cambiano la categoria |
| Vista ma scartata | La candidata soddisfa il criterio della modalità: l'avevi trovata e l'hai respinta |

Il criterio è quello della modalità: nei Problemi la mossa della soluzione o qualsiasi matto; nei Puzzle una perdita inferiore a 0,70 rispetto alla migliore; in Blunder prevention almeno −1,00 senza matto contro.

**Lettura della posizione**, una o più:

| Categoria | Regola |
|---|---|
| Troppo pessimista | La tua fascia è almeno due gradini sotto quella di Stockfish, oppure la davi per persa con valutazione ≥ −1,00 |
| Troppo ottimista | La tua fascia è almeno due gradini sopra |
| Minaccia non vista | Dando la mossa all'avversario (mossa nulla), la sua risposta migliore toglie almeno 2,00 e lascia al massimo +1,00, e la minaccia indicata non è concreta |
| Minaccia fantasma | La minaccia indicata, giocata dopo la mossa nulla, non toglie almeno 1,50 |
| Lettura corretta | Nessuno dei casi precedenti: il punto debole è il calcolo della sequenza |

Le fasce sono quelle di *Valuta la posizione*: equilibrio fra −1 e +1, forte vantaggio o svantaggio da ±3. Quando la posizione è un matto forzato, qualunque minaccia che lo cancella risulta concreta, anche se il risultato resta favorevole: per esempio, nel problema 007mr la spinta a3 del Bianco apre la casa a2 e smonta il matto sulla traversa.

## Dati

Tabella SQLite `failure_diagnoses`, una riga per sessione (`UNIQUE(kind, session_id)`): modalità, esercizio, FEN, risposte grezze (`answer`), prove del motore (`evidence`), categoria di ricerca, categorie di lettura, temi Lichess (solo Problemi) e `rule_version`. Le risposte grezze permettono di riclassificare lo storico quando cambiano le regole. Fa parte del backup SQLite e non viene inviata a servizi esterni.

API locali:

- `POST /api/diagnoses/context`: posizione, mosse legali del giocatore e dell'avversario (con SAN) e l'eventuale diagnosi già salvata. Richiede la sessione aperta.
- `POST /api/diagnoses`: salva e classifica. Risponde 409 se la sessione è già chiusa e 422 se una mossa non è legale.
- `GET /api/diagnoses/summary`: riepilogo per Progressi.

## Monitoraggio

**Progressi → Diagnosi degli errori** mostra:

- la frequenza di ogni categoria nelle ultime 30 diagnosi, confrontata con le 30 precedenti;
- la categoria più frequente, con un'indicazione su cosa allenare;
- la calibrazione: per ogni livello di sicurezza, quante volte la fascia indicata coincideva con quella di Stockfish;
- per i Problemi, i temi Lichess con almeno tre diagnosi, divisi fra soluzione non vista, scartata e lettura errata.

## Limiti

- Le risposte arrivano dopo l'errore e possono essere razionalizzate.
- Con meno di 20–30 diagnosi le percentuali oscillano molto.
- La mossa nulla misura cosa farebbe l'avversario con una mossa in più. È un'approssimazione: in alcune posizioni (zugzwang, scacco) la domanda non ha senso o non viene posta.
- Stockfish lavora a budget limitato; le soglie sono convenzioni didattiche, non verità.

## Verifiche

```bash
.venv/bin/python -m pytest tests/test_diagnosis.py -q
cd web && npm run build && npx playwright test tests/problems.spec.ts tests/puzzle-flow.spec.ts
```

I test backend coprono la candidata vista e scartata, il pessimismo, la minaccia concreta (…Ra6+ che infilza re e donna in Blunder prevention) e quella fantasma, la diagnosi unica per sessione, il rifiuto di sessioni chiuse e le mosse già provate nelle tre modalità. I test browser compilano la diagnosi in un Problema e controllano il riepilogo, e in un Puzzle verificano che il tentativo fallito compaia fra le candidate.
