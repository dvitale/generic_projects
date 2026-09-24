# Provenienza e componenti

- **Maia frontend** — CSSLab, [maia-platform-frontend](https://github.com/CSSLab/maia-platform-frontend), commit `a6e52f5c811ee18863cb2f0e81f2433a5b9905de`, GPL-3.0. Worker originale, mappa delle mosse e logica di tokenizzazione adattata in `web/src/engine/maia.ts`. Licenza in `licenses/maia-frontend-GPL-3.0.txt`. L'interfaccia e il backend di questa app sono nuovi; non riproducono il marchio o gli account del sito.
- **Modello Maia3 browser** — scaricato da `https://www.maiachess.com/maia3/maia3_simplified.onnx`. Hash e provenienza in `model-manifests/maia-browser.json`. Il file è scaricato localmente e non aggiunto al repository Git. Non si assegna una nuova licenza ai pesi; la licenza del frontend non viene presentata come prova della licenza dei pesi. Riferimento scientifico: [Chessformer](https://arxiv.org/abs/2605.19091).
- **ONNX Runtime Web 1.23.0** — Microsoft, MIT; runtime distribuito dal sito e verificato dal manifest. Licenza in `licenses/onnxruntime-MIT.txt`.
- **Stockfish 19** — [official-stockfish/Stockfish](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19), GPL-3.0. L'installer usa l'archivio ufficiale Linux x86-64 universal, SHA-256 `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f`. Conservare `vendor/stockfish/Copying.txt`, gli avvisi e i sorgenti forniti nell'archivio. Fonte della versione: tag `sf_19` del repository ufficiale.
- **python-chess/chess** — GPL-3.0-or-later; versioni in `requirements.lock`.
- **chess.js** — BSD-2-Clause; **React, Vite, FastAPI** — MIT; altre dipendenze e licenze nei rispettivi pacchetti installati e lockfile.

I file applicativi nuovi e derivati sono forniti sotto GPL-3.0; il testo completo è in `LICENSE`. Le licenze di terzi continuano ad applicarsi ai rispettivi componenti.

- **Chess.com Green/Neo** — tema e immagini scaricati su richiesta per l'installazione locale dai server pubblici Chess.com. Gli asset non sono inclusi nel repository Git e non sono concessi sotto la licenza GPL dell'app. URL e hash in `model-manifests/chesscom-theme.json`.
- **DeepSeek** — servizio API esterno opzionale; nessun peso del modello viene distribuito con l'app. Documentazione: https://api-docs.deepseek.com/.
