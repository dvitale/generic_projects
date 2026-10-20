import {Chess} from 'chess.js'
import type {Game} from './types'

export type Outcome={tone:'win'|'loss'|'draw';title:string;detail:string}

/** How a finished game ended, from the player's side: the reason is read from the final position. */
export function gameOutcome(game:Pick<Game,'initialFen'|'moves'|'result'|'termination'|'playerColor'>):Outcome|null{
  if(!game.result)return null
  const winner=game.result==='1-0'?'w':game.result==='0-1'?'b':null
  const tone=!winner?'draw':winner===game.playerColor?'win':'loss'
  const verdict=tone==='win'?'Hai vinto':tone==='loss'?'Hai perso':'Patta'
  if(game.termination==='resign')return {tone,title:'Hai abbandonato la partita',detail:`${verdict} · ${game.result}`}
  const board=new Chess(game.initialFen)
  try{for(const move of game.moves)board.move({from:move.slice(0,2),to:move.slice(2,4),promotion:move[4]})}
  catch{return {tone,title:verdict,detail:game.result}}
  const side=board.turn()==='w'?'il Bianco':'il Nero'
  if(board.isCheckmate())return {tone,title:`Scacco matto · ${verdict}`,
    detail:`${game.result} · ${tone==='win'?'il re avversario':'il tuo re'} è sotto scacco e non ha mosse per salvarsi.`}
  if(board.isStalemate())return {tone,title:'Stallo · Patta',detail:`${game.result} · ${side} non ha mosse legali ma non è sotto scacco.`}
  if(board.isInsufficientMaterial())return {tone,title:'Patta per materiale insufficiente',detail:`${game.result} · nessuno dei due può più dare scacco matto.`}
  if(board.isThreefoldRepetition())return {tone,title:'Patta per ripetizione',detail:`${game.result} · la stessa posizione si è ripetuta tre volte.`}
  if(board.isDrawByFiftyMoves())return {tone,title:'Patta per la regola delle 50 mosse',detail:`${game.result} · 50 mosse per parte senza catture né mosse di pedone.`}
  return {tone,title:verdict,detail:game.result}
}
