# Trova un’alternativa

Percorso per le posizioni in cui ti sembra che ogni mossa perda. L’obiettivo non è risolvere più esercizi: è aver bisogno di meno aiuto sulle posizioni nuove, e poi trovare da solo lo stesso tipo di idea nelle partite.

Le percezioni («tutte le mosse perdono», «la minaccia è inevitabile») sono trattate come ipotesi da verificare. Il modulo distingue tre difficoltà: ricerca delle mosse, calcolo delle risposte e valutazione della posizione.

## Ruoli

- **Stockfish** decide se una mossa tiene la partita e verifica le continuazioni.
- **Indizi e spiegazioni** nascono da fatti controllati sulla scacchiera: chi attacca che cosa, scambio statico, scacchi, case liberate, continuazione del motore.
- **Il tutor DeepSeek**, se configurato, riformula soltanto i livelli 1–3 e il dettaglio decisivo. Ogni testo viene controllato prima di essere usato: mosse citate, case citate, pezzi nominati su una casa e assenza della soluzione nei livelli 1–3. Un campo non verificabile resta quello generato dalle regole; se il tutor non risponde si usano solo le regole, senza perdere il lavoro.
- **Maia** non giudica mai la correttezza. Rigiocare la posizione con **Gioca da qui** apre una partita contro Maia.

Al tutor arrivano solo FEN, minaccia temuta, mosse considerate, alternative verificate e continuazione. Non arrivano nomi, titoli delle partite o PGN.

## Segnalare il blocco

**Qui mi sento bloccato** compare sotto la scacchiera in Gioca, quando tocca a te. In Rivedi diventa **Qui mi sentivo bloccato**, anche per le partite importate da Maia online, e si usa sulle posizioni in cui muovevi tu. Due azioni:

- **Segna e continua** salva il momento senza mostrare aiuti. Non cambia la partita e non conta come suggerimento.
- **Aiutami a ragionare** apre l’esercizio su una scacchiera separata.
  - In Gioca resta dentro la pagina della partita: la partita aspetta e il tempo di riflessione continua a contare come prima.
  - Da Rivedi apre la sezione **Trova un’alternativa** (voce **Altro** sui telefoni).

Ogni episodio conserva la partita, la semimossa, la FEN e il colore del giocatore.

- **Origine dell’episodio**: `live` se segnalato in Gioca, `retrospective` se segnalato in Rivedi, `scheduled` per ripetizioni e casi analoghi.
- **Momento delle risposte**: sono `live` solo se date mentre la partita aspetta ancora quella mossa; altrimenti sono ricostruite dopo.

Se la partita prosegue, l’esercizio resta sulla posizione salvata. **Gioca … nella partita** applica la mossa trovata solo se la partita è ancora esattamente lì: stessa semimossa, stessa revisione, stessa posizione. Altrimenti risponde 409 e la proposta resta nell’esercizio. Le mosse dell’esercizio non toccano mai mosse o PGN della partita.

Aiuti e verdetti chiesti durante la partita rendono assistita quella decisione (`assisted_plies`). Come per **Suggerisci mossa**, quella decisione esce dalle statistiche indipendenti. Una semplice segnalazione no.

## Prima della ricerca

Due domande brevi, prima di qualsiasi consiglio o valutazione:

1. **Che cosa temi che possa fare l’avversario?** Indichi la mossa sulla scacchiera (posizione con l’avversario al tratto), scrivi una frase breve oppure scegli «Non ne vedo nessuna». Sotto scacco la domanda non serve.
2. **Quali mosse hai considerato?** Fino a otto, sulla scacchiera, oppure «Non ne vedo nessuna».

Le risposte vengono salvate prima dell’analisi. Se Stockfish fallisce restano salvate, e **Riprova l’analisi** riparte da lì.

## Aiuti progressivi

Nessuna valutazione numerica, freccia o prima scelta del motore compare durante la ricerca. Gli aiuti si aprono uno alla volta, solo su richiesta; il server rifiuta un livello saltato.

| Livello | Aiuto | Da che cosa nasce |
|---|---|---|
| 0 | Ricerca autonoma | — |
| 1 | Domanda sulla minaccia | La minaccia indicata: è concreta? Altrimenti la minaccia reale con la mossa all’avversario |
| 2 | Direzione della ricerca | Il tipo di idea della mossa che tiene la partita |
| 3 | Pezzo, zona o relazione da osservare | La casa evidenziata sulla scacchiera |
| 4 | Mossa suggerita, con freccia | Poi la richiesta di prevedere la risposta avversaria, verificata con Stockfish |
| 5 | Continuazione e spiegazione completa | Chiude la ricerca |

Tipi di idea riconosciuti con regole fisse (`direction` in `backend/alternatives.py`):

- eliminare un attaccante;
- difesa tramite scambio;
- contro-minaccia;
- restituire materiale;
- sacrificio;
- mettere al sicuro il pezzo;
- difendere;
- difesa indiretta;
- cattura utile;
- mossa forzante;
- creare una minaccia;
- liberare una casa;
- attivare il re;
- mossa di pedone;
- migliorare un pezzo.

Una minaccia dell’avversario è «reale» se, dandogli la mossa, la valutazione peggiora di almeno 1,50 e la sua mossa matta, dà scacco, cattura o vince materiale nella variante. Perdere un tempo in una posizione che ne ha bisogno non è una minaccia da parare.

Viene registrato il livello massimo di aiuto mostrato prima della soluzione (`help_level`).

## Verdetto

Non serve la prima scelta di Stockfish. La mossa proposta si confronta con la migliore della posizione iniziale, sempre dal punto di vista di chi muove, con due misure tenute distinte:

- **perdita in centesimi** rispetto alla migliore;
- **calo del punteggio atteso** in punti percentuali, con la curva logistica di Lichess.

Il punteggio atteso da solo nasconderebbe un crollo da −6 a −9 in una partita già persa; i centesimi da soli punirebbero un passaggio da +9 a +7 in una partita vinta.

| Verdetto | Regola predefinita |
|---|---|
| Alternativa valida | Perdita ≤ 50 e calo ≤ 5 punti; oppure resta ≥ +4,00 con calo ≤ 2 punti |
| Giocabile con una concessione | Perdita ≤ 150 e calo ≤ 15 punti; oppure resta ≥ +1,50 |
| Non risolve il problema | Tutto il resto, e ogni mossa che consente un matto forzato |
| Verdetto non affidabile | Entro 25 centesimi da una soglia, o profondità < 12: la verifica si ripete con il doppio dei nodi e, se il verdetto cambia, non viene dato |

Casi con il matto:

- Se la posizione ha un matto a favore, ogni matto va bene. Una mossa che resta ≥ +4,00 è una concessione.
- Se ogni mossa è matta, vale la resistenza più lunga.

Budget di ricerca:

- 120.000 nodi per la posizione e per la mossa proposta, 240.000 nella verifica ripetuta;
- 5 candidate a 50.000 nodi per l’elenco delle alternative.

Le soglie sono in `DEFAULTS` e si cambiano con la variabile d’ambiente `SPARRINGMATE_ALTERNATIVE_THRESHOLDS`, un oggetto JSON con le stesse chiavi:

```bash
SPARRINGMATE_ALTERNATIVE_THRESHOLDS='{"validLossCp": 40, "concessionLossCp": 120}'
```

Il messaggio sotto la scacchiera:

- non riporta numeri;
- per una mossa che non basta indica la risposta che la confuta;
- quando il motivo è verificato, riporta la frase della [spiegazione degli errori](spiegazione-errori.md), solo nei motivi che non svelano la mossa migliore.

Un sacrificio non è penalizzato perché perde materiale: decide la continuazione. Se è valido, il messaggio dice che il materiale offerto è giustificato.

In una posizione compromessa (−3,00 o peggio) il percorso diventa ricerca della resistenza migliore. Il livello 2 lo dice, e la spiegazione finale riporta quante mosse sono state analizzate e precisa che non è una prova che ogni mossa perda. Propone anche di rivedere la mossa precedente della partita.

## Dopo la soluzione

La spiegazione collega, in quest’ordine:

1. che cosa temevi;
2. che cosa minacciava davvero l’avversario;
3. il dettaglio che rende possibile l’alternativa;
4. una breve continuazione che lo dimostra.

Riguarda la mossa che hai trovato tu, anche se Stockfish ne preferisce di poco un’altra. È marcata tattica, posizionale oppure tattica e posizione. La continuazione si scorre sulla scacchiera con ◀ ▶.

Poi due domande rapide, con una nota facoltativa:

- **Questa mossa non ti era venuta in mente oppure l’avevi scartata?**
- **Quale dettaglio ora la rende convincente?**

| Classificazione | Area |
|---|---|
| Alternativa non considerata | ricerca delle mosse |
| Scartata per una risposta avversaria | calcolo |
| Minaccia ritenuta inevitabile | valutazione |
| Difficoltà a valutare la posizione risultante | valutazione |
| Motivo non ancora chiaro | da chiarire |

La classificazione finale è quella che deriva dalle tue risposte. Accanto compare un’**ipotesi del sistema**, dichiarata come tale: per esempio «fra le mosse considerate ce n’era una valida» oppure «la minaccia indicata non era concreta». Puoi correggere la classificazione; le statistiche contano solo risposte e correzioni, mai le ipotesi. Non si attribuiscono diagnosi psicologiche.

Esiti:

- **Risolto autonomamente**: alternativa trovata senza aiuti.
- **Risolto con indizio**: trovata dopo i livelli 1–3.
- **Compreso dopo la soluzione**: dopo il livello 4 o 5.
- **Non ancora compreso**: hai risposto «Non mi è ancora chiaro».

## Ripetizione e trasferimento

Ogni episodio completato genera una **ripetizione** della stessa posizione: un nuovo episodio con esposizione `seen`. La ripetizione è tanto più vicina quanto più aiuto è servito:

| Esito | Prossima ripetizione |
|---|---|
| Non ancora compreso | 4 ore |
| Compreso dopo la soluzione o risolto con indizio | 1 giorno |
| Risolto autonomamente | 7 giorni |

Una ripetizione risolta da sola passa alla tappa successiva: 1, 7 e poi 30 giorni, poi il ciclo si chiude. Le ripetizioni pronte entrano nel piano di **Allenamento** accanto a Puzzle e Blunder prevention, e contano fra le verifiche del giorno.

**Cerca una posizione analoga e un controesempio** esamina le decisioni delle tue partite analizzate e, se installati, i problemi Lichess. Ogni candidato passa un filtro statico e poi una verifica Stockfish a 40.000 nodi, al massimo sei per tipo di caso.

- **Posizione analoga**: una mossa valida dello stesso tipo di idea, e almeno una candidata naturale che non basta. Non basta una somiglianza della scacchiera.
- **Controesempio**: una mossa dello stesso tipo è disponibile ma Stockfish la respinge, mentre la posizione resta giocabile. A fine esercizio la mossa tentatrice viene indicata.

Se non c’è un caso adeguato, il modulo lo dice e non lo inventa.

Ogni episodio collegato mantiene `parent_id`, la partita e la semimossa di origine. **Apri nell’analisi** porta alla posizione in Rivedi; **Gioca da qui** rigioca contro Maia.

## Progressi

Il pannello in **Progressi** mostra:

- **Autonomia sulle posizioni nuove**: momenti originali, analoghi e controesempi. Confronta gli ultimi 10 con i 10 precedenti: quota risolta da sola e aiuto medio.
- **Posizioni già viste**: le ripetizioni, contate a parte.
- **Aiuto necessario**: distribuzione dei livelli 0–5 sulle posizioni nuove.
- **Difficoltà più frequenti**, con l’area.
- **La stessa idea nelle partite**: nelle decisioni analizzate in cui la mossa migliore era di quel tipo, quante volte è stata trovata (perdita < 0,80) o mancata (≥ 1,80), prima e dopo il primo episodio. Il tipo è riconosciuto con le stesse regole fisse.
- **Contro Maia online**: risultati delle partite importate da maiachess.com, per livello Maia e cadenza, prima e dopo il primo episodio, con il numero di partite.
- **Partite contro Maia in SparringMate**: per livello, separate fra autonome e con almeno una decisione assistita.
- **Raccolta dati**: segnalazioni dal vivo e in revisione, risposte dal vivo e ricostruite, decisioni rese assistite.

Il passaggio da «riconosco l’idea dopo un suggerimento» a «la trovo da solo» si legge in tre punti:

1. l’aiuto medio sulle posizioni nuove scende e la quota risolta da sola sale;
2. le posizioni analoghe vengono risolte con meno aiuto delle ripetizioni;
3. nelle partite successive la stessa idea viene trovata più spesso.

Non esiste un Elo dell’allenamento. Il confronto dei risultati non attribuisce al modulo le variazioni e mostra sempre la dimensione del campione.

## Dati

Le tabelle SQLite si creano all’avvio, senza toccare quelle esistenti:

- `stuck_episodes`: un episodio per esposizione. Contiene:
  - versioni `model_version` e `rule_version`;
  - ruolo, `parent_id`, origine;
  - partita, revisione, semimossa, FEN e colore;
  - risposte con il loro momento;
  - evidenze Stockfish con motore, nodi e soglie;
  - indizi e loro fonte;
  - livello di aiuto, mossa trovata, previsione;
  - riflessione, classificazione dichiarata, inferita e corretta;
  - esito, tappa e scadenza.
- `stuck_attempts`: ogni tentativo con verdetto, livello di aiuto al momento, valutazione e messaggio.

Partite ed esercizi non vengono mai cancellati. Se un annullamento archivia la linea originale, gli episodi la seguono come gli altri esercizi.

API: tutte sotto `/api/alternatives`.

| Metodo e percorso | Funzione |
|---|---|
| `POST /episodes` | Crea un episodio: segnala o apre |
| `GET /episodes`, `GET /episodes/{id}` | Elenco e dettaglio |
| `POST /episodes/{id}/open` | Apre un momento segnato |
| `POST /episodes/{id}/reasoning` | Salva le risposte e avvia l’analisi |
| `POST /episodes/{id}/analyze` | Ripete l’analisi fallita |
| `POST /episodes/{id}/hint` | Apre il livello successivo |
| `POST /episodes/{id}/attempts` | Propone una mossa |
| `POST /episodes/{id}/accept` | Accetta una mossa con concessione |
| `POST /episodes/{id}/prediction` | Prevede la risposta avversaria |
| `POST /episodes/{id}/reflection` | Salva le risposte dopo la soluzione |
| `POST /episodes/{id}/classification` | Corregge la classificazione |
| `POST /episodes/{id}/apply` | Gioca la mossa nella partita |
| `POST /episodes/{id}/followups` | Cerca posizione analoga e controesempio |
| `GET /progress` | Statistiche per Progressi |

## Casi di verifica

I casi in `tests/test_alternatives.py` sono controllati con Stockfish reale:

- donna sotto attacco con più alternative valide (Qd1, Qf3; Qh3 respinta per …d5);
- torre sotto attacco;
- minaccia apparente con risposta attiva (Bxf7+ invece di salvare il cavallo);
- difesa tramite scambio (cavallo inchiodato sulla torre);
- sacrificio corretto (Bxh7+);
- mossa tranquilla (Kd3 nel finale di pedone);
- posizione realmente persa;
- la stessa posizione speculare per il Nero.

Le prove backend coprono anche:

- segnalazione senza aiuti;
- ordine degli indizi e livello memorizzato;
- mossa illegale respinta;
- persistenza dopo il riavvio;
- guasto del motore e nuovo tentativo;
- PGN invariato e proposta su posizione superata;
- ripetizioni separate dalle posizioni nuove, nel piano e nei progressi;
- casi analoghi e controesempi;
- validazione del testo del tutor;
- soglie configurabili.

`web/tests/find-alternative.spec.ts` prova:

- il percorso dal vivo;
- il percorso in revisione con ricaricamento della pagina e schermo da telefono;
- il pannello in Progressi.

## Limiti

- I tipi di idea sono regole euristiche sulla scacchiera e sulla variante del motore. Un caso può appartenere a più tipi: ne viene scelto uno, con un ordine fisso.
- La verifica usa un budget limitato. Il verdetto «non affidabile» copre solo l’instabilità vicino alle soglie, non ogni errore di valutazione.
- La ricerca di casi analoghi è limitata alle decisioni già analizzate e ai primi 400 problemi importati.
- La ricorrenza nelle partite considera le ultime 60 partite analizzate e le date dei PGN, quando presenti.
- Le partite di Maia online sono confrontabili solo per livello e cadenza: avversari, aperture e condizioni restano diversi.
