# Perché è un errore

Data: 19 ottobre 2026. Descrive la frase che spiega un errore in parole semplici, come viene costruita e quali sono i limiti.

## Perché

Stockfish dice *quanto* una mossa peggiora la posizione, non *perché*. Quando la causa è un pezzo in presa lo si vede subito; quando è una forchetta due mosse dopo, una donna che resta senza case o un matto sulla traversa, la valutazione e le frecce non bastano. La spiegazione legge la confutazione trovata da Stockfish e la racconta in una frase.

## Dove compare

- **Rivedi**, nel riepilogo della partita, sotto le scelte di Stockfish, quando selezioni la mossa nell'elenco o sul grafico;
- **Rivedi → Mosse → Revisione passo passo**, in cima alla mossa selezionata;
- il commento dopo un Puzzle o una posizione di Blunder prevention sbagliati, lo storico dei tentativi e le mosse più costose della partita.

Compare per ogni mossa che perde almeno 0,80 rispetto alla migliore, oppure quando concede o manca un matto. Se nessuno dei motivi qui sotto è verificato, la spiegazione non inventa una causa: dice **Deriva dalla linea di Stockfish**, mostra la linea e offre il tasto **Mostra**, che apre una finestra dove la variante si gioca da sola, partendo dalla linea migliore quando è quella a vincere materiale (campo `bestWins`) (una mossa ogni 1,2 secondi, ▶/⏸ per riprodurla o fermarla, ← → per scorrerla a mano). Vedere come la posizione peggiora mossa dopo mossa spiega la valutazione meglio di una frase generica. Negli altri casi **Guarda la variante sulla scacchiera** apre una scacchiera piccola: **Dopo la tua mossa** riproduce la confutazione, **Mossa migliore** la linea di Stockfish, con le frecce ← → per scorrere.

## Come funziona

`backend/explain.py`, chiamato da `insights.compare`, senza LLM e senza nuove ricerche del motore: usa le due varianti già salvate (la mossa giocata e la migliore) e controlla la scacchiera con regole fisse.

| Motivo | Quando viene dichiarato |
|---|---|
| Matto contro | Stockfish trova un matto dopo la mossa; se il re è chiuso sulla traversa dai propri pezzi lo dice |
| Matto non visto | La migliore alternativa dava matto, la mossa giocata no |
| Pezzo in presa | La risposta cattura un pezzo e lo scambio statico (SEE) le fa guadagnare materiale |
| Difesa tolta | Il pezzo catturato era difeso dal pezzo appena spostato |
| Minaccia non parata | Lo stesso pezzo era già catturabile prima della mossa |
| Linea aperta | La mossa ha liberato la linea su cui avviene la cattura |
| Forchetta o attacco doppio | La risposta attacca almeno due pezzi indifesi, più preziosi dell'attaccante, o il re |
| Infilata | La risposta dà scacco e dietro il re c'è un pezzo da almeno 3 |
| Pezzo intrappolato | Il pezzo è attaccato, si perde dov'è e ogni casa legale lo perde ugualmente (anche dopo due mosse avversarie) |
| Attacco di scoperta, inchiodatura | La risposta scopre un attacco o inchioda al re un pezzo che non si può più salvare |
| Promozione, perdita di materiale | La variante perde materiale senza un motivo più preciso: dice cosa perdi e cosa prendi |
| Re esposto | Almeno due scacchi avversari che non sono semplici cambi |
| Svantaggio di posizione | Nessuna perdita di materiale: re meno protetto, pedone passato concesso, pedoni isolati o doppiati, pezzi meno attivi rispetto all'alternativa |
| Deriva dalla linea di Stockfish | Nessuno dei casi precedenti è verificato: il testo riporta solo la linea (motivo `engine`) |

I motivi tattici richiedono che la variante perda almeno 2 punti di materiale rispetto all'alternativa, oppure che la variante si fermi subito dopo la risposta con una perdita di almeno 1,50: una forchetta parata da un controattacco non viene dichiarata. Il materiale a fine variante conta anche la ripresa ancora in sospeso sull'ultima casa (scambio statico): una linea che si ferma a metà di un cambio, come «Nd5 Bxd5» prima di riprendere, non sembra una perdita e non nasconde il pezzo perso dall'altra variante. Una seconda frase indica l'alternativa: «Con Rxa8+ vincevi una torre» se vinceva materiale, altrimenti la linea preferita da Stockfish. Le linee nel testo sono riportate per intero (fino alle 8 semimosse salvate), più la ripresa in sospeso sull'ultima casa quando conviene: il materiale citato è contato su tutta la linea, quindi ogni cattura che lo compone compare nel testo e nella riproduzione. I pezzi dello stesso tipo presi da entrambe le parti si compensano: con «7. dxc7 Qxd1+ 8. Kxd1» le donne si scambiano e la frase dice «vincevi tre pedoni», non «una donna e tre pedoni».

Il risultato sta nel campo `explanation` dell'insight (`motif`, `title`, `text`, `better`, `focus`, `fen`, `line`, `bestLine`). Con `insights.VERSION = 6` le analisi già salvate ricevono la spiegazione in lettura, senza riscrivere l'archivio. Il tutor DeepSeek riceve la frase insieme agli altri fatti.

## Limiti

- La variante di Stockfish è a budget limitato e lunga al massimo 8 semimosse: una confutazione più profonda finisce in «perdita di materiale» o in «Deriva dalla linea di Stockfish».
- Lo scambio statico ignora inchiodature e scacchi durante la sequenza di catture.
- Sovraccarico, deviazione, adescamento, zugzwang e fortezze non sono riconosciuti.
- «Non ha case sicure» parla solo delle mosse del pezzo: non esclude difese indirette come un controattacco.

## Verifiche

```bash
.venv/bin/python -m pytest tests/test_explain.py -q
cd web && npm run build && npx playwright test tests/insights.spec.ts
```

I test backend coprono donna in presa, difesa tolta, minaccia non parata, forchetta di cavallo con alternativa vincente, alfiere intrappolato lentamente, matto sulla traversa, matto mancato, svantaggio di posizione, una variante interrotta a metà di un cambio (Ba4 di una partita reale, che perde il cavallo), il ricorso alla linea di Stockfish, una linea migliore che vince la donna alla settima semimossa, lo scambio delle donne con ripresa in sospeso (4. d5 di una partita reale) e mosse senza spiegazione. Il test browser seleziona `3. Qxe5+` nel riepilogo e nella revisione passo passo, controlla la frase e scorre la variante; un secondo test trasforma la stessa spiegazione nel caso «linea di Stockfish» e controlla che la finestra parta dalla linea migliore, la riproduzione automatica, la pausa e le frecce.
