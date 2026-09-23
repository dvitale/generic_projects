# Maia per il browser — pacchetto scaricato dal sito ufficiale

Scaricato il 23 settembre 2026 da https://www.maiachess.com/.

Il modello pronto all'uso è `public/maia3/maia3_simplified.onnx` (45.683.686 byte). Il worker JavaScript lo esegue tramite ONNX Runtime Web 1.23.0 e WebAssembly. Non occorre addestrarlo, convertirlo o scegliere un checkpoint PyTorch.

Il pacchetto binario è stato scaricato nella cartella locale di lavoro e non è incluso in questo repository. Gli URL e i checksum per recuperare i singoli file sono nel [manifest](../model-manifests/maia-browser.json).

## Contenuto

- `public/maia3/maia3_simplified.onnx`: modello servito dal sito.
- `public/maia-worker.js`: worker ufficiale con cache IndexedDB.
- `public/ort/`: runtime JavaScript, modulo di caricamento e WebAssembly scaricati dal sito.
- `upstream/`: sorgenti originali di inferenza, preparazione della posizione, mappatura delle mosse e cache, con licenza e package.json di riferimento.
- `licenses/`: licenza del runtime ONNX.
- `manifest.json`: URL, dimensioni e SHA-256 di ciascun file.
- `verification.json`: nomi e dimensioni degli input/output rilevati caricando il modello.

## Integrazione nel progetto

Servire il contenuto di `public/` dalla radice dell'applicazione: il worker usa i percorsi assoluti `/ort/` e il modello è disponibile a `/maia3/maia3_simplified.onnx`. Il pacchetto contiene gli asset e sorgenti di riferimento, non un'applicazione autonoma già avviabile. I sorgenti TypeScript richiedono integrazione con dipendenze, import e tipi dell'app.

Il preprocessing da riutilizzare è in `upstream/src/lib/engine/tensor.ts`; il trattamento degli output e la maschera delle mosse legali sono in `upstream/src/lib/engine/maia.ts`. Preservare l'orientamento della scacchiera e le mappe delle promozioni.

L'artefatto browser accetta `tokens` di forma `[batch,64,12]`, `elo_self` ed `elo_oppo`; restituisce `logits_move` con 4352 valori e `logits_value` con 3 valori per elemento del batch. Non presumere che il suo formato di input coincida con quello dei checkpoint Python con storia: usare il codice frontend associato.

Per il tutor, usare la distribuzione sulle mosse legali restituita dal frontend. Stockfish resta il verificatore separato di mosse, varianti ed esercizi.

## Verifica effettuata

Download completato, dimensioni e checksum registrati. Il modello è stato caricato con successo tramite il runtime WebAssembly scaricato, eseguito in Node.js, ricavando gli input/output riportati in `verification.json`. Non è ancora stata provata una partita né l'intera integrazione nel browser.

## Provenienza

Il bundle distribuito dal sito indica `/maia3/maia3_simplified.onnx`. Il codice sorgente di supporto proviene dal frontend ufficiale, commit `a6e52f5c811ee18863cb2f0e81f2433a5b9905de`:

- [Configurazione del modello](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/contexts/MaiaEngineContext.tsx)
- [Worker](https://www.maiachess.com/maia-worker.js)
- [Modello ONNX](https://www.maiachess.com/maia3/maia3_simplified.onnx)

Le licenze originali sono conservate nel pacchetto; non viene assegnata una nuova licenza agli artefatti scaricati.
