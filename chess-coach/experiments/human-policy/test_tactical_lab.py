from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import struct
from types import SimpleNamespace

import chess
import chess.engine
import pytest
import torch

from features import encode, move_id
from policy import Config, Policy, collate, inputs
from tactical_lab import (AttackLearner, assess_position, attack_targets, compare_model,
                          decode_move, fit_arm, item_from_row, label_cases, parser,
                          position_key, prepare, read_rows, regression_cases,
                          temperature_probs, urgent, write_json)

torch.set_num_threads(2)


def row_for(board, elo=600, identity='train-game', number=1):
    pieces,ep,context = encode(board,elo)
    legal = [move_id(m) for m in board.legal_moves]
    return dict(id=number,game_id=identity,ply=board.ply(),split='train',elo=elo,
                fen=board.fen(en_passant='fen'),pieces=bytes(pieces),ep=bytes(ep),
                context=struct.pack('<8f',*context),legal=struct.pack(f'<{len(legal)}H',*legal),target=0)


@pytest.mark.parametrize('fen', [chess.STARTING_FEN,
    'r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1',
    '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
    '4k3/P7/8/8/8/8/7p/4K3 b - - 0 1'])
def test_real_encoding_roundtrip_and_auxiliary_policy_equivalence(fen):
    board = chess.Board(fen)
    item = item_from_row(row_for(board))
    for move in board.legal_moves:
        assert decode_move(move_id(move)) == move
    cfg = Config(dim=32,layers=1,heads=4,head_dim=8,dropout=0)
    policy = Policy(cfg).eval()
    wrapper = AttackLearner(policy).eval()
    batch = collate([item,{**item,'legal':item['legal'][:1],'target':0}])
    original = policy(*inputs(batch,'cpu'))
    actual,attacks = wrapper(*inputs(batch,'cpu'))
    torch.testing.assert_close(actual,original,rtol=0,atol=0)
    assert attacks.shape == (2,64,2)
    assert torch.isneginf(actual[1,1:]).all()
    attacks.sum().backward()
    assert wrapper.policy.piece.weight.grad.abs().sum() > 0


def test_corrupted_target_or_features_fail_closed():
    row = row_for(chess.Board())
    with pytest.raises(ValueError,match='mismatch'):
        item_from_row({**row,'target':1000})
    with pytest.raises(ValueError,match='mismatch'):
        item_from_row({**row,'pieces':bytes(64)})
    with pytest.raises(ValueError,match='mismatch'):
        item_from_row({**row,'elo':1500})


def test_geometry_does_not_claim_safety_and_preserves_both_colors():
    board = chess.Board(regression_cases()[3]['fen'])
    assert urgent(board)
    assert attack_targets(board)[chess.F4][0] == 1
    # A pinned knight geometrically attacks d5 even when it cannot legally move there.
    board = chess.Board('4r1k1/8/8/8/8/4N3/8/4K3 w - - 0 1')
    assert board.is_pinned(chess.WHITE,chess.E3)
    assert attack_targets(board)[chess.D5][0] == 1
    assert chess.Move.from_uci('e3d5') not in board.legal_moves
    assert not urgent(chess.Board())


def test_position_identity_ignores_counters_and_uncapturable_ep():
    board = chess.Board(); board.push_uci('e2e4')
    assert position_key(board.fen(en_passant='fen')) == position_key(board.fen())
    fields = board.fen().split(); fields[-2:] = ['50','100']
    assert position_key(' '.join(fields)) == position_key(board.fen())


def test_temperature_and_sacrifice_fixture():
    logits = torch.tensor([2.,1.,-torch.inf])
    assert temperature_probs(logits,.6)[0] > temperature_probs(logits,1)[0]
    assert temperature_probs(logits,.6)[2] == 0
    with pytest.raises(ValueError):
        temperature_probs(logits,0)
    board = chess.Board(regression_cases()[4]['fen'])
    for san in ('Qg8+','Rxg8','Nf7#'):
        board.push_san(san)
    assert board.is_checkmate()


class FakeEngine:
    id = {'name':'deterministic test engine'}
    def configure(self,options):
        pass
    def analyse(self,board,limit,root_moves):
        move = root_moves[0]
        # The first legal move is winning; a second one loses; others are slightly inferior.
        index = list(board.legal_moves).index(move)
        score = chess.engine.Mate(-2) if index == 1 else chess.engine.Cp(250 if index == 0 else 200)
        return {'score':chess.engine.PovScore(score,board.turn),'pv':[move],'depth':12}
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass


def test_evaluator_perspective_mate_and_resumption(tmp_path,monkeypatch):
    cases = regression_cases()[:2]
    for case in cases:
        result = assess_position(FakeEngine(),case,100)
        assert result['assessments'][0]['severe'] is False
        assert result['assessments'][1]['allows_mate'] is True
        assert result['assessments'][1]['severe'] is True
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda _:FakeEngine())
    args = SimpleNamespace(stockfish='fake',nodes=100)
    first = label_cases(cases[:1],args,tmp_path)
    assert label_cases(cases,args,tmp_path)[:1] == first
    with pytest.raises(ValueError,match='manifest'):
        label_cases(list(reversed(cases)),args,tmp_path)


def test_all_training_arms_and_evaluation_keep_human_targets(tmp_path):
    cfg = Config(dim=32,layers=1,heads=4,head_dim=8,dropout=0)
    parent = dict(config=asdict(cfg),model=Policy(cfg).state_dict(),dataset={'speed':'rapid'},
                  rating_bounds=[600,1500],step=20)
    checkpoint = tmp_path/'parent.pt'; torch.save(parent,checkpoint)
    item = item_from_row(row_for(chess.Board()))
    prepared = {'train':[item], 'validation':[item]}
    case = dict(fen=item['fen'],elo=600,human=item['human'],group='test',id='one')
    labels = [assess_position(FakeEngine(),case,100)]
    args = SimpleNamespace(seed=5,device='cpu',lr=1e-4,steps=2,batch_size=2,aux_weight=.2,
                           checkpoint=str(checkpoint))
    before = dict(item)
    for arm in ('control','focus','focus_aux'):
        path = fit_arm(arm,parent,prepared,args,tmp_path)
        assert fit_arm(arm,parent,prepared,args,tmp_path) == path
        result = compare_model(path,prepared,labels,args)
        assert result['human_validation']['all']['count'] == 1
        assert 0 <= result['tactical']['test']['1.0']['severe_mass'] <= 1
        state = torch.load(path,weights_only=True)
        Policy(cfg).load_state_dict(state['model'])
        assert state['step'] == 22
    assert item == before
    assert not (tmp_path/'ledger.json').exists()
    assert parser().parse_args(['--stockfish','fake']).steps == 500


def save_rows(path,rows):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE positions(id INTEGER,game_id TEXT,ply INTEGER,split TEXT,elo INTEGER,fen TEXT,pieces BLOB,ep BLOB,context BLOB,legal BLOB,target INTEGER)')
        db.executemany('INSERT INTO positions VALUES(:id,:game_id,:ply,:split,:elo,:fen,:pieces,:ep,:context,:legal,:target)',rows)


def test_prepare_excludes_holdout_games_and_positions(tmp_path):
    import random
    rng = random.Random(93)
    boards, board = [],chess.Board()
    while len(boards)<120:
        if board.is_game_over():
            board = chess.Board()
        board.push(rng.choice(list(board.legal_moves)))
        if urgent(board) and len(list(board.legal_moves))>1:
            boards.append(board.copy())
    validation = [dict(row_for(b,600+(i//2)*200,'val'+str(i),i+1),split='validation')
                  for i,b in enumerate(boards[:10])]
    train = [row_for(b,600,'train'+str(i),i+1) for i,b in enumerate(boards[20:80])]
    train += [dict(validation[0],split='train'),dict(train[0],game_id=validation[1]['game_id'])]
    replay = [row_for(b,800,'replay'+str(i),i+1) for i,b in enumerate(boards[80:100])]
    for name,rows in [('data',train),('replay',replay),('validation',validation),('holdout',validation)]:
        save_rows(tmp_path/f'{name}.sqlite',rows)
    args = SimpleNamespace(**{name:str(tmp_path/f'{name}.sqlite') for name in ('data','replay','validation','holdout')},
                           seed=4,train_size=10,per_band=1)
    prepared = prepare(args,tmp_path)
    assert len(prepared['train']) == 10
    assert len(prepared['cases']) == 16
    assert prepared['audit']['selected_train_validation_overlap'] == 0
    assert prepare(args,tmp_path)['audit'] == prepared['audit']
    assert len(read_rows(tmp_path/'validation.sqlite','validation')) == 10
    write_json(tmp_path/'extra.json',{'ok':True})
    assert json.loads((tmp_path/'extra.json').read_text())['ok']
