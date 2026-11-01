import {useEffect,useState} from 'react'
import {api} from './api'
import type {Prediction} from './engine/maia'

export type MoveQuality='best'|'good'|'inaccuracy'|'mistake'
export interface PieceMove {uci:string;san:string;quality:MoveQuality;drop:number}
/** One badge per target square: Maia's probability, coloured by Stockfish's verdict. */
export interface MoveLabel {to:string;text:string;tone:MoveQuality|'pending';top:boolean;title:string}

export const qualityLabels:Record<MoveQuality,string>={best:'mossa migliore',good:'buona',inaccuracy:'imprecisione',mistake:'errore'}
const order:MoveQuality[]=['best','good','inaccuracy','mistake']
const percent=(p:number)=>`${(p*100).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1})}%`

/** Stockfish's verdict on every move of the selected piece, asked once per position and square. */
export function usePieceMoves(fen:string,square:string|null){
  const [moves,setMoves]=useState<{key:string;list:PieceMove[]}|null>(null),[error,setError]=useState('')
  const key=`${fen}|${square}`
  useEffect(()=>{
    setError('')
    if(!square)return
    let stale=false
    api<{moves:PieceMove[]}>('/review/piece-moves',{fen,square}).then(r=>{if(!stale)setMoves({key,list:r.moves})}).catch(e=>{if(!stale)setError((e as Error).message)})
    return()=>{stale=true}
  },[key])
  return {moves:moves?.key===key?moves.list:null,error}
}

/** Badges for the moves of `square`; promotions to the same square add up and keep their best verdict. */
export function pieceLabels(square:string,legal:string[],prediction:Prediction|null,judged:PieceMove[]|null):MoveLabel[]{
  const top=prediction?.moves[0]?.uci
  const groups=new Map<string,string[]>()
  for(const uci of legal)if(uci.startsWith(square))groups.set(uci.slice(2,4),[...(groups.get(uci.slice(2,4))??[]),uci])
  return [...groups].map(([to,ucis])=>{
    const probability=prediction?ucis.reduce((sum,u)=>sum+(prediction.moves.find(m=>m.uci===u)?.probability??0),0):null
    const verdicts=judged?.filter(m=>ucis.includes(m.uci))??[]
    const best=verdicts.sort((a,b)=>order.indexOf(a.quality)-order.indexOf(b.quality))[0]
    const text=probability===null?'…':percent(probability)
    const verdict=best?`Stockfish: ${qualityLabels[best.quality]}${best.drop>=0.01?` (−${Math.round(best.drop*100)} punti di punteggio atteso)`:''}`:'Stockfish: in valutazione'
    return {to,text,tone:best?.quality??'pending',top:!!top&&ucis.includes(top),
      title:`${best?.san??to} · Maia ${text}${top&&ucis.includes(top)?' (prima scelta)':''} · ${verdict}`}
  })
}
