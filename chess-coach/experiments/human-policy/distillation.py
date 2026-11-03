"""Isolated human/teacher/mixed policy comparison; never edits the live ledger."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import time

import chess
import torch
from torch.nn import functional as F

from features import move_id
from features import encode
from policy import Config, Policy, collate, inputs
from train import evaluate, fingerprint
from tactical_lab import position_key, write_json

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]


def align_distribution(item, prediction):
    board = chess.Board(item['fen'])
    if not board.is_valid():
        raise ValueError('Invalid teacher position')
    actual = {move_id(m) for m in board.legal_moves}
    if len(item['legal']) != len(actual) or set(item['legal']) != actual:
        raise ValueError('Student legal moves disagree with board')
    if not 0 <= item['target'] < len(item['legal']):
        raise ValueError('Invalid human target')
    moves = {}
    for entry in prediction:
        move = chess.Move.from_uci(entry['uci'])
        value = float(entry['probability'])
        key = move_id(move)
        if move not in board.legal_moves or key in moves or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid teacher move or probability')
        moves[key] = value
    if set(moves) != actual or abs(sum(moves.values())-1) > 1e-4:
        raise ValueError('Incomplete or unnormalized teacher distribution')
    return [moves[key] for key in item['legal']]


def combined_loss(logits, target, teacher, legal, alpha):
    if not 0 <= alpha <= 1:
        raise ValueError('Teacher weight must be in [0,1]')
    if teacher.shape != logits.shape or legal.shape != logits.shape:
        raise ValueError('Incompatible distribution shape')
    if not torch.isfinite(teacher).all() or (teacher < 0).any() or (teacher.masked_select(~legal) != 0).any():
        raise ValueError('Invalid teacher distribution')
    if not torch.allclose(teacher.sum(1),torch.ones(teacher.shape[0],device=teacher.device),atol=1e-4):
        raise ValueError('Unnormalized teacher distribution')
    human = F.cross_entropy(logits.float(),target)
    log_probs = F.log_softmax(logits.float(),dim=-1).masked_fill(~legal,0)
    soft = -(teacher*log_probs).sum(-1).mean()
    return (1-alpha)*human + alpha*soft, human.detach(), soft.detach()


def choose_samples(prepared, count, validation_count, seed):
    if count < 5 or count%5 or validation_count < 1:
        raise ValueError('Training size must be divisible by five; validation size must be positive')
    items = prepared['train']
    # Frozen tactical pilot stores its month and replay groups in this order.
    groups = prepared['audit']['sources']
    n_month,n_replay = (g['selected'] for g in groups)
    if len(items) != n_month+n_replay or count*4//5 > n_month or count//5 > n_replay:
        raise ValueError('Unavailable month/replay sample')
    rng=random.Random(seed)
    indices=rng.sample(range(n_month),count*4//5)+rng.sample(range(n_month,n_month+n_replay),count//5)
    rng.shuffle(indices)
    validation=prepared['validation']
    if validation_count > len(validation):
        raise ValueError('Teacher validation sample too large')
    val_indices=sorted(rng.sample(range(len(validation)),validation_count))
    train=[items[i] for i in indices]
    valid=[validation[i] for i in val_indices]
    valid_keys={position_key(v['fen']) for v in validation}
    valid_games={v['game_id'] for v in validation}
    known_keys={position_key(v['fen']) for v in prepared['cases'] if v['group'] in ('known_regression','synthetic_mate','synthetic_sacrifice')}
    if any(position_key(v['fen']) in valid_keys|known_keys or v['game_id'] in valid_games for v in train):
        raise ValueError('Training overlaps holdout or known diagnostic positions')
    return train,valid,dict(train_indices=indices,validation_indices=val_indices,
        train_rating_counts=dict(Counter(str(v['elo']//200*200) for v in train)),
        teacher_validation_rating_counts=dict(Counter(str(v['elo']//200*200) for v in valid)))


def label_samples(items, output, worker, python, batch_size=32):
    path=output/'teacher-labels.json'
    rows=json.loads(path.read_text()) if path.exists() else []
    if len(rows)>len(items):
        raise ValueError('Teacher cache has extra labels')
    for item,row in zip(items,rows):
        if row['key'] != item_key(item):
            raise ValueError('Teacher cache sample mismatch')
        validate_aligned(item,row['probabilities'])
    if len(rows)==len(items):
        return [r['probabilities'] for r in rows]
    worker_env={**os.environ,'MAIA_THREADS':'2'}
    with subprocess.Popen([str(python),'-u',str(worker)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                          text=True,bufsize=1,env=worker_env) as proc:
        while len(rows)<len(items):
            batch=items[len(rows):len(rows)+batch_size]
            proc.stdin.write(json.dumps([dict(fen=i['fen'],elo=i['elo']) for i in batch])+'\n'); proc.stdin.flush()
            response=proc.stdout.readline()
            if not response:
                raise RuntimeError('Teacher stopped without an answer')
            values=json.loads(response)
            if not isinstance(values,list) or len(values)!=len(batch):
                raise RuntimeError(f'Teacher returned invalid batch: {values}')
            rows.extend(dict(key=item_key(item),probabilities=align_distribution(item,prediction))
                        for item,prediction in zip(batch,values))
            write_json(path,rows)
            print(json.dumps(dict(stage='teacher',complete=len(rows),total=len(items))),flush=True)
        proc.stdin.close()
        if proc.wait(timeout=30):
            raise RuntimeError('Teacher worker failed')
    return [r['probabilities'] for r in rows]


def item_key(item):
    value=json.dumps([item['game_id'],item['fen'],item['elo'],item['legal'],item['target']],separators=(',',':'))
    return hashlib.sha256(value.encode()).hexdigest()


def validate_aligned(item, probabilities):
    if len(probabilities)!=len(item['legal']) or any(not math.isfinite(float(p)) or p<0 for p in probabilities) or abs(sum(probabilities)-1)>1e-4:
        raise ValueError('Invalid cached teacher distribution')


def batch_with_teacher(items, labels, device):
    batch=collate(items)
    width=batch['legal'].shape[1]
    padded=[row+[0.]*(width-len(row)) for row in labels]
    return batch,torch.tensor(padded,dtype=torch.float32,device=device)


def fit_arm(name,alpha,parent,train,teacher,args,output):
    path=output/f'{name}.pt'
    if path.exists():
        return path
    torch.manual_seed(args.seed)
    if args.device=='cuda':
        torch.cuda.manual_seed_all(args.seed)
    model=Policy(Config(**parent['config'])).to(args.device)
    model.load_state_dict(parent['model'])
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=.01)
    sampler=torch.Generator().manual_seed(args.seed)
    counts=Counter(i['elo']//200 for i in train)
    weights=torch.tensor([min(4.,math.sqrt(max(counts.values())/counts[i['elo']//200])) for i in train],dtype=torch.double)
    started=time.monotonic()
    with (output/f'{name}.jsonl').open('w') as log:
        for step in range(1,args.steps+1):
            model.train()
            ids=torch.multinomial(weights,args.batch_size,replacement=True,generator=sampler).tolist()
            batch,soft=batch_with_teacher([train[i] for i in ids],[teacher[i] for i in ids],args.device)
            logits=model(*inputs(batch,args.device))
            loss,human,teacher_loss=combined_loss(logits,batch['target'].to(args.device),soft,batch['legal'].to(args.device)>=0,alpha)
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite loss')
            optimizer.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            optimizer.step()
            if step==1 or step%25==0 or step==args.steps:
                row=dict(stage='train',arm=name,step=step,total=args.steps,loss=float(loss.detach()),
                         human_loss=float(human),teacher_loss=float(teacher_loss),seconds=time.monotonic()-started)
                log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
    state=dict(config=parent['config'],model={k:v.detach().cpu() for k,v in model.state_dict().items()},
               dataset=parent['dataset'],rating_bounds=parent['rating_bounds'],step=parent['step']+args.steps,
               parent_sha256=fingerprint(args.checkpoint),experiment=name,teacher_weight=alpha,
               inference='student network only',training_seconds=time.monotonic()-started)
    temp=path.with_suffix('.tmp');torch.save(state,temp);temp.replace(path)
    return path


@torch.inference_mode()
def teacher_metric(model,valid,labels,device,batch_size):
    model.eval(); total=0.; count=0
    for start in range(0,len(valid),batch_size):
        batch,teacher=batch_with_teacher(valid[start:start+batch_size],labels[start:start+batch_size],device)
        logits=model(*inputs(batch,device))
        logq=F.log_softmax(logits.float(),-1).masked_fill(batch['legal'].to(device)<0,0)
        kl=(torch.where(teacher>0,teacher*teacher.clamp_min(1e-30).log(),0)-teacher*logq).sum(-1)
        total += kl.sum().item(); count += len(kl)
    return dict(count=count,mean_kl_teacher_to_student=total/count)


@torch.inference_mode()
def tactical_metric(model,cases,device):
    groups={}
    for case in cases:
        board=chess.Board(case['fen'])
        pieces,ep,context=encode(board,case['elo'])
        moves=list(board.legal_moves)
        batch=collate([dict(pieces=pieces,ep=ep,context=context,legal=[move_id(m) for m in moves],target=0,elo=case['elo'])])
        probs=model(*inputs(batch,device)).float().softmax(-1)[0].cpu().tolist()
        lookup={v['uci']:v for v in case['assessments']}
        if set(lookup)!={m.uci() for m in moves}:
            raise ValueError('Tactical move set differs from board')
        values=dict(id=case['id'],cp200_mass=sum(p for m,p in zip(moves,probs) if lookup[m.uci()]['loss_cp']>=200),
                    cp500_mass=sum(p for m,p in zip(moves,probs) if lookup[m.uci()]['loss_cp']>=500),
                    wdl_severe_mass=sum(p for m,p in zip(moves,probs) if lookup[m.uci()]['severe']))
        groups.setdefault(case['group'],[]).append(values)
    summaries={group:dict(count=len(rows),**{key:sum(row[key] for row in rows)/len(rows)
               for key in ('cp200_mass','cp500_mass','wdl_severe_mass')}) for group,rows in groups.items()}
    return dict(summaries=summaries,cases=groups,warning='Small stratified development sample; finite Stockfish budget; known cases are not independent')


def evaluate_arm(path,validation,valid,labels,tactical,args):
    state=torch.load(path,map_location='cpu',weights_only=True)
    model=Policy(Config(**state['config'])).to(args.device);model.load_state_dict(state['model']);model.eval()
    return dict(checkpoint_sha256=fingerprint(path),human=evaluate(model,validation,args.device,args.batch_size),
                teacher=teacher_metric(model,valid,labels,args.device,args.batch_size),
                tactical=tactical_metric(model,tactical,args.device))


def run(args):
    torch.set_num_threads(2)
    if args.device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; choose --device cpu explicitly')
    output=Path(args.output).resolve(); runs=(LAB/'runs').resolve()
    if not output.is_relative_to(runs) or not output.name.startswith('distillation-'):
        raise ValueError('Output must be a distillation-* directory under the laboratory runs directory')
    output.mkdir(parents=True,exist_ok=True)
    lock=(output/'.lock').open('w')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise RuntimeError('Experiment already running') from error
    paths={'prepared':Path(args.prepared),'checkpoint':Path(args.checkpoint),'teacher_model':ROOT/'models/maia3/maia3_simplified.onnx',
           'teacher_mapping':ROOT/'backend/data/all_moves_maia3.json','teacher_code':ROOT/'backend/maia.py',
           'teacher_worker':LAB/'distill_teacher.py','code':LAB/'distillation.py','policy':LAB/'policy.py',
           'tactical_cases':Path(args.tactical_cases)}
    manifest={'settings':{k:v for k,v in vars(args).items() if k not in ('output','teacher_python')},
              'teacher_python':str(Path(args.teacher_python).resolve()),'hashes':{k:fingerprint(v) for k,v in paths.items()},
              'teacher':'local maia3_simplified.onnx; position only; opponent rating equals mover rating',
              'teacher_weight':{'human':0.,'mixed':.5,'teacher':1.},'no_automatic_promotion':True}
    m=output/'manifest.json'
    if m.exists() and json.loads(m.read_text())!=manifest:
        raise ValueError('Changed configuration, code or source; use a new output directory')
    write_json(m,manifest)
    prepared=torch.load(args.prepared,map_location='cpu',weights_only=True)
    train,valid,selection=choose_samples(prepared,args.train_size,args.teacher_validation,args.seed)
    tactical=json.loads(Path(args.tactical_cases).read_text())
    if [c['id'] for c in tactical]!=[c['id'] for c in prepared['cases']]:
        raise ValueError('Tactical labels do not match frozen cases')
    write_json(output/'selection.json',selection)
    started=time.monotonic()
    labels=label_samples(train+valid,output,LAB/'distill_teacher.py',Path(args.teacher_python))
    train_labels,val_labels=labels[:len(train)],labels[len(train):]
    parent=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    comparison_path=output/'comparison.json'
    comparison=json.loads(comparison_path.read_text()) if comparison_path.exists() else {}
    if 'baseline' not in comparison:
        comparison['baseline']=evaluate_arm(args.checkpoint,prepared['validation'],valid,val_labels,tactical,args)
        write_json(comparison_path,comparison)
    for name,alpha in [('human',0.),('mixed',.5),('teacher',1.)]:
        path=fit_arm(name,alpha,parent,train,train_labels,args,output)
        if name not in comparison:
            comparison[name]=evaluate_arm(path,prepared['validation'],valid,val_labels,tactical,args)
            write_json(comparison_path,comparison)
            print(json.dumps(dict(stage='evaluation',arm=name,metrics=comparison[name]['human']['all'],teacher=comparison[name]['teacher'])),flush=True)
    lines=['# Distillazione: confronto pilota','',f"Train: {len(train)} posizioni; validation umana: {len(prepared['validation'])}; confronto insegnante: {len(valid)}.",
           '', '| Modello | Top-1 umano ↑ | NLL umana ↓ | Divergenza da Maia ↓ | Perdita ≥2 pedoni: urgenze ↓ | Donna esposta: perdita ≥5 ↓ |', '|---|---:|---:|---:|---:|---:|']
    for name,v in comparison.items():
        h=v['human']['all'];k=v['teacher']['mean_kl_teacher_to_student']
        urgent=v['tactical']['summaries']['urgent_enriched']['cp200_mass']
        queen=next(c['cp500_mass'] for c in v['tactical']['cases']['known_regression'] if c['id']=='queen-exposure-11')
        lines.append(f"| {name} | {h['top1']:.2%} | {h['nll']:.4f} | {k:.4f} | {urgent:.2%} | {queen:.2%} |")
    lines += ['', 'La divergenza misura la somiglianza al modello Maia locale: più bassa non significa automaticamente maggiore forza o utilità didattica.',
              'Validation già usata nello sviluppo; test finale non valutato. Nessun modello attivato automaticamente.',
              'Le colonne tattiche sono probabilità delle mosse con la perdita indicata, in unità di valutazione Stockfish; non sono percentuali di partite perse.',
              'Campione tattico limitato e stratificato, con posizioni personali già note: non dimostra generalizzazione.',
              'Mancano partite complete e test finale: sono necessari prima di proporre un cambiamento nel gioco.']
    (output/'RAPPORTO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(stage='complete',output=str(output),seconds=time.monotonic()-started,promoted=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',default=str(LAB/'runs/tactical-pilot-v1/prepared.pt'))
    p.add_argument('--checkpoint',default=str(LAB/'runs/monthly/2026-08/best.pt'))
    p.add_argument('--tactical-cases',default=str(LAB/'runs/tactical-pilot-v1/stockfish-labels.json'))
    p.add_argument('--teacher-python',default=str(ROOT/'.venv/bin/python'))
    p.add_argument('--output',default=str(LAB/'runs/distillation-pilot-v1'))
    p.add_argument('--train-size',type=int,default=2000)
    p.add_argument('--teacher-validation',type=int,default=400)
    p.add_argument('--steps',type=int,default=100)
    p.add_argument('--batch-size',type=int,default=64)
    p.add_argument('--lr',type=float,default=0.00003)
    p.add_argument('--seed',type=int,default=20261101)
    p.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    args=p.parse_args()
    if min(args.train_size,args.teacher_validation,args.steps,args.batch_size)<1 or args.lr<=0:
        p.error('Positive budgets required')
    run(args)
