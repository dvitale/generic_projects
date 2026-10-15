import {useEffect,useRef,useState} from 'react'
import {api} from './api'
import {maia} from './engine/maia'
import type {AnalysisArrow} from './Board'
import type {Evaluation,Game} from './types'

type Suggestion={key:string;fen:string;loading:boolean;stockfish?:Evaluation;maia?:{uci:string;san:string;probability:number};error?:string}

const positionKey=(g:Game|null)=>g?`${g.id}:${g.revision}:${g.version}`:''
function score(e:Evaluation){return e.mate!==null?`matto in ${Math.abs(e.mate)}`:`${e.cp>0?'+':''}${(e.cp/100).toFixed(2)}`}

/** First Stockfish choice (server) and first Maia choice (browser) for the current position. */
export function useMoveSuggestion(game:Game|null){
  const [value,setValue]=useState<Suggestion|null>(null)
  const controller=useRef<AbortController|null>(null)
  const key=positionKey(game)
  useEffect(()=>()=>controller.current?.abort(),[key])
  async function request(){
    if(!game)return
    controller.current?.abort()
    const current=new AbortController();controller.current=current
    const base={key,fen:game.fen}
    setValue({...base,loading:true})
    const [sf,human]=await Promise.allSettled([
      api<{stockfish:Evaluation}>(`/games/${game.id}/suggestion`,{version:game.version,revision:game.revision}),
      maia.predict(game.fen,game.elo,game.elo,current.signal),
    ])
    if(current.signal.aborted)return
    setValue({...base,loading:false,
      stockfish:sf.status==='fulfilled'?sf.value.stockfish:undefined,
      // Without the server record the help would go unnoticed: show Maia only alongside Stockfish.
      maia:sf.status==='fulfilled'&&human.status==='fulfilled'?human.value.moves[0]:undefined,
      error:sf.status==='rejected'?(sf.reason as Error).message:human.status==='rejected'?'Maia non disponibile per il suggerimento.':undefined})
  }
  const shown=value?.key===key?value:null
  const arrows:AnalysisArrow[]=[]
  if(shown?.maia)arrows.push({move:shown.maia.uci,source:'maia',rank:1})
  if(shown?.stockfish?.pv[0])arrows.push({move:shown.stockfish.pv[0],source:'stockfish',rank:1})
  return {suggestion:shown,request,arrows}
}

export function SuggestionBox({suggestion,elo}:{suggestion:Suggestion|null;elo:number}){
  if(!suggestion)return null
  return <div className="suggestion-box" role="status" aria-label="Suggerimento">
    {suggestion.loading?<span>Calcolo del suggerimento…</span>:<>
      {suggestion.stockfish&&<span><i className="arrow-swatch source-stockfish"/> Stockfish: <b>{suggestion.stockfish.san[0]}</b> <small>{score(suggestion.stockfish)}</small></span>}
      {suggestion.maia&&<span><i className="arrow-swatch source-maia"/> Maia {elo}: <b>{suggestion.maia.san}</b> <small>{Math.round(suggestion.maia.probability*100)}%</small></span>}
      {suggestion.error&&<span className="error-text">{suggestion.error}</span>}
      <small className="suggestion-note">Mossa assistita: la tua prossima scelta non entra nelle statistiche delle decisioni.</small>
    </>}
  </div>
}
