"""Supplementary CP-loss diagnostic, including positions where WDL has saturated.

This does not rewrite the frozen experiment's criteria or promote a model.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import torch

from serve import Model
from tactical_lab import write_json
from train import fingerprint


def loss_metrics(assessments, probabilities):
    if set(probabilities) != {a['uci'] for a in assessments}:
        raise ValueError('Evaluation and policy move sets differ')
    return {'cp200_mass':sum(probabilities[a['uci']] for a in assessments if a['loss_cp']>=200),
            'cp500_mass':sum(probabilities[a['uci']] for a in assessments if a['loss_cp']>=500),
            'wdl_severe_mass':sum(probabilities[a['uci']] for a in assessments if a['severe'])}


def report(directory, device='cpu'):
    directory = Path(directory)
    frozen = json.loads((directory/'manifest.json').read_text())
    comparisons = json.loads((directory/'comparison.json').read_text())
    labels = json.loads((directory/'stockfish-labels.json').read_text())
    if set(comparisons) != {'baseline','control','focus','focus_aux'}:
        raise ValueError('Wait for all training arms to complete')
    torch.set_num_threads(2)
    results = {}
    for name,original in comparisons.items():
        checkpoint = Path(frozen['checkpoint']) if name == 'baseline' else directory/f'{name}.pt'
        if fingerprint(checkpoint) != original['checkpoint_sha256']:
            raise ValueError('Checkpoint changed after evaluation')
        model = Model(checkpoint,device)
        cases,groups = [],defaultdict(list)
        for case in labels:
            prediction = model.predict(case['fen'],case['elo'])
            probabilities = {m['uci']:m['probability'] for m in prediction['moves']}
            metrics = loss_metrics(case['assessments'],probabilities)
            groups[case['group']].append(metrics)
            cases.append(dict(id=case['id'],group=case['group'],**metrics))
        summaries = {group:{key:sum(r[key] for r in rows)/len(rows) for key in rows[0]}
                     for group,rows in groups.items()}
        results[name] = dict(summaries=summaries,cases=cases)
    write_json(directory/'cp-diagnostic.json',results)
    lines = ['# Sparring partner umano: primo esperimento controllato','',
             'Il motore attivo non è stato modificato. I candidati rimangono nel laboratorio.','',
             '## Verifiche e campione','',
             '- 60.000 esempi di training e 6.877 di validation controllati nella rappresentazione.',
             '- 106 posizioni tattiche: 50 ordinarie, 50 arricchite in urgenze, 4 note e 2 sintetiche.',
             '- Tre addestramenti da 500 passi ciascuno; stessi pesi iniziali, budget e learning rate.',
             '- Nessun target Stockfish: la scelta da apprendere resta quella del giocatore umano.','',
             '## Corrispondenza con le mosse umane e perdite di valutazione','',
             '| Variante | Top-1 umano ↑ | NLL ↓ | P(perdita ≥2 pedoni), ordinarie ↓ | P(perdita ≥2 pedoni), urgenze ↓ | P(perdita ≥5 pedoni), prima di 6…Cd7 ↓ |',
             '|---|---:|---:|---:|---:|---:|']
    names = dict(baseline='Attuale',control='Training normale',focus='Più urgenze',focus_aux='Urgenze + riconoscimento attacchi')
    for name,result in results.items():
        human = comparisons[name]['human_validation']['all']
        final = next(r for r in result['cases'] if r['id']=='queen-exposure-11')
        groups = result['summaries']
        lines.append(f"| {names[name]} | {human['top1']:.2%} | {human['nll']:.4f} | {groups['rating_balanced']['cp200_mass']:.2%} | {groups['urgent_enriched']['cp200_mass']:.2%} | {final['cp500_mass']:.2%} |")
    lines += ['', 'Le colonne indicano la probabilità totale assegnata alle mosse con quella perdita di valutazione, non la percentuale di partite perse. “Pedoni” indica unità di valutazione Stockfish, non necessariamente materiale catturato.','',
              '## Perché servono due misure','',
              'La metrica WDL originale richiede anche una diminuzione di 0,15 dell’aspettativa di risultato. Nelle posizioni già sfavorevoli questa misura può saturare: prima di 6…Cd7 non classificava la perdita di donna come nuovo errore grave. Per questo affianchiamo una misura in centipawn senza il filtro WDL. La revisione è dichiarata e non cambia retroattivamente i criteri del pilota.','',
              '## Criteri esplorativi fissati prima del confronto','',
              '| Variante | Qualità umana conservata | Massa WDL nelle urgenze ridotta ≥10% | Massa WDL ordinaria non peggiora >1 punto |',
              '|---|---|---|---|']
    base = comparisons['baseline']
    for name in ('control','focus','focus_aux'):
        value = comparisons[name]
        h = value['human_validation']['all']; b = base['human_validation']['all']
        human_ok = h['nll']<=b['nll']+.03 and h['top1']>=b['top1']-.01
        urgent_ok = value['tactical']['urgent_enriched']['1.0']['severe_mass'] <= .9*base['tactical']['urgent_enriched']['1.0']['severe_mass']
        ordinary_ok = value['tactical']['rating_balanced']['1.0']['severe_mass'] <= base['tactical']['rating_balanced']['1.0']['severe_mass']+.01
        lines.append(f"| {names[name]} | {'Sì' if human_ok else 'No'} | {'Sì' if urgent_ok else 'No'} | {'Sì' if ordinary_ok else 'No'} |")
    lines += ['', '## Limiti','',
              '- Campione piccolo, una sola inizializzazione casuale e budget breve: risultati esplorativi.',
              '- Validation già usata nei cicli precedenti; test finale non consultato nelle prestazioni.',
              '- Il caso della donna era noto e non misura da solo generalizzazione.',
              '- Valutazioni a 12.000 nodi per mossa; confronti decisivi da confermare con analisi più profonda.',
              '- Campione bilanciato per fascia: non rappresenta la frequenza delle posizioni durante una partita.',
              '- Nessuna stima di Elo, nessun confronto diretto con Maia online, nessuna promozione automatica.']
    (directory/'RAPPORTO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',default='runs/tactical-pilot-v1')
    p.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args = p.parse_args()
    report(args.directory,args.device)
