# Stima Elo della partita

In **Rivedi → Stima Elo della partita** si confrontano le mosse del colore scelto con le probabilità del modello Maia3 locale. Non serve DeepSeek, né una chiamata esterna. Il risultato è salvato nel database locale con la versione della partita.

È una **stima sperimentale di compatibilità con i profili Maia**, non un rating FIDE, Chess.com o Lichess, una performance agonistica o una diagnosi delle competenze. Il modello predice mosse umane: il livello che meglio spiega una sequenza non coincide necessariamente con la forza del giocatore. Aperture memorizzate, ritmo di gioco, aiuti, ripetizioni e singole scelte inconsuete possono influenzare molto il risultato. La procedura non è stata calibrata su un campione indipendente di giocatori.

## Metodo riproducibile

1. Ricostruire la partita dal FEN iniziale. Considerare solo le mosse del giocatore con almeno due alternative legali; nei Drill escludere la sequenza preparatoria.
2. Richiedere almeno 10 decisioni. Se sono più di 40, selezionare 40 posizioni a indici equidistanti, includendo prima e ultima. Si limita così il lavoro nel browser.
3. Confrontare 11 livelli: 600, 800, …, 2600. Tenere fisso il livello avversario: quello configurato per Maia; per i PGN, 1500 come ipotesi esplicitata nell’interfaccia (gli header Elo non vengono attualmente importati).
4. Per ciascun livello sommare `log(max(P(mossa giocata | posizione, livello, avversario), 1e-12))`. Le probabilità sono quelle di Maia normalizzate sulle mosse legali, senza campionare una risposta del bot.
5. Mostrare il livello con somma maggiore. Se lo scarto tra massimo e minimo è inferiore a 2, mostrare **Livello non distinguibile** senza un Elo puntuale. La soglia è una scelta prudenziale del prototipo, non una soglia validata empiricamente.
6. La fascia compatibile include i livelli con somma distante al massimo 2 dal massimo; si mostrano gli estremi dell’insieme. Non è un intervallo di confidenza statistico. Una stima al bordo mostra 600 o 2600 e segnala il limite del confronto: non permette di dedurre che la forza reale sia inferiore o superiore a quel valore.

I punteggi per tutti i livelli, il metodo `maia3-likelihood-v1`, il numero di decisioni e l’ipotesi sull’avversario restano salvati per consentire future calibrazioni e confronti. Nessun punteggio viene inventato da un LLM o convertito arbitrariamente dalla perdita in centipawn. Una partita in corso può essere valutata, ma il risultato riguarda solo la sequenza disponibile.

## Annullo e salvataggio

Una nuova mossa rende la stima precedente non applicabile. L’annullamento cambia anche la revisione della partita e invalida i calcoli in corso: non si può salvare una risposta riferita al ramo precedente, neppure se contiene lo stesso numero di mosse.

Se la partita era già stata analizzata, prima dell’annullamento si conserva una copia nell’archivio, riconoscibile da **prima dell’annullamento**. Esercizi, tentativi e spiegazioni restano associati a quella sequenza. La copia è consultabile in revisione e non aumenta il conteggio delle partite nei Progressi.

## Possibili estensioni

Per trasformare l’indicazione in una misura più affidabile occorrono partite di giocatori con rating noto, separate tra calibrazione e verifica, segmentazione per cadenza e piattaforma, valutazione dell’errore fuori campione e confronto su molte partite. La fascia attuale non va presentata come una probabilità di possedere un determinato rating.
