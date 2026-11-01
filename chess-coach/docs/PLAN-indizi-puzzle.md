# Piano: dagli indizi dei Puzzle a un percorso di studio

Obiettivo: quando il giocatore resta bloccato su un puzzle, SparringMate non deve limitarsi a ripetere il metodo generale
(«cerca scacchi, catture e minacce») né mostrare subito la soluzione. Deve dire che tipo di mossa manca, poi riconoscere
le lacune che si ripetono e proporre uno studio mirato per superarle.

Le classificazioni le decide Stockfish con regole fisse (`backend/diagnosis.py`, funzione `solution`); il tutor non decide nulla.

## Fase 1 — indizi a scala nel puzzle bloccato (fatta)

Vedi `docs/diagnosi-errori.md`, sezione «Indizi dei Puzzle». In breve:

- livello 1, **tipo di mossa**: forzante (scacco, cattura, promozione), mossa tranquilla con minaccia, profilassi,
  miglioramento posizionale;
- livello 2, **dove guardare**: il pezzo che muove, evidenziato sulla scacchiera (per la profilassi anche l'idea dell'avversario);
- il tipo di soluzione resta registrato nella sessione (`puzzle_sessions.solution`) ogni volta che il giocatore chiede
  un indizio o la soluzione: è il dato da cui partono le fasi 2 e 3.

## Fase 2 — riconoscere la lacuna (fatta, tranne un punto)

Realizzata il 1° novembre 2026: vedi `docs/lacune-studio.md`. Resta da fare il riconoscimento del motivo tattico negli esercizi dalle tue partite (punto 1, secondo elenco).

1. **Registrare anche il motivo tattico**, oltre al tipo di mossa.
   - Problemi Lichess (`backend/problems.py`): il motivo c'è già nei temi (`fork`, `pin`, `deflection`, `overloading`,
     `quietMove`, `endgame`…). Servono il pulsante «Chiedi un indizio» anche lì e la stessa registrazione di
     `solution` per sessione.
   - Esercizi dalle partite: il motivo va riconosciuto dalla posizione. È la parte più costosa e meno affidabile:
     da fare per ultima, solo per motivi verificabili con regole chiare (attacco doppio, inchiodatura, pezzo sovraccarico).
2. **Aggregare per tipo e per motivo**: per ciascuno, puzzle visti, risolti senza aiuto, risolti con indizio, soluzione
   vista. Una lacuna è *confermata* solo con un campione minimo (indicativamente ≥ 6 casi e tasso di riuscita
   nettamente sotto la media del giocatore), altrimenti si mostra come «da osservare».
3. **Distinguere tre famiglie**, dicendo sempre quanto è certa la lettura:
   - lacuna di **metodo**: cerca solo mosse forzanti, fallisce le mosse tranquille e la profilassi;
   - lacuna **tattica**: non riconosce un motivo preciso;
   - lacuna **teorica**: finali con poco materiale, tecniche note (opposizione, Lucena, Philidor). Qui la lettura è
     un'ipotesi basata su fase e materiale.
4. Mostrare le lacune in una scheda dei progressi (accanto a `DiagnosisProgress`).

## Fase 3 — percorso di studio per la lacuna (fatta)

Realizzata il 1° novembre 2026: vedi `docs/lacune-studio.md`. Differenze dal piano: la lezione usa testi fissi per tema e una posizione sbagliata dal giocatore; il superamento confronta la serie mista con l'atteso Elo; per le lacune dei Puzzle il ripasso riprogramma gli esercizi originali; il percorso vive in Problemi e Progressi, non nel Piano di allenamento.

Per una lacuna confermata, SparringMate propone un blocco mirato, dentro il Piano di allenamento esistente:

1. **Lo schema in breve**: cos'è, come si riconosce, un esempio commentato.
2. **Serie a tema** di problemi Lichess con quel tema, prima un po' sotto il livello del giocatore (fissare lo schema),
   poi in salita.
3. **Serie mista senza etichetta**: sapere il tema in anticipo falsa la prova; il test vero è riconoscerlo da solo.
4. **Ripasso del puzzle originale** con la ripetizione dilazionata già in uso.
5. Chiusura della lacuna quando il tasso di riuscita nella serie mista torna in linea con la media.

## Da fare

- Motivo tattico negli esercizi dalle tue partite (attacco doppio, inchiodatura, pezzo sovraccarico), con regole verificabili: permetterebbe lacune per motivo anche nei Puzzle e indizi di livello «motivo» come nei Problemi.
- Verificare sui dati reali, dopo qualche settimana d'uso, se le soglie (3/6 casi, 20 punti) producono lacune sensate.

## Come riprenderlo

In una nuova sessione: «riprendi il piano in `docs/PLAN-indizi-puzzle.md`, punti da fare».
