# Chess Coach

Progetto di un'applicazione per l'allenamento scacchistico personalizzato con **Maia-3** come sparring partner e **Stockfish** come valutatore.

## Stato

Fase di progettazione e acquisizione degli asset: il modello browser ufficiale Maia e il relativo runtime sono stati scaricati e ne è stato verificato il caricamento. L'applicazione non è ancora implementata; non sono state eseguite partite o benchmark.

## Documentazione

Leggi la [specifica funzionale e tecnica](docs/progetto.md), versione 1.2 del 23 settembre 2026. Include architettura, esperienza utente, integrazione dei motori, profilo delle competenze, esercizi, piano di allenamento, API e roadmap.

## Obiettivo

Collegare partite, analisi degli errori, esercizi personali e verifiche su posizioni nuove, per misurare i miglioramenti del giocatore nel tempo.

## Configurazione proposta

- Modello ONNX già distribuito da maiachess.com, con worker JavaScript e ONNX Runtime Web/WebAssembly ufficiali: nessun addestramento o conversione. Vedi [motore browser](docs/motore-browser.md) e [manifest dei download](model-manifests/maia-browser.json).
- Stockfish per analisi, varianti e validazione degli esercizi.
- Interfaccia web React/Next.js e backend Python/FastAPI.
- PostgreSQL per partite, evidenze, tentativi e piani.
- Moduli estendibili per diagnosi, pianificazione, ripassi e spiegazioni.

## Riferimenti

- [Maia Chess](https://www.maiachess.com/)
- [Motore Maia-3](https://github.com/CSSLab/maia3)
- [Paper Chessformer](https://arxiv.org/abs/2605.19091)
- [Stockfish](https://github.com/official-stockfish/Stockfish)

Maia-3 usa un Transformer. Maia originale CNN resta un possibile adapter facoltativo. I binari e il modello sono stati scaricati localmente; il repository conserva i riferimenti e i checksum, senza duplicare i file voluminosi. I rispettivi riferimenti di licenza sono indicati nella documentazione.
