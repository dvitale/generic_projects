import {useEffect,useState} from 'react'
import {Chess} from 'chess.js'
import {api} from './api'
import {maia} from './engine/maia'
import type {Exercise,Game} from './types'

type Comparison={key:string;played?:string;maia?:string;elo?:number;error?:string;loading:boolean}

/** Predictions are requested only after success, on the original decision position. */
export function usePuzzleComparison(exercise:Exercise|null,sessionId:string|undefined,solved:boolean){
  const key=(exercise?.id??'')+':'+(sessionId??'')
  const [data,setData]=useState<Comparison|null>(null)
  const [view,setView]=useState('')
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    if(!solved||!exercise)return
    let stale=false
    const controller=new AbortController()
    setData({key,loading:true})
    const timer=window.setTimeout(()=>{if(!stale)setView(key)},1400)
    ;(async()=>{
      const game=await api<Game>('/games/'+exercise.gameId)
      if(stale)return
      const board=new Chess(game.initialFen)
      for(const move of game.moves.slice(0,exercise.ply))board.move(move)
      const played=game.moves[exercise.ply]
      if(board.fen()!==exercise.fen||!played||!exercise.legalMoves.includes(played))throw new Error('Mossa originale non disponibile per questa posizione.')
      setData({key,played,elo:game.elo,loading:true})
      const prediction=await maia.predict(exercise.fen,game.elo,game.elo,controller.signal)
      if(!stale)setData({key,played,elo:game.elo,maia:prediction.moves[0]?.uci,loading:false})
    })().catch(error=>{if(!stale)setData(current=>({...current,key,loading:false,error:error instanceof Error?error.message:'Confronto non disponibile.'}))})
    return()=>{stale=true;controller.abort();window.clearTimeout(timer)}
  },[key,solved,retry])
  const current=solved&&data?.key===key?data:null
  return {data:current,visible:!!current?.played&&view===key,
    toggle:()=>setView(value=>value===key?'':key),retry:()=>setRetry(value=>value+1)}
}
