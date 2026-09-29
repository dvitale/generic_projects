# Verifica del motore Maia e della scelta delle mosse

Data: 29 settembre 2026. Questa verifica distingue compatibilità con il modello browser ufficiale e parità di gioco con il sito. La prima è verificabile; la seconda richiede anche il comportamento del server ufficiale.

## Risultati verificati

- Il modello locale è identico byte per byte a `https://www.maiachess.com/maia3/maia3_simplified.onnx`: 45.683.686 byte, SHA-256 `405bf76c15727dad8728b352c06a8f3c1b80fb2760e8d666b32485c63d75b856`.
- Anche `maia-worker.js` coincide con quello distribuito dal sito: SHA-256 `db44a23840a6f200508d0a5ff1c502488aba59efa2d1d083134eccba40b59394`.
- Tutte le 4.352 associazioni UCI/indice coincidono con il frontend CSSLab al commit `a6e52f5c811ee18863cb2f0e81f2433a5b9905de`.
- Su 89 inferenze, la codifica dei pezzi e l’insieme delle mosse legali coincidono con le funzioni ufficiali. La differenza massima assoluta nelle probabilità è `3,13 × 10^-8`; nella probabilità di risultato è inferiore a `5 × 10^-5`, compatibile con l’arrotondamento a quattro decimali del frontend ufficiale.
- Sono comprese posizioni con il Nero al tratto, arrocco, en passant e promozioni. I casi sintetici sono verificati ai livelli 600, 1500 e 2600.
- Maia3 riceve gli Elo numerici effettivi per giocatore e avversario; in gioco l’app imposta entrambi al livello selezionato. Non applica la vecchia conversione in categorie di Maia2.

Confronto effettuato con [tokenizzazione ufficiale](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/lib/engine/tensor.ts) e [lettura degli output](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/lib/engine/maia.ts). Il riferimento di preprocessing usa `chess.js` al posto di `chess.ts`; le posizioni speciali sono controllate anche con `python-chess`.

## Differenza architetturale rispetto a Play sul sito

Nel [controller ufficiale di Play](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/hooks/usePlayController/useVsMaiaController.ts), la mossa proviene da `fetchGameMove` e dal campo `top_move` della risposta del server. Il nome del campo, da solo, non dimostra che la mossa sia scelta con argmax.

L’[API frontend](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/api/play.ts) invia a `/api/v1/play/get_move` la sequenza delle mosse, la configurazione del modello e informazioni sul tempo. Il backend di questa funzione non è presente nel repository frontend. La richiesta diagnostica anonima è stata rifiutata con HTTP 403; non è stato possibile confrontare le risposte online sulle stesse posizioni.

Restano quindi non verificati: pesi effettivamente usati dal server, uso della storia, Elo dell’avversario, temperatura, eventuali filtri sulle candidate e altri criteri di scelta. Il download del modello per il browser non dimostra che quel file sia anche il motore server usato in Play.

## Come sceglie SparringMate

`chooseMaiaMove` chiama il modello locale sulla posizione corrente; `sample` sorteggia sull’intera distribuzione legale, senza taglio delle mosse poco probabili. È equivalente a temperatura 1 e nessun filtro top-p. Il ritardo di 1,2–3,2 secondi regola solo la presentazione: non aumenta la profondità di ricerca.

Questo campionamento è una modalità valida per Maia, ma non certifica una forza equivalente a quella di Play sul sito. Il [motore UCI ufficiale Maia3](https://github.com/CSSLab/maia3/blob/1e13597c42d4858b7cfd7cfdae01e297263364b2/maia3/uci.py) espone temperatura e top-p; temperatura zero sceglie la mossa più probabile. La configurazione di quel programma non è prova della configurazione del server web.

Probabilità umana e qualità tattica sono grandezze diverse. Anche una seconda scelta frequente può lasciare un pezzo in presa; la prima scelta a livello 600 può essere sbagliata. Limitarsi alle mosse sopra una piccola soglia non garantisce l’eliminazione di questi errori.

## Verifiche ripetibili

Da `web/`, eseguire:

```bash
npm test -- tests/maia-engine.spec.ts
```

Il test controlla il modello tramite hash, codifica e mosse legali su sette posizioni sintetiche, e 21 inferenze reali nel browser ai tre livelli. Verifica anche l’invio degli Elo e documenta che il sorteggio completo può selezionare una mossa con probabilità dell’1%. Le fixture sono posizioni sintetiche, non partite personali.

L’audit delle partite locali è conservato separatamente sul PC. La valutazione usa Stockfish 19 con un thread, 64 MB di hash e 120.000 nodi per ricerca, confrontando sulla stessa posizione la mossa giocata e la prima proposta di Maia. Tre esempi sono approfonditi a un milione di nodi. Sono confronti fra decisioni: non simulazioni di partite complete né stime Elo della forza del bot.

## Intervento consigliato

Per isolare l’effetto del sorteggio, aggiungere una modalità dichiarata **Prima scelta Maia**, affiancata alla modalità attuale. Il livello deve restare quello selezionato e le probabilità di analisi devono rimanere quelle originali. Confrontare poi partite nuove a parità di condizioni prima di scegliere una modalità predefinita.

Un filtro Stockfish contro le sviste sarebbe un motore ibrido con forza diversa: andrebbe reso esplicito e calibrato. Cambiare di nascosto Elo, pesi o probabilità non è una dimostrazione di equivalenza con maiachess.com. Questa verifica non modifica la selezione delle mosse dell’app.
