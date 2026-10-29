import {useEffect,useMemo,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import FloatingPanel from './FloatingPanel'
import type {Color} from './types'

export interface Explanation {motif:string;title:string;text:string;better:string|null;focus:string[];fen:string;line:string[];bestLine:string[];bestWins?:boolean}

const STEP_MS=1200

function replay(fen:string,line:string[]){
  const board=new Chess(fen),steps=[{fen:board.fen(),san:'',move:''}]
  for(const uci of line){
    try{const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]});steps.push({fen:board.fen(),san:move.san,move:uci})}catch{break}
  }
  return steps
}

/** The two Stockfish lines on a small board, stepped by hand or played back on their own. */
function LineReplay({explanation,autoplay=false}:{explanation:Explanation;autoplay?:boolean}){
  // In the window, start where the gain is: the better line when it wins material.
  const [which,setWhich]=useState<'line'|'bestLine'>(autoplay&&explanation.bestWins?'bestLine':'line'),[step,setStep]=useState(autoplay?0:1)
  const [playing,setPlaying]=useState(autoplay),[back,setBack]=useState(false)
  const steps=useMemo(()=>replay(explanation.fen,explanation[which]),[explanation,which])
  const at=Math.min(step,steps.length-1),current=steps[at],last=steps.length-1
  const first=(line:string[])=>replay(explanation.fen,line.slice(0,1))[1]?.san
  useEffect(()=>{
    if(!playing)return
    if(at>=last){setPlaying(false);return}
    const timer=setTimeout(()=>{setBack(false);setStep(at+1)},STEP_MS)
    return()=>clearTimeout(timer)
  },[playing,at,last])
  const go=(next:number)=>{setPlaying(false);setBack(next<at);setStep(next)}
  const choose=(line:'line'|'bestLine')=>{setWhich(line);setBack(false);setStep(autoplay?0:1);setPlaying(autoplay)}
  const toggle=()=>{if(playing){setPlaying(false);return}if(at>=last){setBack(false);setStep(0)}setPlaying(true)}
  return <div className="mistake-explanation-board">
    <div className="row" role="group" aria-label="Variante da guardare">
      <button aria-pressed={which==='line'} onClick={()=>choose('line')}>Dopo la tua mossa ({first(explanation.line)})</button>
      <button aria-pressed={which==='bestLine'} onClick={()=>choose('bestLine')}>Mossa migliore ({first(explanation.bestLine)})</button>
    </div>
    <Board fen={current.fen} orientation={explanation.fen.split(' ')[1] as Color} interactive={false} legalMoves={[]} onMove={()=>{}}
      lastMove={back?steps[at+1]?.move:current.move||undefined} animateMove={autoplay} reverseMove={back}/>
    <div className="review-step-controls">
      <button aria-label="Mossa precedente della variante" disabled={at===0} onClick={()=>go(at-1)}>←</button>
      {autoplay&&<button aria-label={playing?'Metti in pausa la variante':'Riproduci la variante'} onClick={toggle}>{playing?'⏸':'▶'}</button>}
      <span role="status">{at===0?'Posizione prima della mossa':`${at}/${last} · ${current.san}`}</span>
      <button aria-label="Mossa successiva della variante" disabled={at===last} onClick={()=>go(at+1)}>→</button>
    </div>
    <p className="footnote">Variante di Stockfish a budget limitato: mostra la difesa più forte trovata, non l’unica possibile.</p>
  </div>
}

/** Plain-language reason for a mistake, with the refuting line replayable on a small board. */
export default function MistakeExplanation({explanation}:{explanation?:Explanation|null}){
  const [open,setOpen]=useState(false)
  if(!explanation)return null
  // Without a verified motif the line itself is the explanation: play it back in a window.
  const engine=explanation.motif==='engine'
  return <div className="mistake-explanation" aria-label="Perché è un errore">
    <span className="insight-badge">{explanation.title}</span>
    <p className="mistake-explanation-text">{explanation.text}</p>
    {explanation.better&&<p className="muted">{explanation.better}</p>}
    {engine
      ?<button className="quiet" onClick={()=>setOpen(true)}>Mostra</button>
      :<button className="quiet" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'Nascondi la variante':'Guarda la variante sulla scacchiera'}</button>}
    {open&&(engine
      ?<FloatingPanel title="Linea di Stockfish" onClose={()=>setOpen(false)}><LineReplay explanation={explanation} autoplay/></FloatingPanel>
      :<LineReplay explanation={explanation}/>)}
  </div>
}
