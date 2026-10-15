import {useEffect,useRef,useState} from 'react'
import {api} from './api'
import {whiteValue,type BarValue} from './EvalBar'
import type {Evaluation,Game} from './types'

const cache=new Map<string,BarValue>()

/** Quick Stockfish evaluation (White's perspective) of the game position after `ply` half-moves. */
export function usePositionEval(game:Game|null,ply:number,enabled:boolean):BarValue|null{
  const key=game&&enabled?`${game.id}:${game.initialFen}:${game.moves.slice(0,ply).join(' ')}`:''
  const [, setTick]=useState(0)
  const last=useRef<{game:string;value:BarValue}|null>(null)
  useEffect(()=>{
    if(!key||cache.has(key)||!game)return
    let stopped=false
    // A short delay skips the positions passed through while scrolling the move list.
    const timer=setTimeout(()=>{
      api<{evaluation:Evaluation}>(`/games/${game.id}/evaluation?ply=${ply}`)
        .then(r=>{cache.set(key,whiteValue(r.evaluation,r.evaluation.perspective??'w'));if(!stopped)setTick(t=>t+1)})
        .catch(()=>{/* The bar stays neutral when the engine is unavailable. */})
    },150)
    return()=>{stopped=true;clearTimeout(timer)}
  },[key])
  if(!key||!game)return null
  const value=cache.get(key)
  if(value){last.current={game:game.id,value};return value}
  // Keep the previous value while the new position is evaluated, so the bar moves instead of blinking.
  return last.current?.game===game.id?last.current.value:null
}
