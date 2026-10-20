import {useMemo,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import type {Color} from './types'

export interface Explanation {motif:string;title:string;text:string;better:string|null;focus:string[];fen:string;line:string[];bestLine:string[]}

function replay(fen:string,line:string[]){
  const board=new Chess(fen),steps=[{fen:board.fen(),san:'',move:''}]
  for(const uci of line){
    try{const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]});steps.push({fen:board.fen(),san:move.san,move:uci})}catch{break}
  }
  return steps
}

/** Plain-language reason for a mistake, with the refuting line replayable on a small board. */
export default function MistakeExplanation({explanation}:{explanation?:Explanation|null}){
  const [open,setOpen]=useState(false),[which,setWhich]=useState<'line'|'bestLine'>('line'),[step,setStep]=useState(1)
  const steps=useMemo(()=>explanation?replay(explanation.fen,explanation[which]):[],[explanation,which])
  if(!explanation)return null
  const color=explanation.fen.split(' ')[1] as Color
  const at=Math.min(step,steps.length-1),current=steps[at]
  const choose=(line:'line'|'bestLine')=>{setWhich(line);setStep(1)}
  return <div className="mistake-explanation" aria-label="Perché è un errore">
    <span className="insight-badge">{explanation.title}</span>
    <p className="mistake-explanation-text">{explanation.text}</p>
    {explanation.better&&<p className="muted">{explanation.better}</p>}
    <button className="quiet" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'Nascondi la variante':'Guarda la variante sulla scacchiera'}</button>
    {open&&<div className="mistake-explanation-board">
      <div className="row" role="group" aria-label="Variante da guardare">
        <button aria-pressed={which==='line'} onClick={()=>choose('line')}>Dopo la tua mossa</button>
        <button aria-pressed={which==='bestLine'} onClick={()=>choose('bestLine')}>Mossa migliore</button>
      </div>
      <Board fen={current.fen} orientation={color} interactive={false} legalMoves={[]} onMove={()=>{}} lastMove={current.move||undefined}/>
      <div className="review-step-controls">
        <button aria-label="Mossa precedente della variante" disabled={at===0} onClick={()=>setStep(at-1)}>←</button>
        <span role="status">{at===0?'Posizione prima della mossa':`${at}/${steps.length-1} · ${current.san}`}</span>
        <button aria-label="Mossa successiva della variante" disabled={at===steps.length-1} onClick={()=>setStep(at+1)}>→</button>
      </div>
      <p className="footnote">Variante di Stockfish a budget limitato: mostra la difesa più forte trovata, non l’unica possibile.</p>
    </div>}
  </div>
}
