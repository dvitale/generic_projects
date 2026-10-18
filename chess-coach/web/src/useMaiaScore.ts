import {useEffect,useRef,useState} from 'react'
import {Chess} from 'chess.js'
import {maia,type Outcome} from './engine/maia'

export type MaiaScore={elo:number;white:number;outcome:Outcome}

const cache=new Map<string,MaiaScore>()

/** Final positions have a known result: Maia's value head is only asked about positions with legal moves. */
function terminal(fen:string,elo:number):MaiaScore|null{
  const board=new Chess(fen)
  if(board.isCheckmate())return board.turn()==='w'?{elo,white:0,outcome:{win:0,draw:0,loss:1}}:{elo,white:1,outcome:{win:1,draw:0,loss:0}}
  if(board.isDraw()||board.isStalemate())return {elo,white:.5,outcome:{win:0,draw:1,loss:0}}
  return null
}

/** Expected score for White that Maia predicts when both players have the given Elo. */
export function useMaiaScore(fen:string|null,elo:number,enabled:boolean):MaiaScore|null{
  const key=fen&&enabled?`${fen}:${elo}`:''
  const [, setTick]=useState(0)
  const last=useRef<MaiaScore|null>(null)
  useEffect(()=>{
    if(!key||!fen||cache.has(key))return
    const known=terminal(fen,elo)
    if(known){cache.set(key,known);setTick(t=>t+1);return}
    let stopped=false
    const controller=new AbortController()
    // Same short delay as the Stockfish bar: positions skipped while scrolling are not evaluated.
    const timer=setTimeout(()=>{
      maia.predict(fen,elo,elo,controller.signal)
        .then(p=>{cache.set(key,{elo,white:p.whiteExpectedScore,outcome:p.whiteOutcome});if(!stopped)setTick(t=>t+1)})
        .catch(()=>{/* The bar stays on the previous value when Maia is unavailable. */})
    },150)
    return()=>{stopped=true;controller.abort();clearTimeout(timer)}
  },[key])
  if(!key)return null
  const value=cache.get(key)
  if(value){last.current=value;return value}
  return last.current
}
