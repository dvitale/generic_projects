"""Isolated, bounded human-policy experiment. Never updates the live checkpoint ledger.

Stockfish labels are evaluation-only. Training targets remain recorded human moves.
Attack maps are geometric chess-rule labels, not tactical verdicts or safe-move filters.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import json
import math
from pathlib import Path
import random
import sqlite3
import struct
import time

import chess
import chess.engine
import torch
from torch import nn
from torch.nn import functional as F

from dataset import Positions
from features import PROMOTIONS, encode, move_id
from policy import Config, Policy, collate, inputs
from train import evaluate, fingerprint


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def position_key(fen):
    # Canonical legal en-passant field; ignore counters, as in the monthly holdout.
    return ' '.join(chess.Board(fen).fen().split()[:4])


def decode_move(action):
    return chess.Move(action // 320, action // 5 % 64, promotion=PROMOTIONS[action % 5])


def attack_targets(board):
    return [[float(board.is_attacked_by(color, square)) for color in (chess.WHITE, chess.BLACK)]
            for square in chess.SQUARES]


def urgent(board):
    # Only a sampling proxy: a defended or pinned attack need not be a real threat.
    return board.is_check() or any(
        piece.color == board.turn and piece.piece_type != chess.PAWN
        and board.is_attacked_by(not board.turn, square)
        for square, piece in board.piece_map().items())


def item_from_row(row):
    board = chess.Board(row['fen'])
    if not board.is_valid():
        raise ValueError('Invalid board in source data')
    pieces, ep, context = encode(board, row['elo'])
    stored_context = struct.unpack('<8f', row['context'])
    legal = list(struct.unpack(f'<{len(row["legal"])//2}H', row['legal']))
    if (list(row['pieces']) != pieces or list(row['ep']) != ep
        or any(abs(a-b) > 1e-6 for a,b in zip(stored_context,context))
        or len(legal) != len(set(legal))
        or set(legal) != {move_id(m) for m in board.legal_moves}
        or not 0 <= row['target'] < len(legal)):
        raise ValueError(f'Encoding/target mismatch at row {row["id"]}')
    move = decode_move(legal[row['target']])
    if move not in board.legal_moves:
        raise ValueError('Illegal human target')
    return dict(pieces=pieces, ep=ep, context=context, legal=legal, target=row['target'],
                elo=row['elo'], attacks=attack_targets(board), urgent=urgent(board),
                fen=row['fen'], human=move.uci(), game_id=row['game_id'])


def regression_cases():
    # Known diagnostic positions, never claimed to be an unseen evaluation sample.
    moves = 'e2e4 e7e5 g1f3 d8f6 d2d4 f6f4 b1c3 d7d6 d4d5 f8e7 f1d3'.split()
    board, cases = chess.Board(), []
    for ply, uci in enumerate(moves):
        board.push_uci(uci)
        if ply in (4, 6, 8, 10):
            cases.append(dict(fen=board.fen(), elo=600, group='known_regression',
                              id=f'queen-exposure-{ply+1}', human=None))
    cases.append(dict(fen='5r1k/6pp/4Q2N/8/8/8/8/K7 w - - 0 1', elo=600,
                      group='synthetic_sacrifice', id='queen-sacrifice-mate', human=None))
    board = chess.Board()
    for uci in ('f2f3','e7e5','g2g4'):
        board.push_uci(uci)
    cases.append(dict(fen=board.fen(), elo=600, group='synthetic_mate',
                      id='mate-in-one', human=None))
    return cases


def read_rows(path, split):
    with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            'SELECT * FROM positions WHERE split=? ORDER BY id', (split,))]


def prepare(args, output):
    cache = output/'prepared.pt'
    if cache.exists():
        return torch.load(cache, weights_only=True)
    # Read holdout identities only, including test; never evaluate test outcomes.
    with sqlite3.connect(f'file:{Path(args.holdout).resolve()}?mode=ro', uri=True) as db:
        blocked = {position_key(row[0]) for row in db.execute('SELECT fen FROM positions')}
        blocked_games = {row[0] for row in db.execute('SELECT DISTINCT game_id FROM positions')}
    cases = regression_cases()
    blocked.update(position_key(c['fen']) for c in cases)
    rng, train_items, audits, seen = random.Random(args.seed), [], [], set()
    for source, count in ((args.data, args.train_size*4//5), (args.replay, args.train_size//5)):
        rows = read_rows(source, 'train')
        rng.shuffle(rows)
        accepted, excluded = [], Counter()
        for row in rows:
            if len(accepted) >= count:
                break
            if not 600 <= row['elo'] <= 1500:
                excluded['rating'] += 1
                continue
            key = position_key(row['fen'])
            if key in blocked or row['game_id'] in blocked_games:
                excluded['holdout_or_regression'] += 1
                continue
            if key in seen:
                excluded['duplicate_position'] += 1
                continue
            item = item_from_row(row)
            accepted.append(item)
            seen.add(key)
        if len(accepted) != count:
            raise ValueError('Not enough non-overlapping training data')
        train_items.extend(accepted)
        audits.append(dict(source=str(source), selected=len(accepted), exclusions=dict(excluded)))
        del rows
    validation = [item_from_row(row) for row in read_rows(args.validation, 'validation')]
    if any(position_key(item['fen']) in seen for item in validation):
        raise ValueError('Validation overlaps selected training positions')
    # Two separate strata: rating-balanced ordinary positions and urgent-enriched positions.
    for group in ('rating_balanced', 'urgent_enriched'):
        for band in range(600,1500,200):
            pool = [v for v in validation if v['elo']//200*200 == band
                    and len(v['legal']) > 1 and (group != 'urgent_enriched' or v['urgent'])]
            rng.shuffle(pool)
            selected = []
            used = {position_key(c['fen']) for c in cases}
            for item in pool:
                if position_key(item['fen']) in used:
                    continue
                selected.append(item)
                used.add(position_key(item['fen']))
                if len(selected) == args.per_band:
                    break
            if len(selected) != args.per_band:
                raise ValueError('Not enough validation positions in a requested stratum')
            cases.extend(dict(fen=v['fen'], elo=v['elo'], human=v['human'], group=group,
                              id=f'{group}-{band}-{i}', game_id=v['game_id'])
                         for i,v in enumerate(selected))
    report = dict(train_positions=len(train_items), validation_positions=len(validation),
                  audited_encoding_rows=len(train_items)+len(validation),
                  selected_train_validation_overlap=0, sources=audits,
                  train_rating_counts=dict(Counter(str(v['elo']//200*200) for v in train_items)),
                  urgent_train_fraction=sum(v['urgent'] for v in train_items)/len(train_items),
                  validation_rating_counts=dict(Counter(str(v['elo']//200*200) for v in validation)),
                  tactical_cases=len(cases), test='identities excluded, outcomes not evaluated',
                  warning='Attack geometry is not a tactical safety label; rating is not calibrated playing strength')
    result = dict(train=train_items, validation=validation, cases=cases, audit=report)
    torch.save(result, cache)
    write_json(output/'data-audit.json', report)
    print(json.dumps(dict(stage='data_audit', **report)), flush=True)
    return result


def assess_position(engine, case, nodes):
    board = chess.Board(case['fen'])
    assessments = []
    for move in board.legal_moves:
        # Clear hash for comparable independent root-move budgets.
        engine.configure({'Clear Hash': None})
        info = engine.analyse(board, chess.engine.Limit(nodes=nodes), root_moves=[move])
        score = info['score'].pov(board.turn)
        assessments.append(dict(uci=move.uci(), san=board.san(move),
                                cp=score.score(mate_score=100000), mate=score.mate(),
                                expectation=score.wdl(model='sf', ply=board.ply()).expectation(),
                                pv=[m.uci() for m in info.get('pv',[])[:8]], depth=info.get('depth')))
    best_cp = max(a['cp'] for a in assessments)
    best_expected = max(a['expectation'] for a in assessments)
    for a in assessments:
        a['loss_cp'] = max(0, best_cp-a['cp'])
        a['expectation_loss'] = max(0, best_expected-a['expectation'])
        a['allows_mate'] = a['mate'] is not None and a['mate'] < 0 and best_cp > -90000
        a['severe'] = a['allows_mate'] or (a['loss_cp'] >= 200 and a['expectation_loss'] >= .15)
    return dict(**case, assessments=assessments)


def label_cases(cases, args, output):
    path = output/'stockfish-labels.json'
    labels = json.loads(path.read_text()) if path.exists() else []
    if [v['id'] for v in labels] != [v['id'] for v in cases[:len(labels)]]:
        raise ValueError('Cached evaluation manifest mismatch')
    with chess.engine.SimpleEngine.popen_uci(args.stockfish) as engine:
        engine.configure({'Threads':1,'Hash':64})
        write_json(output/'stockfish.json', dict(engine=engine.id, nodes_per_move=args.nodes,
                   limitations='Finite search; engine-labelled severity, not ground truth or human Elo'))
        for case in cases[len(labels):]:
            labels.append(assess_position(engine, case, args.nodes))
            write_json(path, labels)
            if len(labels)%10 == 0:
                print(json.dumps(dict(stage='stockfish', complete=len(labels), total=len(cases))), flush=True)
    return labels


class AttackLearner(nn.Module):
    """Training-only auxiliary head on the unchanged policy's square representations."""
    def __init__(self, policy):
        super().__init__()
        self.policy = policy
        self.attack_head = nn.Linear(policy.cfg.dim, 2)

    def forward(self, pieces, ep, context, legal):
        p = self.policy
        x = p.piece(pieces) + p.ep(ep) + p.square(torch.arange(64,device=pieces.device))[None]
        x = x + p.context(context)[:,None]
        bias = p.geometry(p.relative).permute(2,0,1)[None]
        for block in p.blocks:
            x = block(x,bias)
        x = p.norm(x)
        a = p.origin(x).view(-1,64,5,p.cfg.head_dim)
        b = p.destination(x).view(-1,64,5,p.cfg.head_dim)
        ids = legal.clamp_min(0)
        frm,to,promo = ids//320,ids//5%64,ids%5
        row = torch.arange(x.shape[0],device=x.device)[:,None]
        logits = (a[row,frm,promo]*b[row,to,promo]).sum(-1)/math.sqrt(p.cfg.head_dim)
        logits = logits+p.origin_bias(x)[row,frm,promo]+p.destination_bias(x)[row,to,promo]
        return logits.masked_fill(legal<0,-torch.inf), self.attack_head(x)


def fit_arm(arm, parent, prepared, args, output):
    target = output/f'{arm}.pt'
    if target.exists():
        return target
    torch.manual_seed(args.seed)
    model = Policy(Config(**parent['config']))
    model.load_state_dict(parent['model'])
    wrapper = AttackLearner(model).to(args.device)
    # All arms restart the optimizer identically, so the comparison isolates this pilot.
    optimizer = torch.optim.AdamW(wrapper.parameters(), lr=args.lr, weight_decay=.01)
    items = prepared['train']
    counts = Counter(v['elo']//200 for v in items)
    weights = torch.tensor([min(4.,math.sqrt(max(counts.values())/counts[v['elo']//200]))
                            * (3. if arm != 'control' and v['urgent'] else 1.) for v in items],dtype=torch.double)
    generator = torch.Generator().manual_seed(args.seed)
    start = time.monotonic()
    with (output/f'{arm}.jsonl').open('w') as log:
        for step in range(1,args.steps+1):
            wrapper.train()
            indices = torch.multinomial(weights,args.batch_size,replacement=True,generator=generator).tolist()
            selected = [items[i] for i in indices]
            batch = collate(selected)
            logits, attacks = wrapper(*inputs(batch,args.device))
            human_loss = F.cross_entropy(logits,batch['target'].to(args.device))
            labels = torch.tensor([v['attacks'] for v in selected],device=args.device)
            aux_loss = F.binary_cross_entropy_with_logits(attacks,labels)
            loss = human_loss + (args.aux_weight*aux_loss if arm == 'focus_aux' else 0.)
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite training loss')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(wrapper.parameters(),1.)
            optimizer.step()
            if step%100 == 0 or step == 1:
                record = dict(arm=arm,step=step,human_loss=float(human_loss.detach()),
                              auxiliary_loss=float(aux_loss.detach()),seconds=time.monotonic()-start)
                log.write(json.dumps(record)+'\n'); log.flush()
                print(json.dumps(record),flush=True)
    state = dict(config=parent['config'], model={k:v.detach().cpu() for k,v in model.state_dict().items()},
                 dataset=parent['dataset'], rating_bounds=parent['rating_bounds'],
                 step=parent['step']+args.steps, parent_sha256=fingerprint(args.checkpoint),
                 experiment=arm, inference='policy only; no attack head, Stockfish, search or filtering',
                 training_seconds=time.monotonic()-start,
                 auxiliary={k:v.detach().cpu() for k,v in wrapper.attack_head.state_dict().items()})
    temporary = target.with_suffix('.tmp')
    torch.save(state,temporary); temporary.replace(target)
    return target


def temperature_probs(logits, temperature):
    if temperature <= 0:
        raise ValueError('Temperature must be positive')
    return (logits.float()/temperature).softmax(-1)


@torch.inference_mode()
def compare_model(path, prepared, labelled, args):
    state = torch.load(path,map_location='cpu',weights_only=True)
    model = Policy(Config(**state['config'])).to(args.device)
    model.load_state_dict(state['model']); model.eval()
    human_metrics = evaluate(model,prepared['validation'],args.device,64)
    groups = defaultdict(list)
    for case in labelled:
        board = chess.Board(case['fen'])
        pieces,ep,context = encode(board,case['elo'])
        moves = list(board.legal_moves)
        item = dict(pieces=pieces,ep=ep,context=context,legal=[move_id(m) for m in moves],target=0,elo=case['elo'])
        logits = model(*inputs(collate([item]),args.device))[0]
        lookup = {v['uci']:v for v in case['assessments']}
        measurements = {}
        for temperature in (1., .8, .6):
            probabilities = temperature_probs(logits,temperature).cpu().tolist()
            pairs = [(lookup[move.uci()],p) for move,p in zip(moves,probabilities)]
            top = pairs[max(range(len(pairs)),key=lambda i:pairs[i][1])][0]
            measurements[str(temperature)] = dict(
                severe_mass=sum(p for a,p in pairs if a['severe']),
                mate_mass=sum(p for a,p in pairs if a['allows_mate']),
                expected_loss=sum(p*a['expectation_loss'] for a,p in pairs),
                top_severe=int(top['severe']), top=top['san'],
                human_severe=int(lookup[case['human']]['severe']) if case['human'] else None)
        groups[case['group']].append(dict(id=case['id'],elo=case['elo'],temperatures=measurements))
    summaries = {}
    for group,rows in groups.items():
        summaries[group] = {}
        for temperature in ('1.0','0.8','0.6'):
            values = [v['temperatures'][temperature] for v in rows]
            summaries[group][temperature] = dict(count=len(values), **{
                key: sum(v[key] for v in values if v[key] is not None)/sum(v[key] is not None for v in values)
                if any(v[key] is not None for v in values) else None
                for key in ('severe_mass','mate_mass','expected_loss','top_severe','human_severe')})
    return dict(checkpoint_sha256=fingerprint(path),human_validation=human_metrics,
                tactical=summaries,cases=dict(groups))


def run(args):
    torch.set_num_threads(4)
    output = Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    frozen = {k:v for k,v in vars(args).items() if k != 'output'}
    frozen['fingerprints'] = {k:fingerprint(getattr(args,k)) for k in
                              ('data','replay','validation','holdout','checkpoint','stockfish')}
    frozen['code_sha256'] = {name:fingerprint(Path(__file__).parent/name) for name in
                            ('tactical_lab.py','policy.py','features.py','train.py')}
    manifest = output/'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != frozen:
        raise ValueError('Experiment settings, sources or code changed: choose a new output directory')
    write_json(manifest,frozen)
    prepared = prepare(args,output)
    labelled = label_cases(prepared['cases'],args,output)
    result_path = output/'comparison.json'
    results = json.loads(result_path.read_text()) if result_path.exists() else {}
    if 'baseline' not in results:
        results['baseline'] = compare_model(args.checkpoint,prepared,labelled,args)
        write_json(result_path,results)
        print(json.dumps(dict(stage='baseline',metrics=results['baseline']['human_validation']['all'])),flush=True)
    parent = torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    for arm in ('control','focus','focus_aux'):
        path = fit_arm(arm,parent,prepared,args,output)
        if arm not in results:
            results[arm] = compare_model(path,prepared,labelled,args)
            write_json(result_path,results)
            print(json.dumps(dict(stage='evaluated',arm=arm,metrics=results[arm]['human_validation']['all'])),flush=True)
    lines = ['# Primo confronto tattico — solo laboratorio','',
             'Nessun modello promosso automaticamente. Test finale non valutato.','',
             '| Variante | Top-1 umano | NLL ↓ | Errori gravi: massa ordinaria ↓ | Massa urgenze ↓ | Donna esposta: massa ↓ |',
             '|---|---:|---:|---:|---:|---:|']
    for name,value in results.items():
        h = value['human_validation']['all']; t = value['tactical']
        lines.append(f"| {name} | {h['top1']:.2%} | {h['nll']:.4f} | {t['rating_balanced']['1.0']['severe_mass']:.2%} | {t['urgent_enriched']['1.0']['severe_mass']:.2%} | {t['known_regression']['1.0']['severe_mass']:.2%} |")
    lines += ['', '## Interpretazione e limiti','',
              '- Campione tattico piccolo e bilanciato per fascia: non stima il tasso di blunder in partite complete.',
              '- Errori gravi: perdita di almeno 200 centipawn e 0,15 di aspettativa WDL, oppure matto concesso evitabile. Stockfish a nodi limitati può sbagliare.',
              '- Le posizioni personali già note e i casi sintetici sono riportati separatamente; non dimostrano generalizzazione.',
              '- Le mosse umane, inclusi errori e sacrifici, restano i soli target di scelta mossa. Stockfish non entra nel training.',
              '- Attacchi geometrici, inclusi quelli di pezzi inchiodati, sono etichette ausiliarie, non giudizi di sicurezza.',
              '- Tre bracci con stessi pesi iniziali, seed, budget e nuovo ottimizzatore: control; urgenze ×3; urgenze ×3 con loss ausiliaria 0,2.',
              '- Temperature alternative sono solo una diagnosi offline; il servizio di gioco resta invariato.',
              '- Prima di promuovere un candidato servono campione tattico più ampio e confronti in partite complete con più seed.']
    (output/'RISULTATI.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(stage='complete',output=str(output),promoted=False)),flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default='data/cycles/months/2026-08.train.sqlite')
    p.add_argument('--replay',default='data/cycles/months/2026-08.replay.sqlite')
    p.add_argument('--validation',default='data/cycles/fixed-600-1500.sqlite')
    p.add_argument('--holdout',default='data/cycles/fixed.sqlite')
    p.add_argument('--checkpoint',default='runs/monthly/2026-08/best.pt')
    p.add_argument('--output',default='runs/tactical-pilot-v1')
    p.add_argument('--stockfish',required=True)
    p.add_argument('--train-size',type=int,default=60000)
    p.add_argument('--per-band',type=int,default=10)
    p.add_argument('--nodes',type=int,default=12000)
    p.add_argument('--steps',type=int,default=500)
    p.add_argument('--batch-size',type=int,default=64)
    p.add_argument('--lr',type=float,default=0.00003)
    p.add_argument('--aux-weight',type=float,default=.2)
    p.add_argument('--seed',type=int,default=20261024)
    p.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    return p


if __name__ == '__main__':
    p = parser(); args = p.parse_args()
    if min(args.train_size,args.per_band,args.nodes,args.steps,args.batch_size) < 1 or args.train_size%5:
        p.error('Positive sizes required; train-size must be a multiple of five')
    if args.lr <= 0 or args.aux_weight < 0:
        p.error('Invalid learning rate or auxiliary weight')
    run(args)
