# Visualizzazione

La sezione **Visualizza** allena il calcolo a mente: una posizione di una tua partita, le mosse che seguono scritte ma
non giocate sulla scacchiera, e una domanda sulla posizione a cui portano. È l'idea 3 del piano
([PLAN-indizi-puzzle.md](PLAN-indizi-puzzle.md)), dalle domande verificabili del paper Queen (arXiv 2610.03695,
appendice D).

## Come funziona

- La posizione viene da una partita a caso fra le tue (escluse le copie di revisione), da una semimossa a caso dopo
  la 16ª: le mosse sono le tue e quelle del tuo avversario, non teoria imparata a memoria.
- La linea sono le semimosse successive della stessa partita. La lunghezza parte da 2 e si adatta: cresce di una
  dopo 3 risposte giuste di fila a quella lunghezza, cala di una dopo un errore, fra 1 e 8 (`backend/visualization.py`,
  `level`, ricalcolata ogni volta dalla storia delle risposte).
- La domanda riguarda la posizione finale e la risposta la calcola python-chess, senza motore:
  - **che cosa c'è in una casa** toccata dalla linea (arrivo o partenza di una mossa), fra il pezzo giusto, pezzi
    che stavano su quelle case o le hanno attraversate, e «Casa vuota»;
  - **quanti pezzi avversari attaccano** un pezzo che si è mosso nella linea;
  - **quante catture legali** ha chi deve muovere;
  - **se chi deve muovere è sotto scacco**;
  - se lo è, **se è matto**, oppure **quale mossa è legale** fra una legale e mosse che lascerebbero il re sotto
    scacco, tutte nella stessa notazione (`Re1-d1`) perché la forma non tradisca la risposta.
- La risposta resta sul server finché non scegli (`visualization_questions`); dopo la scelta vedi la spiegazione e
  la posizione finale, con **Partenza** / **Dopo la linea** per confrontarle.

## API

- `POST /api/visualization/next`: nuova domanda (`id`, `fen`, `orientation`, `line`, `plies`, `question`, `options`).
  409 se non c'è una partita abbastanza lunga.
- `POST /api/visualization/{id}/answer` con `{"choice": n}`: esito, risposta, spiegazione, posizione finale e
  riepilogo. 409 se la domanda ha già una risposta.
- `GET /api/visualization/summary`: lunghezza attuale, ultime 20 risposte, risultati per lunghezza.

## Limiti

- Le domande sono semplici per costruzione: misurano se tieni la posizione, non se valuti bene.
- I risultati non entrano ancora nelle **Lacune ricorrenti**: servirebbero per distinguere la lacuna di calcolo
  («perdo il filo» sulle linee lunghe) da quella tattica, come previsto dal piano.
