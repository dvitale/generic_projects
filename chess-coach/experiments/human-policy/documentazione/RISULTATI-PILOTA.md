# Confronto pilota — solo laboratorio

Validation: 5233 posizioni in 334 partite. Test finale non valutato.

| Modello | Parametri | Top-1 | Top-3 | Top-5 | NLL ↓ | CPU mediana/mossa |
|---|---:|---:|---:|---:|---:|---:|
| tiny | 864,590 | 30.1% | 50.5% | 60.2% | 2.568 | 2.20 ms |
| small | 4,996,242 | 29.6% | 50.6% | 60.2% | 2.571 | 6.66 ms |
| maia3_5m | 5,230,084 | 52.6% | 80.9% | 89.8% | 1.450 | 12.91 ms |

Top-k: frequenza con cui la mossa umana registrata è fra le k proposte. Non è una misura di Elo o di vittorie.

## Posizioni non presenti nel train e utilità del rating

| Modello | Posizioni | Top-1 | NLL con rating reale ↓ | NLL con rating fisso 1500 ↓ |
|---|---:|---:|---:|---:|
| tiny | 4531 | 27.7% | 2.667 | 2.673 |
| small | 4531 | 27.1% | 2.680 | 2.687 |
| maia3_5m | 4531 | 52.8% | 1.435 | 1.493 |

L'ablazione cambia solo il rating in ingresso: una NLL più bassa col rating reale suggerisce informazione utile su questo campione, non dimostra forza calibrata.

## Limiti del confronto

- 702 posizioni di validation ricompaiono anche nel train (primi quattro campi FEN): split per partita, non per posizione.
- Prototipi: 1.000 passi da 64 esempi; Maia è già addestrato su un corpus molto più ampio. Non è un confronto di architetture a parità di addestramento.
- Campione rapid da un prefisso di settembre 2026, con fasce rare. Maia è un riferimento preaddestrato con dominio diverso.
- Per Maia: sola FEN, storia riempita ripetendo la posizione corrente; rating avversario posto uguale al proprio; nessun tempo. Non riproduce il sito Maia.
- Tutti i modelli: probabilità normalizzate sulle mosse legali, temperatura 1, nessuna ricerca Stockfish, inferenza float32.
- Tempi CPU/GPU: modello già caricato, batch 1, 30 ripetizioni; esclusi caricamento, parsing FEN e generazione delle mosse legali.
- Nessun collegamento con il gioco, le analisi, i dati o il servizio di SparringMate.

## Addestramento eseguito sul PC — 20 ottobre 2026

RTX 4050 Laptop, ambiente Python isolato. Campione: 3.228 partite rapid, 50.120 posizioni; 39.631 train, 5.233 validation, 5.256 test non valutate.

| Modello | Passi × batch | Tempo training | Picco memoria allocata PyTorch |
|---|---:|---:|---:|
| tiny | 1000 × 64 | 34.8 s | 175.0 MiB |
| small | 1000 × 64 | 513.0 s | 498.1 MiB |

Ogni rete ha visto 64.000 esempi campionati con ripetizione: non sono 64.000 posizioni distinte. I tempi comprendono checkpoint e lettura del dataset, non la validation finale. La memoria non include tutta quella del driver.

## Verifiche e decisione

18 test superati: legalità, promozioni, prospettiva del Nero, conservazione delle probabilità, filtro PGN incompleti, ripresa equivalente a training continuo e corrispondenza con il percorso ufficiale Maia.

Il prossimo miglioramento prioritario è ampliare e diversificare i dati, soprattutto nella fascia 600–1200, e misurare la stabilità su più run. Questi numeri non autorizzano ad attribuire una forza Elo al prototipo.

**Nessuna integrazione:** sviluppo, pesi, dati, test e benchmark restano in `experiments/human-policy`. Qualsiasi collegamento con gioco, analisi o interfaccia richiede una successiva conferma esplicita.
