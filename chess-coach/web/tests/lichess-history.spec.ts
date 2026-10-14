import {test,expect} from '@playwright/test'
import {Chess} from 'chess.js'
import {lichessTarget} from '../src/LichessAnalysis'

test('custom Black start preserves FEN, all moves and absolute selected ply',()=>{
  const initialFen='4k2r/8/8/8/8/8/8/R3K3 b - - 0 17'
  const board=new Chess(initialFen)
  board.move('Rh7');const selected=board.fen();board.move('Ra2')
  const result=lichessTarget(selected,'b',{initialFen,moves:['h8h7','a1a2']},1)
  expect(result.mode).toBe('game')
  const url=new URL(result.url)
  expect(url.hash).toBe('#34');expect(url.searchParams.get('color')).toBe('black')
  const replay=new Chess();replay.loadPgn(decodeURIComponent(url.pathname.slice('/analysis/pgn/'.length)))
  expect(replay.history()).toEqual(['Rh7','Ra2'])
  expect(replay.fen()).toBe(board.fen());replay.undo();expect(replay.fen()).toBe(selected)
})

test('checkmate and promotion survive URL encoding and inconsistent history stays explicit',()=>{
  const initialFen='7k/P7/6K1/8/8/8/8/8 w - - 0 40'
  const board=new Chess(initialFen);board.move('a8=Q#')
  const game={initialFen,moves:['a7a8q']}
  const result=lichessTarget(board.fen(),'w',game)
  expect(result.mode).toBe('game');expect(new URL(result.url).hash).toBe('#79')
  const replay=new Chess();replay.loadPgn(result.pgn)
  expect(replay.isCheckmate()).toBe(true)
  expect(lichessTarget(new Chess().fen(),'w',game).mode).toBe('unavailable')
  expect(lichessTarget(board.fen(),'w',{initialFen,moves:['a7b8q']}).mode).toBe('unavailable')
})

test('long games offer complete PGN instead of silently truncated navigation',()=>{
  const board=new Chess(),initialFen=board.fen()
  const moves=Array.from({length:300},()=>['g1f3','g8f6','f3g1','f6g8']).flat()
  for(const uci of moves)board.move({from:uci.slice(0,2),to:uci.slice(2,4)})
  const result=lichessTarget(board.fen(),'w',{initialFen,moves})
  expect(result.mode).toBe('manual')
  const replay=new Chess();replay.loadPgn(result.pgn)
  expect(replay.history()).toHaveLength(moves.length)
})
