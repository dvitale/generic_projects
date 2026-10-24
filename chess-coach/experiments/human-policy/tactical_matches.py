"""Small offline paired match diagnostic. No changes to SparringMate or model selection."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

import chess
import chess.engine
import chess.pgn
import torch

from serve import Model
from tactical_lab import write_json
from train import fingerprint


def choose(prediction, board, rng):
    moves = sorted((v['uci'],v['probability']) for v in prediction['moves'])
    legal = {m.uci() for m in board.legal_moves}
    if len(moves)!=len(legal) or {m for m,_ in moves} != legal:
        raise ValueError('Policy/legal move mismatch')
    if any(not math.isfinite(p) or p<0 for _,p in moves) or abs(sum(p for _,p in moves)-1)>1e-3:
        raise ValueError('Invalid policy probabilities')
    draw = rng.random()*sum(p for _,p in moves)
    for move,p in moves:
        draw -= p
        if draw<0:
            return move,p
    return next((m,p) for m,p in reversed(moves) if p>0)


def play_game(models, colors, seed, opening, elo=600, max_plies=160, engine=None, nodes=12000):
    board = chess.Board()
    for uci in opening:
        board.push_uci(uci)
    rngs = {chess.WHITE:random.Random(seed*2),chess.BLACK:random.Random(seed*2+1)}
    records = []
    while not board.is_game_over(claim_draw=True) and len(records)<max_plies:
        side = board.turn
        name = colors[side]
        response = models[name].predict(board.fen(),elo)
        uci,p = choose(response,board,rngs[side])
        move = chess.Move.from_uci(uci)
        record = dict(ply=board.ply(),fen=board.fen(),model=name,uci=uci,san=board.san(move),probability=p)
        if engine:
            engine.configure({'Clear Hash':None})
            best = engine.analyse(board,chess.engine.Limit(nodes=nodes))['score'].pov(side)
            engine.configure({'Clear Hash':None})
            actual = engine.analyse(board,chess.engine.Limit(nodes=nodes),root_moves=[move])['score'].pov(side)
            loss = max(0,best.score(mate_score=100000)-actual.score(mate_score=100000))
            wdl = max(0,best.wdl(model='sf',ply=board.ply()).expectation()-actual.wdl(model='sf',ply=board.ply()).expectation())
            mate = actual.mate() is not None and actual.mate()<0 and best.score(mate_score=100000)>-90000
            record.update(loss_cp=loss,expectation_loss=wdl,severe=mate or (loss>=200 and wdl>=.15))
        records.append(record)
        board.push(move)
    outcome = board.outcome(claim_draw=True)
    pgn = chess.pgn.Game.from_board(board)
    pgn.headers.update(Event='SparringMate isolated paired pilot',White=colors[chess.WHITE],
                       Black=colors[chess.BLACK],Result=outcome.result() if outcome else '*')
    return dict(seed=seed,opening=opening,white=colors[chess.WHITE],black=colors[chess.BLACK],
                result=pgn.headers['Result'],termination=outcome.termination.name if outcome else 'PLY_LIMIT',
                plies=len(records),decisions=records,pgn=str(pgn))


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    manifest = dict(**vars(args),baseline_sha256=fingerprint(args.baseline),
                    candidate_sha256=fingerprint(args.candidate),stockfish_sha256=fingerprint(args.stockfish),
                    code_sha256=fingerprint(__file__))
    path = output/'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError('Match settings changed: choose another output directory')
    write_json(path,manifest)
    torch.set_num_threads(2)
    models = {'baseline':Model(args.baseline,args.device),'candidate':Model(args.candidate,args.device)}
    openings = [[],['e2e4','e7e5'],['d2d4','d7d5'],['g1f3','g8f6']]
    games = []
    with chess.engine.SimpleEngine.popen_uci(args.stockfish) as engine:
        engine.configure({'Threads':1,'Hash':64})
        for pair in range(args.pairs):
            for reverse in (False,True):
                file = output/f'game-{pair}-{int(reverse)}.json'
                colors = {chess.WHITE:'candidate' if reverse else 'baseline',
                          chess.BLACK:'baseline' if reverse else 'candidate'}
                game = json.loads(file.read_text()) if file.exists() else play_game(
                    models,colors,args.seed+pair,openings[pair%len(openings)],args.elo,args.max_plies,engine,args.nodes)
                write_json(file,game)
                games.append(game)
                print(json.dumps({k:game[k] for k in ('seed','white','black','result','termination','plies')}),flush=True)
    totals = defaultdict(lambda:dict(moves=0,severe=0,wins=0,losses=0,draws=0,truncated=0))
    for game in games:
        for record in game['decisions']:
            totals[record['model']]['moves'] += 1
            totals[record['model']]['severe'] += int(record['severe'])
        for color in ('white','black'):
            name = game[color]
            if game['result'] == '*':
                key = 'truncated'
            elif game['result'] == '1/2-1/2':
                key = 'draws'
            else:
                key = 'wins' if (game['result']=='1-0')==(color=='white') else 'losses'
            totals[name][key] += 1
    write_json(output/'summary.json',dict(games=len(games),models=dict(totals),
               warning='Tiny paired diagnostic, not an Elo estimate; truncated games are not adjudicated'))
    (output/'games.pgn').write_text('\n\n'.join(g['pgn'] for g in games)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',default='runs/monthly/2026-08/best.pt')
    p.add_argument('--candidate',required=True)
    p.add_argument('--stockfish',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--pairs',type=int,default=2)
    p.add_argument('--max-plies',type=int,default=160)
    p.add_argument('--nodes',type=int,default=12000)
    p.add_argument('--elo',type=int,default=600)
    p.add_argument('--seed',type=int,default=20261024)
    p.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    args = p.parse_args()
    if min(args.pairs,args.max_plies,args.nodes)<1:
        p.error('Positive budgets required')
    run(args)
