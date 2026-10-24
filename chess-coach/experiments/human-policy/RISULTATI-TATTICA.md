# Sparring partner umano: primo esperimento controllato

Il motore attivo non è stato modificato. I candidati rimangono nel laboratorio.

## Verifiche e campione

- 60.000 esempi di training e 6.877 di validation controllati nella rappresentazione.
- 106 posizioni tattiche: 50 ordinarie, 50 arricchite in urgenze, 4 note e 2 sintetiche.
- Tre addestramenti da 500 passi ciascuno; stessi pesi iniziali, budget e learning rate.
- Nessun target Stockfish: la scelta da apprendere resta quella del giocatore umano.

## Corrispondenza con le mosse umane e perdite di valutazione

| Variante | Top-1 umano ↑ | NLL ↓ | P(perdita ≥2 pedoni), ordinarie ↓ | P(perdita ≥2 pedoni), urgenze ↓ | P(perdita ≥5 pedoni), prima di 6…Cd7 ↓ |
|---|---:|---:|---:|---:|---:|
| Attuale | 37.81% | 2.0959 | 38.70% | 37.08% | 91.70% |
| Training normale | 38.68% | 2.0589 | 38.63% | 36.99% | 93.73% |
| Più urgenze | 38.35% | 2.0619 | 38.32% | 37.09% | 91.72% |
| Urgenze + riconoscimento attacchi | 38.52% | 2.0622 | 38.37% | 37.09% | 91.94% |

Le colonne indicano la probabilità totale assegnata alle mosse con quella perdita di valutazione, non la percentuale di partite perse. “Pedoni” indica unità di valutazione Stockfish, non necessariamente materiale catturato.

## Perché servono due misure

La metrica WDL originale richiede anche una diminuzione di 0,15 dell’aspettativa di risultato. Nelle posizioni già sfavorevoli questa misura può saturare: prima di 6…Cd7 non classificava la perdita di donna come nuovo errore grave. Per questo affianchiamo una misura in centipawn senza il filtro WDL. La revisione è dichiarata e non cambia retroattivamente i criteri del pilota.

## Criteri esplorativi fissati prima del confronto

| Variante | Qualità umana conservata | Massa WDL nelle urgenze ridotta ≥10% | Massa WDL ordinaria non peggiora >1 punto |
|---|---|---|---|
| Training normale | Sì | No | Sì |
| Più urgenze | Sì | No | Sì |
| Urgenze + riconoscimento attacchi | Sì | No | Sì |

## Limiti

- Campione piccolo, una sola inizializzazione casuale e budget breve: risultati esplorativi.
- Validation già usata nei cicli precedenti; test finale non consultato nelle prestazioni.
- Il caso della donna era noto e non misura da solo generalizzazione.
- Valutazioni a 12.000 nodi per mossa; confronti decisivi da confermare con analisi più profonda.
- Campione bilanciato per fascia: non rappresenta la frequenza delle posizioni durante una partita.
- Nessuna stima di Elo, nessun confronto diretto con Maia online, nessuna promozione automatica.

## Esito del 24 ottobre 2026

**Nessun candidato viene promosso.** Tutti migliorano leggermente la previsione
delle mosse umane, ma nessuno riduce del 10% la massa WDL degli errori nelle
urgenze. La misura supplementare in centipawn conferma che il problema della
donna resta: 91,70% nel modello attuale, 91,94% nella variante con compito
ausiliario. Non basta per definirla migliore come sparring partner.

Quattro partite offline del candidato ausiliario contro il riferimento, con
colori alternati, sono finite con 0 vittorie, 1 patta e 3 sconfitte del candidato.
Tutte sono terminate naturalmente, senza raggiungere il limite. Stockfish ha
segnalato 30 errori WDL gravi su 164 mosse del candidato, contro 19 su 166 del
riferimento. È una diagnosi piccola e selezionata: non permette una stima Elo
né una conclusione generale sulla superiorità di un modello.

Il ricontrollo a 120.000 nodi per mossa (dieci volte il budget iniziale) conferma
tutte le classificazioni di perdita di almeno cinque punti nella posizione
prima di 6…Cd7. Il sacrificio sintetico Dg8+ resta un matto corretto in due mosse;
la classificazione di un'altra mossa del caso sintetico cambia, confermando
il limite delle analisi poco profonde.

**73 test automatici distinti passano**, inclusi 16 nuovi test del laboratorio
tattico. Il servizio di gioco continua a usare `2026-08-step20000-b4e7f4ddd752`.
Nessun registro mensile, partita personale o checkpoint attivo è stato modificato.

## Direzione del prossimo esperimento

Il criterio generico di urgenza seleziona il 48,3% dei dati di training: comprende
molti attacchi geometrici innocui. Il prossimo confronto dovrebbe distinguere
minacce a pezzi di maggior valore, catture urgenti e matti immediati, conservando
difese, sacrifici corretti e scelte umane come target. Il pilota attuale non prova
che il compito ausiliario sia inutile; prova che questa formulazione, con questo
budget, non ha risolto il problema.

Prima di altro training esteso: aumentare il campione di questi casi, controllare
la frequenza degli errori umani nelle stesse situazioni e separare gli effetti di
dati, rappresentazione e durata con confronti a budget uguale. Nessun filtro
Stockfish nel gioco e nessuna riduzione automatica della casualità.
