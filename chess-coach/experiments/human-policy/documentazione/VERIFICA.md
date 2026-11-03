# Verifica locale — 20 ottobre 2026

Prova di funzionamento, non certificazione della forza scacchistica.

- GPU: NVIDIA GeForce RTX 4050 Laptop GPU, PyTorch 2.7.1+cu128.
- Test: 13 passed in 3.63s.
- Campione: 824 partite rapid, 12731 posizioni da un prefisso pubblico limitato a 32 MiB.
- Ripresa: tiny ripreso dal passo 100 e arrivato al passo 101.
- Output verificato: 5 mosse, probabilità residua e somma complessiva pari a 1.

| Configurazione | Parametri | Passi della prova | Tempo di training | Picco memoria allocata PyTorch |
|---|---:|---:|---:|---:|
| tiny | 864,590 | 100 | 2.9 s | 63.8 MiB |
| small | 4,996,242 | 10 | 1.1 s | 187.2 MiB |

I tempi sono prove brevi con batch 16: non sono stime di un addestramento completo.
La memoria riportata riguarda le allocazioni PyTorch e non tutta la memoria occupata dal driver.
Il dataset di prova ha solo 385 posizioni train nella fascia 600–799.
Nessuna conclusione sulla forza a 600 o sulla superiorità rispetto a Maia.

I rapporti dettagliati e i pesi restano locali in `runs/`, esclusi da Git.
Il test separato del dataset non è stato consultato per scegliere il modello.
