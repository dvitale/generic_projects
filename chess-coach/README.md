# Chess Coach

Progetto di un'applicazione per l'allenamento scacchistico personalizzato con **Maia-3** come sparring partner e **Stockfish** come valutatore.

## Stato

Fase di progettazione: la specifica è disponibile, ma l'applicazione non è ancora implementata e i motori non sono stati eseguiti o misurati.

## Documentazione

Leggi la [specifica funzionale e tecnica](docs/progetto.md), versione 1.1 del 23 settembre 2026. Include architettura, esperienza utente, integrazione dei motori, profilo delle competenze, esercizi, piano di allenamento, API e roadmap.

## Obiettivo

Collegare partite, analisi degli errori, esercizi personali e verifiche su posizioni nuove, per misurare i miglioramenti del giocatore nel tempo.

## Configurazione proposta

- Maia-3 5M come prima baseline da verificare su CPU.
- Stockfish per analisi, varianti e validazione degli esercizi.
- Interfaccia web React/Next.js e backend Python/FastAPI.
- PostgreSQL per partite, evidenze, tentativi e piani.
- Moduli estendibili per diagnosi, pianificazione, ripassi e spiegazioni.

## Riferimenti

- [Maia Chess](https://www.maiachess.com/)
- [Motore Maia-3](https://github.com/CSSLab/maia3)
- [Paper Chessformer](https://arxiv.org/abs/2605.19091)
- [Stockfish](https://github.com/official-stockfish/Stockfish)

Maia-3 usa un Transformer. Maia originale CNN resta un possibile adapter facoltativo. Questo progetto non include ancora codice, binari o pesi dei motori; i rispettivi riferimenti di licenza sono indicati nella specifica.
