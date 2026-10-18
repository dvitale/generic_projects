# Allenarsi per perdere meno contro Maia: guida pratica

Funzioni SparringMate aggiornate il 16 ottobre 2026. Tutorial esterni verificati il 6 ottobre 2026. I tutorial esterni si basano sulla documentazione ufficiale consultata il 6 ottobre: le aree personali a pagamento non sono state provate con il tuo account. Nomi e disponibilità possono variare. Le routine proposte sono consigli per il tuo obiettivo, non prescrizioni ufficiali dei servizi.

**Passa subito alla pratica:** [importa i PGN Maia](http://localhost:8033/?section=schedule&import=pgn) · [apri Allenamento](http://localhost:8033/?section=schedule) · [apri Blunder prevention](http://localhost:8033/?section=prevention) · [apri Studio](http://localhost:8033/?section=study) · [rivedi le tue partite](http://localhost:8033/?section=archive).

I collegamenti a SparringMate aprono l’app locale in una nuova scheda e richiedono che sia avviata su questo PC. I rimandi ai capitoli restano nella guida; quelli ai servizi esterni aprono una nuova scheda.

## Il tuo obiettivo di lavoro

Nelle partite esaminate, i temi da allenare per primi sono il controllo delle minacce avversarie, gli scacchi dopo una cattura e le occasioni di recupero. Per iniziare, scegli una domanda da usare sempre: **«Dopo la mia mossa, quali scacchi e catture avrà l'avversario?»**

Non serve aprire quattro programmi ogni giorno. Usa SparringMate come archivio delle partite Maia e calendario principale; prova eventualmente uno degli altri strumenti per un compito preciso. Valuta il risultato nelle nuove partite senza aiuti, non soltanto dal numero di puzzle completati.

## Misurare il progresso senza inseguire un numero Elo

In **Rivedi → Decisioni**, guarda quante tue scelte non hanno perso valutazione in modo rilevante e quante hanno conservato un vantaggio. Gli errori del bot non entrano nel tuo conteggio. Un profilo Maia 1300 non premia una partita più di un profilo 600: **Somiglianza con Maia** resta un confronto facoltativo, separato dalla qualità.

In [**Progressi**](http://localhost:8033/?section=progress), confronta partite con partite e drill con drill. I conteggi mostrano quanti casi sono stati osservati: poche decisioni non dimostrano una tendenza stabile e cambiare avversario o difficoltà può cambiare i risultati.

### Esercitarti a valutare prima di rinunciare

1. Apri [**Allenamento**](http://localhost:8033/?section=schedule), quindi **Valuta la posizione**.
2. Indica se il lato che muove è in vantaggio, equilibrio o svantaggio, senza consultare il motore. Scrivi la minaccia concreta che temi e una risorsa difensiva o offensiva.
3. Indica quanto sei sicuro e, se è la tua impressione, **Mi sembra già persa**. Se ricordi la posizione o il punteggio, segnala la familiarità: resterà pratica.
4. Premi **Salva e confronta con Stockfish**. Confronta le risorse della variante con quello che temevi; puoi aprire la partita di origine o approfondire su Lichess.
5. Nei Progressi osserva quando l'impressione di sconfitta non è confermata dal motore. Non devi pensare positivo a tutti i costi: alcune posizioni sono davvero sfavorevoli.

Le posizioni derivano dalle tue partite analizzate e possono essere favorevoli, equilibrate o sfavorevoli. Non sono selezionate soltanto fra i tuoi blunder. Una posizione ricordata non prova un miglioramento del giudizio in una partita nuova. Queste verifiche non incrementano i successi dei puzzle né il calendario dei ripassi.

## 1. Da Maia Chess a SparringMate

### Recuperare una partita

1. Accedi a [Maia Chess](https://www.maiachess.com/) e apri la partita terminata, oppure ritrovala nella sezione Analysis.
2. Cerca il pannello **Export** e il campo **PGN**. Nel componente ufficiale attuale l'icona di copia, o il riquadro del PGN, copia il testo negli appunti. Non copiare il campo FEN: descrive una sola posizione.
3. In SparringMate [apri **Importa PGN**](http://localhost:8033/?section=schedule&import=pgn), quindi incolla il testo in **Partite PGN**.
4. Lascia **Automatico contro Maia**. Il programma riconosce il lato umano quando l'altro giocatore si chiama, per esempio, Maia 600. Per altri PGN inserisci il tuo nome esattamente come appare nelle intestazioni oppure scegli Bianco/Nero.
5. Lascia selezionato **Analizza e prepara gli esercizi dopo l'importazione**, quindi premi **Importa partite**.
6. Attendi **Esercizi pronti** e apri **Allenamento**. Puoi anche aprire subito la partita dal riepilogo dell'importazione. Prosegui con la [configurazione del calendario](#prima-configurazione).

La copia PGN è verificata nel [componente ExportGame ufficiale](https://github.com/CSSLab/maia-platform-frontend/blob/a6e52f5c811ee18863cb2f0e81f2433a5b9905de/src/components/Common/ExportGame.tsx). Maia descrive le funzioni di esportazione anche nell'[annuncio della piattaforma](https://www.maiachess.com/blog/platform-v1).

### Più partite e conservazione dei dati

Puoi incollare più PGN separati da righe vuote, oppure scegliere più file `.pgn` nello stesso caricamento: massimo 20 partite e 1 MB complessivo per operazione. Se Maia offre soltanto la copia, puoi salvare quel testo in un normale file `.pgn` e caricarlo in seguito.

Importa una serie consecutiva, includendo vittorie e patte. Il riepilogo distingue partite nuove, già presenti ed errori: un PGN problematico non nasconde quelli importati correttamente. Se il colore non è riconosciuto, correggi il nome o scegli il colore e ripeti l'importazione.

L'identificativo Maia, quando presente, distingue partite diverse anche con mosse identiche. La reimportazione non cancella l'analisi già salvata. Se lo stesso identificativo contiene mosse differenti, il programma chiede di verificare i PGN. Conserva risultato, intestazioni e annotazioni temporali presenti; non ricostruisce tempi che Maia non esporta. Per le nuove importazioni riconosce il livello dal nome del bot.

### Limite della sincronizzazione

La verifica del 7 ottobre ha restituito la lista dello storico senza autenticazione (HTTP 200), ma il dettaglio delle partite richiede accesso (HTTP 401). La verifica della risposta autenticata è ancora incompleta. Questa versione di SparringMate usa quindi il passaggio PGN, senza promettere una sincronizzazione dell'account, chiedere cookie o conservare credenziali Maia. Non è stata verificata un'API pubblica stabile per sincronizzare lo storico completo dal solo nome utente.

## 2. Il calendario di SparringMate

### Prima configurazione

1. Apri [**Allenamento**](http://localhost:8033/?section=schedule) nella barra laterale.
2. Imposta inizialmente **10–15 minuti** e **2–3 posizioni nuove al giorno**. È una proposta di partenza: abbassa il limite se accumuli ripassi.
3. Seleziona i giorni in cui vuoi allenarti e premi **Salva piano**.
4. Premi **Inizia il prossimo ripasso**. Il piano propone prima i ripassi, poi le nuove posizioni, evitando la stessa decisione sia come puzzle sia come prevenzione nella medesima lista.
5. Terminato l'esercizio, torna in **Allenamento** per aggiornare il riepilogo e aprire il successivo. Puoi interrompere: impostazioni, tentativi e scadenze restano salvati.

La durata è una stima di circa due minuti per esercizio, non un conto alla rovescia. Se sbagli, la verifica effettuata conta nel lavoro di oggi: non devi riuscire per forza per considerare utile la sessione. Il riepilogo distingue verifiche, successi e pratica anticipata.

### Come cambiano le scadenze

| Esito | Effetto |
|---|---|
| Primo successo al primo tentativo, senza aiuti | Richiamo dopo 4 ore |
| Successivi richiami riusciti al primo tentativo | Dopo 1, 3, 7, 14, 30, 90 e 180 giorni |
| Errore, risposta corretta con indizio o soluzione mostrata | Progressione azzerata; nuova verifica dopo 4 ore |
| Risposta corretta dopo un errore nella stessa sessione | Utile pratica; non promuove il ripasso |
| Riapertura prima della scadenza | Pratica; non fa avanzare il calendario |

**Un puzzle sbagliato resta nella lista da ripassare.** Puoi riprovarlo subito; il piano attende però quattro ore prima di considerare una nuova verifica indipendente. Questa distinzione impedisce di confondere il ricordo immediato della soluzione con un apprendimento più stabile.

Un esercizio corretto esce dalla lista in scadenza soltanto se il primo tentativo è riuscito senza aiuti ed è un richiamo valido, non una ripetizione anticipata. Torna quando scade. La lista dei puzzle da ripassare e il numero di attività proposte oggi possono quindi differire.

I giorni di pausa non cancellano gli arretrati. Il calendario mostra le scadenze attuali, che cambiano dopo le risposte; gli orari sono in Europe/Rome. Il piano limita il carico quotidiano ma non impedisce di aprire altri esercizi come pratica. Non invia notifiche esterne e non richiede che il browser rimanga aperto per conservare le scadenze.

Questo sistema si ispira alla ripetizione dilazionata; non è il prodotto MoveTrainer e non è collegato a Chessable. Misura il ricordo delle posizioni ripassate, non ancora il trasferimento dell'abilità alle partite nuove.

Per approfondire: [come funzionano le scadenze](#come-cambiano-le-scadenze), [esempio di settimana](#una-settimana-sostenibile) e [richiamo con MoveTrainer](#movetrainer-ricordare-lidea-dopo-una-pausa).

### La tua routine consigliata

Prima di ogni risposta, cerca uno scacco avversario, una cattura e una minaccia al re. Dopo un errore guarda la sequenza prima di chiedere una spiegazione; poi prova a descrivere il meccanismo con una frase. Alla fine scegli una sola regola da portare nella partita successiva, per esempio: «Prima di prendere un cavallo controllo gli scacchi contro il mio re».

Passa alla pratica: [Blunder prevention](http://localhost:8033/?section=prevention) per evitare una mossa perdente, [Drill](http://localhost:8033/?section=drill) per continuare a giocare e [Progressi](http://localhost:8033/?section=progress) per rivedere gli indicatori.

## 3. Studio: fissare le lezioni delle tue partite

Il calendario ti fa rigiocare le posizioni. **Studio**, nella barra laterale sotto Puzzle e Problemi (sul telefono nel menu **Altro**), serve a ricordare *perché* una mossa era sbagliata e a verificarlo senza aiuti. Le sei schede usano solo partite già analizzate: le partite di confutazione contro Stockfish non compaiono. [Apri Studio](http://localhost:8033/?section=study).

### Dopo ogni partita: Impara da una partita

1. In **Rivedi → Decisioni** premi **Studia questa partita**, oppure apri **Studio → Impara da una partita** e scegli la partita.
2. L’elenco mostra le decisioni che hanno perso almeno 0,80. Per ciascuna trovi in un solo posto **Puzzle**, **Blunder prevention**, **Drill da qui**, **Gioca contro Stockfish**, **Chiedi al tutor** e **Rivedi nella partita**. Puzzle e Drill sono attivi solo per i tre errori più costosi; Blunder prevention solo per i blunder che rendono la posizione difficile da difendere.
3. Scrivi in **La mia lezione** una frase che controlleresti prima di muovere, per esempio «Prima di catturare conto chi difende la casa d’arrivo», e premi **Crea flashcard**.
4. Chiudi con **Quiz della partita**.

### Quiz: richiamare senza muovere i pezzi

Il quiz propone fino a cinque domande sulle tre decisioni più costose della partita: la mossa migliore, la risposta più forte dell’avversario dopo il tuo errore e chi stava meglio. Ogni opzione sbagliata è controllata da Stockfish e perde almeno 1,50 rispetto a quella giusta, quindi non ci sono risposte «quasi giuste». Conta solo la prima risposta: rispondi pensando, non per tentativi. Fallo il giorno dopo la revisione, non subito: ricordare dopo una pausa è proprio ciò che vuoi allenare.

### Flashcard: ripassare la regola, non la mossa

Quando, dopo un puzzle o una prevenzione sbagliati, usi **Spiega motivo**, la lezione ottenuta diventa una scheda, tranne quando un’analisi più profonda di Stockfish giudica buona la mossa giocata. Altre schede nascono dal pacchetto di una partita o dal tutor.

1. Osserva la posizione e la domanda; prova a dire la regola ad alta voce.
2. Premi **Mostra risposta**: vedi la lezione con la freccia della tua mossa e di quella di Stockfish.
3. Valuta con onestà quanto ricordavi (tasti 1–4):

| Valutazione | Quando usarla | Prossima scadenza |
|---|---|---|
| Di nuovo | Non ricordavi la regola | Dopo 10 minuti |
| Difficile | Ricordata a fatica | 1 giorno, poi intervalli poco più lunghi |
| Bene | Ricordata con un po’ di riflessione | 1 giorno, poi 3, poi intervalli crescenti |
| Facile | Ricordata subito | 4 giorni, poi intervalli più lunghi |

**Archivia scheda** quando la regola è superata o era sbagliata. Le flashcard hanno un calendario proprio: non modificano le scadenze dei puzzle in **Allenamento**.

### Esame di prova: verificare senza aiuti

Ogni due settimane, in **Esame di prova** scegli 6, 8 o 10 posizioni e 8, 12 o 20 minuti, poi premi **Inizia l’esame**. Le posizioni vengono dai tuoi puzzle, con temi alternati e preferenza per quelle che non hai visto negli ultimi tre giorni. Non ci sono indizi né esiti finché non premi **Consegna**: con **Salta per ora** passi oltre e torni dopo alle posizioni lasciate senza risposta. Una mossa vale come nei puzzle, se perde meno di 0,70 rispetto a Stockfish.

Nei risultati apri ogni posizione sbagliata con **Apri come puzzle** o **Rivedi nella partita**. L’esame non tocca tentativi e ripassi dei puzzle; lo storico dei punteggi compare anche in [**Progressi**](http://localhost:8033/?section=progress). Servono almeno tre puzzle per avviarlo. Il punteggio dipende da quali posizioni escono: confronta la tendenza su più esami, non un singolo risultato.

### Chiedi al tutor: domande su una posizione

Apri una posizione con **Chiedi al tutor** dal pacchetto o dal quaderno, oppure incolla una FEN. Scrivi una domanda come «Perché non Cxe5?», anche in notazione italiana (C, A, T, D, R), oppure muovi un pezzo sulla scacchiera: la domanda «Perché non …?» si prepara da sola e la posizione non cambia.

Stockfish analizza ogni mossa citata e la migliore; le varianti restano visibili sotto la risposta. Se il tutor DeepSeek è configurato, spiega soltanto quelle varianti. Una risposta che cita mosse di pezzo o catture non verificate viene scartata e sostituita dai fatti di Stockfish. Senza chiave la risposta è costruita solo dalle varianti. Con **Salva la lezione come flashcard** la regola entra nei ripassi. Prima di chiedere, formula la tua ipotesi: il tutor serve a confermarla o smentirla.

### Quaderno: vedere quali errori si ripetono

Il **Quaderno** raggruppa errori e imprecisioni per tema, con le tue lezioni e i tre esempi più costosi di ciascun tema. Una volta alla settimana leggi il tema più numeroso e scegli la regola da portare nella partita successiva. **Esporta PGN annotato** crea un capitolo per esempio, con la variante di Stockfish, da aprire in Lichess Studio, ChessBase o un altro lettore PGN.

### La tua routine di studio

- Dopo ogni partita analizzata: pacchetto della partita e una o due flashcard, cinque minuti.
- Il giorno dopo: il quiz della partita.
- Ogni giorno, prima dei puzzle: le flashcard in scadenza.
- Ogni due settimane: un esame di prova, senza guardare prima le soluzioni.

Per approfondire: [routine sulle minacce](#la-tua-routine-consigliata) e [esempio di settimana](#una-settimana-sostenibile).

## 4. Aimchess: scegliere cosa allenare

### A cosa ti serve

[Aimchess](https://aimchess.com/) presenta lezioni personalizzate dalle partite, tra cui **Retry Mistakes**, **Blunder Preventer**, **Defender** e allenamento alla conversione del vantaggio. Il Blunder Preventer descritto dal servizio propone due alternative da confrontare; il 360 Trainer mescola tipi diversi di posizione. Queste sono le funzioni pertinenti al tuo problema. Non è stata verificata una connessione diretta con Maia Chess: non basare l'acquisto sull'aspettativa che legga automaticamente le tue partite Maia.

Collegamenti utili: [apri Aimchess](https://aimchess.com/) · [ripassa la routine sulle minacce](#la-tua-routine-consigliata) · [torna al calendario locale](#il-calendario-di-sparringmate).

### Sessione pratica proposta: 10 minuti

1. Accedi al tuo account e controlla quali lezioni sono disponibili nel tuo piano.
2. Se il report usa una tua cronologia di partite, verifica che sia recente e rappresentativa. Un report di partite giocate altrove non misura automaticamente le difficoltà contro Maia.
3. Scegli **Blunder Preventer**, se disponibile. Prima di scegliere tra le mosse, formula una risposta avversaria per ciascuna: «Dopo A arriva questo scacco; dopo B non c'è perché…».
4. Passa a **Defender** per applicare lo stesso controllo a una difesa attiva.
5. Usa **Retry Mistakes** quando gli esercizi provengono davvero dalla tua cronologia. Dopo aver trovato la mossa, spiega quale minaccia risolve.
6. Chiudi la sessione con una posizione mista, se disponibile, per non aspettarti sempre una combinazione vincente.

Non scegliere la mossa soltanto perché sembra meno aggressiva. L'obiettivo è distinguere una cattura sicura da una cattura che permette uno scacco intermedio. Annota il motivo dell'errore, non soltanto l'esito rosso/verde.

Per ora darei priorità a prevenzione e difesa. Il lavoro esteso sulle aperture può attendere: conoscere una variante più lunga non risolve da solo il problema degli scacchi avversari non controllati.

## 5. MoveTrainer: ricordare l'idea dopo una pausa

### Che cosa stai usando

MoveTrainer è la tecnologia di studio interattivo dei corsi, presente anche nei [Courses di Chess.com](https://support.chess.com/en/articles/10318195-what-are-movetrainer-courses). Le mosse studiate ritornano secondo un calendario; nella [documentazione della ripetizione](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work), una risposta corretta allunga l'intervallo e un errore lo riduce. È adatto al richiamo di materiale già appreso; il numero di ripassi non certifica da solo la forza di gioco.

Collegamenti utili: [guida ufficiale ai corsi MoveTrainer](https://support.chess.com/en/articles/10318195-what-are-movetrainer-courses) · [intervalli di ripasso ufficiali](https://support.chess.com/en/articles/10319322-how-does-the-spaced-repetition-scheduling-work) · [confronta le scadenze di SparringMate](#come-cambiano-le-scadenze).

### Preparazione proposta

1. Apri un corso a cui hai accesso nella piattaforma che utilizzi. Controlla anteprima, contenuto e condizioni prima di acquistare materiale nuovo.
2. Per questo obiettivo scegli lezioni elementari su sicurezza del re, pezzi indifesi, forchette, infilate e scacchi intermedi. È un criterio di selezione, non il nome garantito di un corso.
3. Avvia la funzione di apprendimento delle nuove mosse, solitamente indicata come **Learn**; poi usa quella di ripasso, **Review**, quando il materiale è in scadenza. I nomi esatti possono differire tra le interfacce.

### Come studiare una posizione

1. Leggi la spiegazione prima di memorizzare la sequenza.
2. Formula la minaccia: «La torre è dietro il re sulla stessa diagonale» è più utile di «devo ricordare questa casa».
3. Gioca la mossa prevista e segui la risposta avversaria fino a capire la conseguenza.
4. Se sbagli, ricostruisci il perché della risposta. Una ripetizione immediata corretta ti aiuta a fissarla, ma non dimostra ancora che l'avresti riconosciuta da solo.
5. Nella sessione successiva affronta prima i ripassi dovuti, poi eventualmente aggiungi poco materiale.

Per partire, dedica cinque minuti al giorno a poche posizioni comprese bene. Se aumentano gli arretrati, sospendi temporaneamente le nuove lezioni. Non cercare di compensare saltando le spiegazioni.

Non è verificato un flusso diretto “Maia → corso personale MoveTrainer” per il tuo account. Il calendario locale di SparringMate copre già il ripasso dei tuoi PGN Maia; non occorre comprare un corso per ottenere questa funzione.

## 6. Noctie: provare le idee durante il gioco

### Funzioni pertinenti

La [FAQ ufficiale](https://noctie.ai/faq/) descrive un avversario adattivo, feedback sulle mosse e flashcard ricavate dagli errori, con ripetizione dilazionata. Il giudizio sulle mosse deriva dalla prospettiva del modello umano e non equivale alla valutazione Stockfish. L'adattamento non garantisce vittorie facili: la stessa FAQ avverte che anche un principiante può trovare impegnative le prime partite.

Collegamenti utili: [apri Noctie](https://app.noctie.ai/) · [FAQ ufficiale](https://noctie.ai/faq/) · [come trasferire una posizione Maia](#usare-una-posizione-delle-tue-partite-maia).

### Sessione proposta

1. Apri [app.noctie.ai](https://app.noctie.ai/) e accedi. Verifica il piano richiesto per giocare e salvare: la documentazione corrente indica funzioni di allenamento legate a Club Noctie.
2. Apri **Play**. Per apprendere senza fretta scegli un tempo comodo o Unlimited, se disponibile nella tua configurazione.
3. Nelle prime sessioni usa il feedback come occasione di riflessione: dopo una segnalazione di errore prova a trovare la risposta avversaria prima di chiedere un indizio.
4. A fine partita apri la revisione da **Progress** e torna a una scelta importante. Domandati se il problema era una minaccia non vista oppure una risposta prevista ma valutata male.
5. Apri **Flashcards** e lavora sul materiale in scadenza. Ripeti la spiegazione del motivo prima di muovere.
6. In una sessione separata prova senza suggerimenti e annullamenti: serve a vedere quanto riesci a fare da solo.

I nomi delle sezioni e le funzioni di accesso sono documentati nella [guida ufficiale dell'app](https://noctie.ai/docs/blind-mode-guide/).

### Usare una posizione delle tue partite Maia

Puoi trasferire una posizione, anche senza collegare gli account: in Maia aprila nella revisione e copia il **FEN** dal pannello Export. In Noctie apri **Setup**, incolla il FEN nel relativo campo e controlla lato al tratto e posizione prima di avviare la pratica. Gioca poche mosse cercando di prevenire lo stesso tipo di minaccia.

La guida Noctie documenta collegamenti per Chess.com e Lichess attraverso Profile → Linked accounts. Non è verificato un collegamento Maia. L'importazione PGN negli Opening Books serve invece al repertorio: non va confusa con l'analisi automatica della partita originale e la produzione di flashcard dai suoi errori.

### Quando lo sceglierei nel tuo caso

Userei Noctie quando vuoi allenare il controllo delle minacce dentro una partita con feedback. Terrei però le partite Maia online come prova esterna, a condizioni il più possibile simili, e le importerei in SparringMate. I livelli e i colori dei vari servizi non sono direttamente confrontabili.

## 7. Una settimana sostenibile

Esempio organizzativo, modificabile:

| Giorno | Attività principale |
|---|---|
| Lunedì | Flashcard in scadenza, ripassi SparringMate e una breve continuazione dalla tua partita |
| Martedì | Ripassi più un modulo di prevenzione/difesa, in SparringMate oppure Aimchess |
| Mercoledì | Una partita Maia online senza aiuti, poi importazione |
| Giovedì | Quiz della partita di mercoledì, ripassi e poche posizioni comprese con MoveTrainer, se lo utilizzi |
| Venerdì | Una sessione Noctie con obiettivo preciso, oppure un drill locale |
| Sabato | Una partita Maia online e revisione di un episodio |
| Domenica | Pausa o breve bilancio con il Quaderno; un esame di prova ogni due settimane |

Per iniziare questa settimana: [importa le partite Maia](#da-maia-chess-a-sparringmate), [imposta il calendario](http://localhost:8033/?section=schedule) e scegli un solo supporto tra [Aimchess](#aimchess-scegliere-cosa-allenare), [MoveTrainer](#movetrainer-ricordare-lidea-dopo-una-pausa) e [Noctie](#noctie-provare-le-idee-durante-il-gioco).

Prima della settimana successiva chiediti: ho evitato almeno una minaccia che prima non vedevo? Ho riconosciuto uno scacco dopo una cattura? Ho sfruttato un'occasione di recupero? Registra tutte le partite di verifica, non soltanto quelle frustranti. Un campione piccolo può oscillare: conta soprattutto la riduzione degli stessi errori in posizioni nuove.

[Torna all’inizio della guida](#allenarsi-per-perdere-meno-contro-maia-guida-pratica).
