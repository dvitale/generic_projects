# Lacune ricorrenti e percorsi di studio

Quando non trovi una mossa, il problema raramente è quella posizione: di solito è un tipo di mossa che non cerchi o uno schema che non riconosci. SparringMate raccoglie i tuoi risultati di Puzzle e Problemi, riconosce i gruppi di posizioni in cui ti blocchi più spesso del previsto e, per una lacuna confermata, propone un percorso di studio. Le classificazioni sono regole fisse su dati verificati (Stockfish, temi Lichess, rating); il tutor non decide nulla. Codice: `backend/gaps.py`, interfaccia `web/src/GapsProgress.tsx` e `web/src/StudyPath.tsx`.

## Da dove vengono i dati

- **Puzzle (dalle tue partite):** ogni esercizio ha il tipo di soluzione classificato da Stockfish (`exercises.solution`: forzante, tranquilla con una minaccia, profilassi, miglioramento) e un indicatore di finale (al massimo 4 pezzi oltre a re e pedoni). La classificazione si calcola alla prima richiesta di indizio o di soluzione, in background dopo una soluzione trovata, e, per gli esercizi rimasti senza, in background all'apertura di Progressi: la scheda dice quanti ne mancano. Riuscita significa: risolto al primo tentativo, senza indizi né soluzione. L'atteso è la tua media di riuscita nei Puzzle.
- **Problemi (Lichess):** il gruppo è ciascun tema Lichess del problema, esclusi quelli che non dicono cosa bisognava vedere (lunghezza, esito, provenienza, fase di mediogioco o apertura, `mate` generico). Riuscita è il risultato valutato per il rating. L'atteso è la probabilità Elo di risolverlo dati il tuo rating di allora e quello del problema: un tema difficile non sembra una lacuna solo perché i suoi problemi hanno rating alto.

Contano le ultime 300 sessioni di ciascuna fonte. I problemi giocati dentro un percorso non contano, perché nella serie a tema sai già cosa cercare.

## Quando è una lacuna

Per ogni gruppo: casi, risolti, tasso di riuscita e atteso medio.

| Stato | Condizione |
| --- | --- |
| Da osservare | almeno 3 casi e riuscita almeno 20 punti sotto l'atteso |
| Confermata | almeno 6 casi, almeno 3 non risolti, riuscita almeno 20 punti sotto l'atteso |

Tre famiglie, sempre dichiarate:

- **Metodo di ricerca:** tipi di soluzione dei Puzzle e i temi `quietMove`, `defensiveMove`, `long`, `veryLong`. Non manca uno schema: manca una domanda nella ricerca.
- **Motivo tattico:** gli altri temi Lichess (forchetta, inchiodatura, deviazione…).
- **Teoria (ipotesi):** finali con poco materiale nei Puzzle e i temi di finale Lichess. È una lettura basata su fase e materiale: dentro un finale la causa può essere tattica.

Una lacuna superata con un percorso riparte da zero: contano solo i casi successivi alla chiusura.

## Il percorso di studio

Uno solo alla volta (`study_paths`). Il tema Lichess allenato è il tema stesso per i Problemi; per i Puzzle è il più vicino al tipo di soluzione: `quietMove` per le mosse tranquille, `defensiveMove` per la profilassi, `long` per le soluzioni forzanti (calcolo di sequenze). Il miglioramento posizionale non ha problemi Lichess adatti: la scheda rimanda a Trova un'alternativa. I finali usano `endgame`.

1. **Lezione:** come si riconosce lo schema e la domanda da farsi (testi fissi per tema, in `LESSONS`), con una delle tue posizioni non risolte e la sua soluzione.
2. **Serie a tema:** 8 problemi con il tema, il primo 200 punti sotto il tuo rating, poi 50 in più a ogni problema fino a 100 sopra. Si preferiscono i problemi mai visti.
3. **Serie mista:** 8 problemi intorno al tuo rating; 4, in posizioni casuali, portano il tema, ma nessuno lo annuncia. È superata se i problemi con il tema sono risolti almeno quanto prevede il rating, meno 10 punti; altrimenti si torna alla serie a tema (nuovo giro).
4. **Ripasso:** dopo 2 giorni. Per una lacuna dei Problemi tornano le posizioni sbagliate da cui è nata (fino a 3), poi il percorso si chiude come superato. Per una lacuna dei Puzzle quegli esercizi tornano fra i Puzzle da ripassare alla stessa data e il percorso si chiude subito.

**Problemi liberi** mette da parte il percorso senza abbandonarlo; **Abbandona il percorso** lo chiude senza esito. Con meno di 20 problemi del tema nel database importato, la lezione avvisa che alcuni si ripeteranno.

## API

- `GET /api/gaps`: lacune (confermate e da osservare), percorso attivo, lacune superate, soglie.
- `POST /api/study-paths` con `{"gap": "theme:fork"}` (chiavi `kind:<tipo>`, `theme:<tema>`, `phase:endgame`): crea il percorso. 409 se ce n'è già uno, se la lacuna non è confermata o non ha problemi adatti, se il database dei problemi manca.
- `GET /api/study-paths/active`: percorso attivo e ultimo percorso chiuso.
- `POST /api/study-paths/{id}/start`, `POST /api/study-paths/{id}/abandon`.
- `POST /api/problems/next` con `{"path": id}`: vedi [problemi.md](problemi.md#percorso-di-studio).

## Limiti

- Pochi casi danno stime instabili: le soglie sono volutamente basse per dare un segnale presto, e la scheda mostra sempre i numeri grezzi.
- L'atteso dei Puzzle è la tua media, non una difficoltà per posizione: i Puzzle non hanno un rating.
- Il motivo tattico degli esercizi dalle tue partite non viene riconosciuto (solo il tipo di soluzione): resta da fare, vedi [PLAN-indizi-puzzle.md](PLAN-indizi-puzzle.md).
- La mappatura dei tipi di soluzione sui temi Lichess è un'approssimazione, in particolare profilassi → mossa difensiva.

## Verifiche

```bash
.venv/bin/python -m pytest tests/test_gaps.py -q
cd web && npm run build && npx playwright test tests/problems.spec.ts tests/study-path.spec.ts
```
