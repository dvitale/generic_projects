# Drill e Puzzle: analisi e progetto di personalizzazione

Aggiornamento: 24 settembre 2026. Questo documento descrive la prima implementazione locale e le estensioni progettate. Integra `progetto.md`; dove differiscono, lo stato eseguibile e questo documento prevalgono sulle precedenti proposte.

## Cosa fa il progetto originale

L'analisi riguarda il frontend ufficiale Maia al commit `a6e52f5c811ee18863cb2f0e81f2433a5b9905de`, non un backend privato ricostruito per supposizione.

| Funzione | Comportamento osservabile nei sorgenti | Conseguenza per Chess Coach |
|---|---|---|
| Play | Maia propone mosse umane condizionate dal livello | Sparring con distribuzione Maia e controllo di legalità separato |
| Analyze | Previsioni Maia affiancate a valutazioni Stockfish | Separare plausibilità umana e qualità scacchistica |
| Drill | Aperture, finali e posizioni personalizzate, sequenze ripetibili, limite di mosse e revisione | Allenare una sequenza di decisioni e un piano, non soltanto una risposta |
| Puzzle | Posizione da risolvere, tentativi, rinuncia, rating e analisi successiva | Registrare primo tentativo, aiuti e ripetizioni come eventi diversi |

La pagina `/drills` rimanda alle aperture. Il controller costruisce sessioni da sequenze PGN o posizioni, supporta ripetizioni, risposte Maia e revisione Stockfish. Il codice originale presenta statistiche di precisione e perdita di valutazione: non dimostrano da sole un apprendimento trasferibile.

La pagina Puzzle usa il primo tentativo per correttezza e rating; consente ulteriori tentativi. L'API del frontend richiede un puzzle con contesto di partita e valutazioni e registra le mosse tentate e la rinuncia. L'elenco delle mosse corrette arriva dal server. La soglia esatta del backend originale non è pubblicata in questi sorgenti e non viene attribuita a Maia per supposizione.

Fonti primarie:

- [Controller Drill](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/hooks/useOpeningDrillController/useOpeningDrillController.ts)
- [Tipi aperture, finali e sessioni](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/types/openings.ts)
- [Pagina Puzzle](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/pages/puzzles.tsx)
- [API training](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/api/train.ts)
- [Paper Chessformer](https://arxiv.org/abs/2605.19091) e [Maia3](https://github.com/CSSLab/maia3)

Maia3 è basato su Transformer/Chessformer. Il riferimento iniziale a una CNN riguarda le precedenti generazioni. L'app usa direttamente `maia3_simplified.onnx` distribuito dal sito e il relativo runtime JavaScript/WASM: non richiede addestramento né conversioni Python.

## Flusso personalizzato

1. Gioca con Maia oppure importa una tua partita PGN, indicando il colore.
2. Stockfish confronta le tue mosse con alternative, sempre dalla prospettiva del giocatore che decide.
3. Le tre decisioni più critiche sopra soglia diventano esercizi personali con posizione, storia precedente e provenienza.
4. Risolvi la decisione come Puzzle oppure riparti dalla stessa posizione come Drill contro Maia.
5. Conserva separatamente primo tentativo, aiuti, tentativi successivi e ripassi programmati.
6. Il piano giornaliero propone ripasso, pratica contro Maia e revisione. Le future verifiche su posizioni nuove misureranno il trasferimento.

## Implementato in questa versione

### Drill

- Catalogo iniziale: Italiana, Siciliana, Caro-Kann, Gambetto di donna e finale re e torre contro re.
- Posizioni personali ricavate dagli esercizi creati nelle revisioni. Il colore coincide con chi doveva decidere nella partita originale.
- Livello Maia, colore dove applicabile e durata da 3 a 12 decisioni del giocatore.
- Conservazione della storia precedente alla posizione, utile per ricostruzione, arrocco, en passant e ripetizioni.
- Risposte campionate dalla distribuzione Maia sulle mosse legali, senza sostituzione silenziosa con un altro motore.
- Fine al numero previsto di decisioni o al termine della partita; l'ultima decisione può chiudere il drill prima della risposta del bot.
- Revisione Stockfish delle sole decisioni effettivamente giocate nel drill: la sequenza preparata non contribuisce ai risultati.
- Motivazione delle proposte: provenienza da un errore personale oppure presenza della sequenza iniziale nelle partite libere/importate. Nessuna diagnosi di repertorio inventata.

### Puzzle

- Generazione dalle posizioni critiche delle proprie partite, senza soluzione nell'elenco iniziale degli esercizi.
- Nuova valutazione della mossa scelta: accettate alternative con perdita entro 50 centesimi di pedone, a budget limitato. È una regola del prototipo, non quella dichiarata del sito Maia.
- Nessuna soluzione mostrata automaticamente dopo un errore; sono possibili altri tentativi, indizio generale e richiesta esplicita della soluzione.
- Sessione persistente e versione del tentativo per evitare doppie registrazioni.
- Primo tentativo senza aiuti distinto da tentativi successivi, sessioni assistite e pratica anticipata.
- Ripasso dopo 1, 3, 7, 14 e 30 giorni in base ai successi indipendenti consecutivi. Errori o aiuti nella prima prova riportano al giorno successivo. La pratica anticipata non aumenta la serie né rinvia il ripasso.
- Le sessioni aperte vengono riprese per impedire che una ricarica azzeri il primo tentativo.

### Profilo e piano

SQLite conserva partite, revisioni, posizioni, sessioni Drill, sessioni Puzzle e tentativi. Il profilo mostra frequenza dei temi negli esercizi, scadenze e successi indipendenti. Il piano attuale è una struttura di 25 minuti con quantità di ripassi adattata ai dati, non ancora un ottimizzatore pedagogico.

I temi automatici sono intenzionalmente limitati: calcolo/mosse candidate e minacce di matto. Non è implementato un classificatore affidabile di inchiodature, strutture pedonali o errori strategici.

## Estensione del tutor: progetto successivo

### Evidenze e competenze

Introdurre `decision_events`, `skill_evidence`, `skill_state`, `training_items`, `training_sessions`, `plans` e `transfer_checks`. Ogni evidenza deve contenere giocatore, colore, posizione e storia, origine, tema e confidenza del classificatore, difficoltà, tempo impiegato, aiuti, risultato, versione dei motori e budget di analisi.

Una frequenza elevata di errori può dipendere dalle opportunità: dividere gli errori per occasioni reali dello stesso tema e stratificare per difficoltà e fase. Separare partite libere, Drill già conosciuti, Puzzle nuovi e ripassi. Evitare di contare più volte la stessa posizione o posizioni quasi identiche della stessa partita.

Per ogni competenza mantenere una distribuzione di incertezza, non soltanto un punteggio. Iniziare con un modello beta-binomiale documentato, poi stimare difficoltà e abilità con un modello calibrato su dati sufficienti. Il rating inserito in Maia descrive un gruppo di giocatori: non è la probabilità individuale di risolvere un esercizio.

### Selezione motivata degli esercizi

Selezionare prima i ripassi scaduti, poi una combinazione di temi prioritari e posizioni nuove. Proposta da validare: 50% ripasso, 30% trasferimento su posizioni non viste, 20% repertorio/tecnica scelta dal giocatore. Consentire all'utente di cambiare obiettivo e tempo disponibile.

Priorità iniziale: impatto scacchistico × frequenza normalizzata × rilevanza per il repertorio × necessità di ripasso. Penalizzare duplicati e ripetizioni recenti; valorizzare informazione nuova quando l'incertezza è alta. Questi pesi sono una scelta da sperimentare, non un risultato del paper Maia.

### Drill avanzati

- Repertorio importato da PGN e distribuzione reale delle aperture del giocatore.
- Obiettivi verificabili: sviluppo, sicurezza del re, conservazione del vantaggio, piano di finale. Verificatori espliciti per obiettivo; Stockfish da solo non certifica la comprensione del piano.
- Maia come avversario plausibile e Stockfish come verifica. Per posizioni a pochi pezzi, integrazione opzionale Syzygy per risultati esatti.
- Progressione guidata, poi condizioni variate: cambio di risposta Maia, posizione simile ma nuova, colore o ordine di mosse quando sensato.
- Confronto a distanza con la prima sessione, stessa difficoltà e condizioni di aiuto comparabili.

### Puzzle avanzati

- Generatore di varianti tattiche a più mosse con albero di risposte verificate, non semplice confronto della prima mossa.
- Filtrare posizioni instabili aumentando profondità/budget e verificando alternative equivalenti. Registrare esiti incerti senza penalizzare il giocatore.
- Catalogo esterno con licenza e provenienza verificate per il primo utilizzo e i test su posizioni mai viste.
- Indizi progressivi: tema → pezzi coinvolti → mossa candidata → soluzione. Ogni livello è un aiuto distinto.
- Misurare tempo, sicurezza dichiarata e qualità della spiegazione separatamente dal risultato scacchistico.

### Tutor conversazionale opzionale

Un modello linguistico può spiegare solo fatti e varianti forniti dai verificatori. Non deve inventare motivi tattici o giudicare legalità. La versione corrente usa testi deterministici e non richiede API esterne. Il piano futuro deve permettere spiegazioni correggibili e mostrare da quale partita arriva ogni suggerimento.

## Criteri di accettazione delle estensioni

| Area | Verifica richiesta |
|---|---|
| Scacchi | Legalità, orientamento nero, promozioni, en passant, arrocco, matto/stallo e storia conservata |
| Personalizzazione | Proposte diverse su profili diversi, spiegabili con evidenze reali |
| Puzzle | Alternative equivalenti accettate; aiuti e retry non trasformati in successi indipendenti |
| Drill | Solo decisioni nuove valutate; obiettivi e numero di decisioni rispettati |
| Apprendimento | Miglioramento su posizioni nuove e a distanza, con incertezza e difficoltà controllate |
| Persistenza | Ripresa dopo ricarica, niente duplicati, dati esportabili |
| Motori | Identità, versione, budget e asset verificabili; niente fallback nascosti |

## Limiti attuali

Applicazione personale locale senza account, sincronizzazione cloud o multiplayer. I job di analisi in corso vanno riavviati dopo il riavvio del server. Le analisi finite e i dati del giocatore persistono. Il modello browser usa i canali dei pezzi; il motore delle regole applica separatamente i vincoli di legalità. Le analisi a budget finito non sono dimostrazioni matematiche e la soglia in centesimi di pedone è una prima approssimazione.
