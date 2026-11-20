import {useEffect,useMemo,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import FloatingPanel from './FloatingPanel'
import EvalBar,{whiteValue} from './EvalBar'
import {api} from './api'
import {moverOf,objectiveScore} from './evalText'
import type {Color,Evaluation} from './types'

export interface Explanation {motif:string;title:string;text:string;better:string|null;focus:string[];fen:string;line:string[];bestLine:string[];bestWins?:boolean}

const STEP_MS=1200

function replay(fen:string,line:string[]){
  const board=new Chess(fen),steps=[{fen:board.fen(),san:'',move:''}]
  for(const uci of line){
    try{const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]});steps.push({fen:board.fen(),san:move.san,move:uci})}catch{break}
  }
  return steps
}

type Candidate={uci:string;san:string;cp:number;mate:number|null}
type Verdict={uci:string;san:string;cp:number;mate:number|null;loss:number;missedMate:boolean;best:boolean;label:string}
type Analysis={evaluation:Evaluation;terminal:'checkmate'|'draw'|null;candidates:Candidate[];move?:Verdict}
type FreeMove={uci:string;san:string;fen:string}

const analyses=new Map<string,Analysis>()

/** Stockfish on any position (and, with `move`, the verdict on that move), cached for the whole session. */
function useAnalysis(fen:string|null,move?:string):Analysis|null{
  const key=fen?fen+'|'+(move??''):''
  const [, setTick]=useState(0)
  useEffect(()=>{
    if(!key||analyses.has(key))return
    let stopped=false
    // A short delay skips the positions passed through while stepping with the arrows.
    const timer=setTimeout(()=>{
      api<Analysis>('/analysis/position',{fen,move})
        .then(r=>{analyses.set(key,r);if(!stopped)setTick(t=>t+1)})
        .catch(()=>{/* Without the engine the bar stays neutral and no arrow is drawn. */})
    },150)
    return()=>{stopped=true;clearTimeout(timer)}
  },[key])
  return key?analyses.get(key)??null:null
}

const points=(cp:number)=>(cp/100).toFixed(2).replace('.',',')
const legal=(fen:string)=>new Chess(fen).moves({verbose:true}).map(m=>m.from+m.to+(m.promotion??''))

/** The two Stockfish lines on a small board, stepped by hand or played back on their own.
 * With `explore` the board is also an analysis board: evaluation bar, Stockfish's best move as a blue arrow,
 * and moves of one's own off the line, each judged with the review rule. */
function LineReplay({explanation,autoplay=false,explore=false}:{explanation:Explanation;autoplay?:boolean;explore?:boolean}){
  // In the window, and for a missed gain, start where the gain is: the better line when it wins material.
  const [which,setWhich]=useState<'line'|'bestLine'>((autoplay||explanation.motif==='missed_gain')&&explanation.bestWins?'bestLine':'line'),[step,setStep]=useState(autoplay?0:1)
  const [playing,setPlaying]=useState(autoplay),[back,setBack]=useState(false)
  // Moves played off the line: they branch from line step `base`; `freeAt` of them are on the board.
  const [free,setFree]=useState<{base:number;moves:FreeMove[]}|null>(null),[freeAt,setFreeAt]=useState(0)
  const [arrows,setArrows]=useState(true)
  const steps=useMemo(()=>replay(explanation.fen,explanation[which]),[explanation,which])
  useEffect(()=>{setFree(null);setFreeAt(0)},[explanation])
  const at=Math.min(step,steps.length-1),current=steps[at],last=steps.length-1
  const off=!!free&&freeAt>0,shown=off?free!.moves[freeAt-1]:null
  const fen=shown?.fen??current.fen
  const parent=off?(freeAt>1?free!.moves[freeAt-2].fen:steps[free!.base].fen):null
  const analysis=useAnalysis(explore?fen:null),verdict=useAnalysis(explore&&off?parent:null,shown?.uci)?.move
  const first=(line:string[])=>replay(explanation.fen,line.slice(0,1))[1]?.san
  useEffect(()=>{
    if(!playing)return
    if(at>=last){setPlaying(false);return}
    const timer=setTimeout(()=>{setBack(false);setStep(at+1)},STEP_MS)
    return()=>clearTimeout(timer)
  },[playing,at,last])
  const leave=()=>{setFree(null);setFreeAt(0)}
  const go=(next:number)=>{setPlaying(false);setBack(next<at);setStep(next);leave()}
  const choose=(line:'line'|'bestLine')=>{setWhich(line);setBack(false);setStep(autoplay?0:1);setPlaying(autoplay);leave()}
  const toggle=()=>{if(playing){setPlaying(false);return}if(at>=last){setBack(false);setStep(0)}setPlaying(true)}
  const previous=()=>{if(free){setBack(true);setFreeAt(freeAt-1)}else go(at-1)}
  const next=()=>{if(free&&freeAt<free.moves.length){setBack(false);setFreeAt(freeAt+1)}else if(!off)go(at+1)}
  function play(uci:string){
    // The line's own next move just steps forward along it.
    if(!off&&steps[at+1]?.move===uci){go(at+1);return}
    try{
      const board=new Chess(fen),move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]})
      const kept=off?free!.moves.slice(0,freeAt):[]
      setPlaying(false);setBack(false)
      setFree({base:free?.base??at,moves:[...kept,{uci,san:move.san,fen:board.fen()}]});setFreeAt(kept.length+1)
    }catch{/* Not legal here: the board only offers legal moves. */}
  }
  const mover=moverOf(fen),best=analysis?.candidates[0]
  const lastMove=back?(off?free!.moves[freeAt]?.uci:free&&freeAt===0?free.moves[0]?.uci:steps[at+1]?.move):shown?.uci??(current.move||undefined)
  const status=off?`Fuori dalla variante · ${free!.moves.slice(0,freeAt).map(m=>m.san).join(' ')}`:at===0?'Posizione prima della mossa':`${at}/${last} · ${current.san}`
  const board=<Board fen={fen} orientation={explanation.fen.split(' ')[1] as Color} interactive={explore&&!playing} legalMoves={explore&&!playing?legal(fen):[]} onMove={play}
    lastMove={lastMove} animateMove={autoplay} reverseMove={back} analysisArrows={explore&&arrows&&best?[{move:best.uci,source:'stockfish',rank:0}]:[]}/>
  return <div className={`mistake-explanation-board ${explore?'explore':''}`}>
    {!!explanation.bestLine.length&&<div className="row" role="group" aria-label="Variante da guardare">
      <button aria-pressed={which==='line'} onClick={()=>choose('line')}>Dopo la tua mossa ({first(explanation.line)})</button>
      <button aria-pressed={which==='bestLine'} onClick={()=>choose('bestLine')}>Mossa migliore ({first(explanation.bestLine)})</button>
    </div>}
    {explore?<div className="line-replay-stage"><EvalBar value={analysis?whiteValue(analysis.evaluation,mover):null} orientation={explanation.fen.split(' ')[1] as Color}/>{board}</div>:board}
    <div className="review-step-controls">
      <button aria-label="Mossa precedente della variante" disabled={free?freeAt===0&&at===0:at===0} onClick={previous}>←</button>
      {autoplay&&<button aria-label={playing?'Metti in pausa la variante':'Riproduci la variante'} onClick={toggle}>{playing?'⏸':'▶'}</button>}
      <span role="status">{status}</span>
      <button aria-label="Mossa successiva della variante" disabled={free?freeAt===free.moves.length:at===last} onClick={next}>→</button>
    </div>
    {explore&&<div className="line-analysis" aria-label="Analisi di Stockfish">
      {free&&<p className="line-free"><button onClick={()=>go(free.base)}>↩ Torna alla variante</button>{verdict&&<span className={`line-verdict ${verdict.best||verdict.label==='Buona scelta'?'good':verdict.label==='Imprecisione'?'inaccuracy':'mistake'}`}>
        <strong>{verdict.san}</strong>: {verdict.best?'prima scelta di Stockfish':verdict.label.toLowerCase()}{!verdict.best&&verdict.loss>0&&<> (perde {points(verdict.loss)})</>} · valutazione {objectiveScore(verdict,moverOf(parent!))}</span>}</p>}
      {analysis?.terminal?<p className="muted">{analysis.terminal==='checkmate'?'Scacco matto.':'Patta.'}</p>
        :<p className="line-candidates"><span className="muted">Stockfish:</span>{analysis?analysis.candidates.map((c,i)=><button key={c.uci} className="quiet" title={i===0?'Mossa migliore per Stockfish: giocala sulla scacchiera':'Giocala sulla scacchiera'} onClick={()=>play(c.uci)}>{i===0&&'★ '}{c.san} <small>{objectiveScore(c,mover)}</small></button>):<small className="muted">analisi in corso…</small>}</p>}
      <label className="switch"><input type="checkbox" checked={arrows} onChange={e=>setArrows(e.target.checked)}/>Freccia della mossa migliore</label>
    </div>}
    <p className="footnote">Variante di Stockfish a budget limitato: mostra la difesa più forte trovata, non l’unica possibile.{explore&&' Puoi uscire dalla variante muovendo i pezzi: Stockfish valuta ogni posizione e giudica le tue mosse.'}</p>
  </div>
}

/** «Mostra» for a single refuting line, as in a puzzle hint: the better line stays hidden. */
export function ShowLine({fen,line,title}:{fen:string;line:string[];title:string}){
  const [open,setOpen]=useState(false)
  const only=useMemo<Explanation>(()=>({motif:'engine',title,text:'',better:null,focus:[],fen,line,bestLine:[]}),[fen,line,title])
  return <>
    <button className="quiet" onClick={()=>setOpen(true)}>Mostra</button>
    {open&&<FloatingPanel title={title} onClose={()=>setOpen(false)}><LineReplay explanation={only} autoplay/></FloatingPanel>}
  </>
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
      :<LineReplay explanation={explanation} explore/>)}
  </div>
}
