# Giudizio delle mosse: franchigia e matto mancato

Data: 3 novembre 2026. Descrive la regola unica con cui revisione, Puzzle, pratica libera, diagnosi ed Esame di prova giudicano una mossa rispetto alla migliore di Stockfish (`review_loss` e `missed_mate` in `backend/engine.py`, `accepted` in `backend/mistakes.py`).

## Perché

Fino al 3 novembre 2026 la perdita era la differenza grezza in centesimi tra la migliore mossa e quella giocata. In una posizione già decisa quella differenza è soprattutto rumore della ricerca. Nella partita #100 (dal puzzle della #37, mossa 32 del Bianco) 32. Ne2 era stata accettata dal puzzle e poi segnata come errore grave dalla revisione: Stockfish aveva dato +12,5 a Ne2 e +18,3 a Re1+, e il puzzle quel giorno aveva trovato valori vicini fra loro. Entrambe le mosse vincono: con una ricerca profonda Ne2 è matto in 11, e la migliore (Nc7) matto in 4.

## La regola

- **Franchigia.** Prima di fare la differenza, ogni valutazione viene limitata a ±600 centesimi (`OUTCOME_CAP_CP`); ogni matto, a favore o contro, vale ±600. Oltre +6 la partita è vinta e un margine maggiore non cambia nulla; sotto −6 è persa, e 3 metri d'acqua o 1200 metri pari sono per chi non sa nuotare. La perdita misura solo quanto la mossa sposta la partita verso un esito diverso.
- **Soglie invariate** sulla nuova scala: imprecisione da 80 a 179 centesimi, errore da 180, errore grave (?? nel riepilogo di Rivedi) da 300. Nei Puzzle e nell'Esame la mossa è accettata se perde meno di 70.
- **Matto mancato.** Se c'era un matto in 1 o 2 mosse e la mossa giocata non porta a sua volta a un matto in 1–2, la decisione è un *Matto mancato* (#?), anche se la posizione resta vinta. È una categoria a sé: non conta fra le decisioni senza perdite, le imprecisioni o gli errori. Nei Puzzle una mossa che manca un matto in 1–2 è rifiutata. Diventa puzzle con il tema *Riconoscere il matto*.

| Prima (migliore) | Dopo (giocata) | Perdita | Giudizio |
|---|---|---|---|
| +18,3 | +12,5 | 0 | buona scelta |
| matto in 4 | +13,7 | 0 | buona scelta |
| −12 | −18 | 0 | buona scelta |
| +8 | +2 | 400 | errore grave |
| +1 | −7 | 700 | errore grave |
| matto in 1 | +15 | 0 | matto mancato |

## Come si mostrano i punteggi

Stockfish e le regole lavorano dal punto di vista di chi muove (positivo = buono per chi deve giocare): così una perdita
si calcola nello stesso modo per i due colori. **Ciò che si mostra** è invece sempre sulla scala oggettiva: positivo se è
avanti il Bianco, negativo se è avanti il Nero, chiunque muova. La conversione si fa solo nel testo:

- interfaccia: `web/src/evalText.ts` (`objectiveScore(score, chi muove)`, `SCORE_NOTE`), usata da lezioni, «Segui la
  partita», Rivedi, Trova un’alternativa, confronto e storico degli errori, Blunder prevention, diagnosi e tutor dello
  Studio;
- backend: `engine.objective(score, white)` e `LOSS_NOTE`, per i testi generati (spiegazioni, quiz, regole).

Dicitura standard, la stessa ovunque: «Perdere 1,20 significa, per il Bianco, scendere di 1,20 (da 0,00 a −1,20); per
il Nero, salire di 1,20 (da 0,00 a +1,20).» Le soglie delle regole si scrivono per i due colori («col Bianco non sotto
−1,00, col Nero non sopra +1,00»). I matti: «matto del Bianco in 3», «matto del Nero in 3».
I prompt del tutor DeepSeek restano dal punto di vista di chi muove: sono istruzioni interne, non testo mostrato.

## Dati già salvati

Le analisi salvate vengono rivalutate alla lettura (`load_analysis`): perdita, matto mancato ed etichetta seguono la regola attuale, e così l'elenco dei momenti critici. Gli esercizi già creati restano nel database. Quelli nati in una posizione già decisa (come il puzzle della #37) ora accettano qualunque mossa che resti vincente e non manchi un matto breve.

## Cosa non cambia

Blunder prevention e *Trova un'alternativa* hanno criteri propri, già legati alla soglia di sicurezza (−1,00) e alla probabilità di vittoria: non usano questa regola.

## Limiti noti

La franchigia elimina il rumore solo nelle zone sature. Nella zona in bilico, fra −6 e +6, la stessa mossa può ancora ricevere giudizi diversi in momenti diversi. Ci sono tre ragioni: le ricerche sono brevi (10.000–80.000 nodi) e con due thread non sono ripetibili, revisione e puzzle usano procedure diverse (`compare_candidates` contro `compare`), e un verdetto già dato non viene salvato né riusato. Restano da fare un giudice unico ripetibile e i verdetti salvati per coppia posizione–mossa.

Prove: `tests/test_review_loss.py`, `tests/test_learning.py`, `web/tests/review-summary.spec.ts`.
