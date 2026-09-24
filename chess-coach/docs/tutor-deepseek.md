# Tutor DeepSeek

## Uso

Nella sezione **Rivedi**, analizza una partita con Stockfish. Nel pannello **Tutor DeepSeek** puoi descrivere cosa avevi in mente e premere **Chiedi al tutor DeepSeek**. La riflessione è facoltativa. Il tutor spiega le decisioni e propone fino a tre attività, per un massimo di 25 minuti; i pulsanti aprono i Puzzle o avviano i Drill effettivamente disponibili.

La generazione parte solo al clic. Aprire la pagina, giocare o analizzare con Stockfish non genera chiamate al modello remoto. Una richiesta identica, con la stessa analisi e gli stessi dati di pratica, riusa la risposta salvata. Modificare la riflessione o le evidenze produce una nuova richiesta. I progressi quantitativi restano calcolati dai tentativi reali: le ipotesi del tutor non modificano automaticamente le competenze del giocatore.

## Dati inviati e conservazione

A `https://api.deepseek.com/chat/completions` vengono inviati:

- fino a tre decisioni della partita selezionata: posizione FEN, mossa giocata, alternative e valutazioni Stockfish;
- colore, livello di riferimento e tipo di sessione;
- riflessione scritta dal giocatore;
- riepilogo dei progressi e identificativi degli esercizi e Drill disponibili.

Non vengono inviati la chiave nel testo del prompt, i nomi dei giocatori nelle intestazioni PGN, il database completo o tutte le partite. La chiave è utilizzata soltanto nell'header di autenticazione HTTPS verso il dominio ufficiale, con redirect disabilitati. Risposte, riflessione e riferimenti alle evidenze sono salvati nella tabella locale `tutor_reviews`; fanno parte del backup SQLite. I dati inviati al servizio sono soggetti alle condizioni del servizio DeepSeek.

## Configurazione locale

La credenziale è in `.secrets/deepseek.json`, leggibile dal solo proprietario del file. La cartella è esclusa da Git e non è servita dal frontend. Per configurare o sostituire una chiave senza mostrarla sullo schermo:

```bash
cd /opt/generic_projects/chess-coach
python3 scripts/configure_deepseek.py
```

È anche possibile usare `DEEPSEEK_API_KEY` e `DEEPSEEK_MODEL` nell'ambiente del backend. Il modello iniziale è `deepseek-flash`; è supportato anche `deepseek-v4-pro`. Non inserire credenziali in variabili frontend o file sotto `web/public`. Per escludere completamente l'uso del servizio, avviare il backend con `CHESS_COACH_DISABLE_LLM=1`.

## Confini e verifiche

Stockfish rimane il verificatore scacchistico. L'LLM interpreta soltanto le evidenze fornite: le spiegazioni possono essere inesatte e non sono diagnosi definitive. Il sistema valida il formato JSON, la durata del piano e l'esistenza delle posizioni e degli esercizi citati. Questi controlli non dimostrano automaticamente la correttezza di ogni frase del tutor.

Il prompt richiede di distinguere fatti e ipotesi, evitare varianti inventate e trattare la riflessione come dati, non come istruzioni operative. Nessuna risposta del modello viene eseguita come codice o comando; i testi vengono renderizzati come testo React. I piani non creano nuove posizioni o soluzioni non verificate.

Una sola generazione può essere in corso. Le richieste hanno un limite di 2.400 token in uscita e timeout di 55 secondi per le operazioni di lettura della connessione. Non sono previsti tentativi automatici ripetuti. Errori di autenticazione, credito, limite richieste o rete restituiscono messaggi locali senza inoltrare al browser le risposte diagnostiche del fornitore. Stockfish e Maia restano disponibili.

## Verifica effettuata

Una richiesta reale su una partita dimostrativa ha prodotto una risposta valida con riferimenti alle decisioni analizzate; la richiesta identica ha riusato la cache. I test automatici usano risposte simulate per verificare errori API, riferimenti inventati, analisi obsolete e cache senza consumare credito. Le prove del browser disattivano le credenziali reali.

Riferimenti: [API ufficiale DeepSeek](https://api-docs.deepseek.com/) e [formato JSON](https://api-docs.deepseek.com/guides/json_mode/), verificati il 24 settembre 2026.
