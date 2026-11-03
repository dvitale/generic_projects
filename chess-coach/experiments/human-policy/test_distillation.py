import json
from pathlib import Path
from types import SimpleNamespace
import sys

import chess
import pytest
import torch
from torch.nn import functional as F

from distillation import (align_distribution, batch_with_teacher, choose_samples, combined_loss,
                          fit_arm, item_key, label_samples, tactical_metric, teacher_metric, validate_aligned)
from policy import Config, Policy
from tactical_lab import item_from_row
from test_tactical_lab import row_for

torch.set_num_threads(2)


@pytest.mark.parametrize('fen', [chess.STARTING_FEN,
    'r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1',
    '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
    '4k3/P7/8/8/8/8/7p/4K3 w - - 0 1'])
def test_teacher_alignment_roundtrips_all_legal_moves(fen):
    board=chess.Board(fen); item=item_from_row(row_for(board))
    moves=list(board.legal_moves)
    predictions=[dict(uci=m.uci(),probability=(i+1)/sum(range(1,len(moves)+1))) for i,m in enumerate(moves)]
    aligned=align_distribution(item,list(reversed(predictions)))
    lookup={m.uci():predictions[i]['probability'] for i,m in enumerate(moves)}
    assert aligned==pytest.approx([lookup[m.uci()] for m in moves])
    validate_aligned(item,aligned)
    with pytest.raises(ValueError): align_distribution(item,predictions[:-1])
    with pytest.raises(ValueError): align_distribution(item,predictions+[predictions[0]])
    with pytest.raises(ValueError): validate_aligned(item,[float('nan')]*len(moves))


def test_mixed_loss_matches_exact_human_and_teacher_and_masks_padding():
    logits=torch.tensor([[2.,0.,float('-inf')],[1.,2.,3.]],requires_grad=True)
    legal=torch.tensor([[True,True,False],[True,True,True]])
    target=torch.tensor([0,2]);teacher=torch.tensor([[.2,.8,0.],[.2,.3,.5]])
    lh=F.cross_entropy(logits,target)
    ls=-(teacher*F.log_softmax(logits,-1).masked_fill(~legal,0)).sum(-1).mean()
    assert combined_loss(logits,target,teacher,legal,0)[0].item()==pytest.approx(lh.item())
    assert combined_loss(logits,target,teacher,legal,1)[0].item()==pytest.approx(ls.item())
    loss=combined_loss(logits,target,teacher,legal,.5)[0]
    assert loss.item()==pytest.approx((lh.item()+ls.item())/2)
    loss.backward(); assert torch.isfinite(logits.grad).all()
    with pytest.raises(ValueError): combined_loss(logits,target,teacher,legal,1.1)
    with pytest.raises(ValueError): combined_loss(logits,target,torch.ones_like(teacher),legal,.5)


def test_choose_samples_rejects_overlap_and_stays_deterministic():
    import random
    rng=random.Random(34); board=chess.Board();items=[]
    for n in range(20):
        board.push(rng.choice(list(board.legal_moves)))
        items.append(item_from_row(row_for(board,600,'g'+str(n),n+1)))
    prepared=dict(train=items[:15],validation=items[15:],cases=[],audit={'sources':[{'selected':10},{'selected':5}]})
    train,valid,manifest=choose_samples(prepared,10,3,7)
    assert len(train)==10 and len(valid)==3
    assert choose_samples(prepared,10,3,7)[2]==manifest
    corrupt={**prepared,'validation':[items[0],*items[15:]]}
    with pytest.raises(ValueError,match='overlaps'):
        choose_samples(corrupt,10,3,7)


def test_teacher_cache_works_and_rejects_modified_samples(tmp_path):
    worker=tmp_path/'worker.py'
    worker.write_text('''import sys,json,chess\nfor line in sys.stdin:\n b=json.loads(line);out=[]\n for x in b:\n  moves=list(chess.Board(x["fen"]).legal_moves);out.append([{"uci":m.uci(),"probability":1/len(moves)} for m in moves])\n print(json.dumps(out),flush=True)\n''')
    items=[item_from_row(row_for(chess.Board()))]
    first=label_samples(items,tmp_path,worker,sys.executable,batch_size=1)
    assert len(first[0])==20 and sum(first[0])==pytest.approx(1)
    assert label_samples(items,tmp_path,worker,sys.executable)==first
    assert item_key(items[0])!=item_key({**items[0],'elo':800})
    with pytest.raises(ValueError,match='mismatch'):
        label_samples([{**items[0],'elo':800}],tmp_path,worker,sys.executable)


def test_three_arms_use_same_start_and_student_checkpoint(tmp_path):
    from dataclasses import asdict
    cfg=Config(dim=32,layers=1,heads=4,head_dim=8,dropout=0)
    parent=dict(config=asdict(cfg),model=Policy(cfg).state_dict(),dataset={'speed':'rapid'},rating_bounds=[600,1500],step=4)
    path=tmp_path/'parent.pt';torch.save(parent,path)
    item=item_from_row(row_for(chess.Board()))
    probabilities=[1/len(item['legal'])]*len(item['legal'])
    batch,soft=batch_with_teacher([item],[probabilities],'cpu')
    assert soft.shape==batch['legal'].shape
    args=SimpleNamespace(seed=44,device='cpu',lr=.0001,steps=2,batch_size=2,checkpoint=str(path))
    for name,alpha in [('human',0.),('mixed',.5),('teacher',1.)]:
        output=fit_arm(name,alpha,parent,[item],[probabilities],args,tmp_path)
        state=torch.load(output,weights_only=True)
        assert state['teacher_weight']==alpha and state['step']==6
        model=Policy(cfg);model.load_state_dict(state['model'])
        assert teacher_metric(model,[item],[probabilities],'cpu',1)['count']==1
        from tactical_lab import assess_position
        from test_tactical_lab import FakeEngine
        case=assess_position(FakeEngine(),dict(fen=item['fen'],elo=600,human=item['human'],group='test',id='one'),100)
        assert 0<=tactical_metric(model,[case],'cpu')['summaries']['test']['cp200_mass']<=1
        assert fit_arm(name,alpha,parent,[item],[probabilities],args,tmp_path)==output
    assert not (tmp_path/'ledger.json').exists()
