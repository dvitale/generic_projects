# Provenienza e componenti

- **Maia frontend** — CSSLab, [maia-platform-frontend](https://github.com/CSSLab/maia-platform-frontend), commit `a6e52f5c811ee18863cb2f0e81f2433a5b9905de`, GPL-3.0. Mappa delle mosse e logica di tokenizzazione adattate in `backend/maia.py` (fino al 30 ottobre 2026 anche worker e tokenizzazione nel browser, `web/src/engine/maia.ts`). Licenza in `licenses/maia-frontend-GPL-3.0.txt`. L'interfaccia e il backend di questa app sono nuovi; non riproducono il marchio o gli account del sito.
- **Modello Maia3** — eseguito sul server (`models/maia3/`), scaricato da `https://www.maiachess.com/maia3/maia3_simplified.onnx`. Hash e provenienza in `model-manifests/maia-browser.json`. Il file è scaricato localmente e non aggiunto al repository Git. Non si assegna una nuova licenza ai pesi; la licenza del frontend non viene presentata come prova della licenza dei pesi. Riferimento scientifico: [Chessformer](https://arxiv.org/abs/2605.19091).
- **ONNX Runtime** — Microsoft, MIT; la versione Python (`requirements.lock`) esegue Maia sul server. Fino al 30 ottobre 2026 l'interfaccia usava ONNX Runtime Web 1.23.0. Licenza in `licenses/onnxruntime-MIT.txt`.
- **Stockfish 19** — [official-stockfish/Stockfish](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19), GPL-3.0. L'installer usa l'archivio ufficiale Linux x86-64 universal, SHA-256 `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f`. Conservare `vendor/stockfish/Copying.txt`, gli avvisi e i sorgenti forniti nell'archivio. Fonte della versione: tag `sf_19` del repository ufficiale.
- **python-chess/chess** — GPL-3.0-or-later; versioni in `requirements.lock`.
- **Inter** (Rasmus Andersson) e **Fraunces** (Undercase Type) — SIL Open Font License 1.1, inclusi nel bundle tramite `@fontsource-variable/inter` e `@fontsource-variable/fraunces` 5.3.0. Licenze in `licenses/inter-OFL-1.1.txt` e `licenses/fraunces-OFL-1.1.txt`.
- **Database dei puzzle Lichess** — [database.lichess.org](https://database.lichess.org/#puzzles), CC0. Una selezione viene scaricata localmente da `make puzzles` e non aggiunta al repository, salvo gli 11 problemi di `tests/fixtures/lichess-puzzles.csv` usati dai test. Il generatore di Lichess (`lichess-puzzler`, AGPL-3.0) non è incluso né riprodotto.
- **zstandard** (python-zstandard) — BSD-3-Clause; usato solo dall'importazione dei problemi.
- **chess.js** — BSD-2-Clause; **React, Vite, FastAPI** — MIT; altre dipendenze e licenze nei rispettivi pacchetti installati e lockfile.

I file applicativi nuovi e derivati sono forniti sotto GPL-3.0; il testo completo è in `LICENSE`. Le licenze di terzi continuano ad applicarsi ai rispettivi componenti.

- **Chess.com Green/Neo** — tema e immagini scaricati su richiesta per l'installazione locale dai server pubblici Chess.com. Gli asset non sono inclusi nel repository Git e non sono concessi sotto la licenza GPL dell'app. URL e hash in `model-manifests/chesscom-theme.json`.
- **DeepSeek** — servizio API esterno opzionale; nessun peso del modello viene distribuito con l'app. Documentazione: https://api-docs.deepseek.com/.
