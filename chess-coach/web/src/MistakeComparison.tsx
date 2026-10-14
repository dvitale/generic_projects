import {useState} from 'react'
import Board from './Board'
import type {Color,Evaluation} from './types'

interface Step {uci:string;san:string;side:Color;number:number;fen:string;checkmate:boolean}
interface Line extends Evaluation {steps:Step[]}
export interface Comparison {
  fen:string;turn:Color;best:Line;actual:Line;lossCp:number|null;criterion:string;
  verification:{acceptedNow:boolean;note:string};
  sameReply?:{attemptReply:string;legalAfterAlternative:boolean;alternativeReply?:string;line?:Line}
}
function score(e:Evaluation){return e.mate!==null?(e.mate>0?`Matto a favore in ${e.mate}`:`Matto contro in ${Math.abs(e.mate)}`):`${e.cp>=0?'+':''}${(e.cp/100).toFixed(2)}`}
const labels={actual:'Il tuo tentativo',best:'Alternativa Stockfish',reply:'Stessa risposta avversaria'}

export default function MistakeComparison({value:c}:{value:Comparison}){
  const [branch,setBranch]=useState<'actual'|'best'|'reply'>('actual')
  const [cursor,setCursor]=useState(0)
  const line=branch==='reply'?c.sameReply?.line??c.best:c[branch]
  const step=line.steps[cursor-1]
  function select(next:typeof branch){setBranch(next);setCursor(0)}
  return <section className="mistake-comparison" aria-label="Confronto verificato delle mosse">
    <p className={c.verification.acceptedNow?'hint':'footnote'}>{c.verification.acceptedNow
      ?'La verifica più approfondita non conferma il rifiuto: questa mossa ora rientra nel criterio dell’esercizio. Il tentativo storico resta registrato.'
      :'La verifica più approfondita conferma che il tentativo non soddisfa il criterio dell’esercizio.'}</p>
    <div className="comparison-lines">
      {(['actual','best'] as const).map(key=><article key={key}><h4>{labels[key]} · {c[key].steps[0]?.san}</h4><strong>{score(c[key])}</strong><p className="variation">{c[key].steps.map(s=>`${s.number}${s.side==='w'?'.':'…'} ${s.san}`).join(' ')}</p><small>Profondità {c[key].depth} · {c[key].nodes.toLocaleString('it-IT')} nodi</small></article>)}
    </div>
    <p className="footnote">Valutazioni della scelta iniziale dal tuo punto di vista. {c.criterion} Un punteggio 0,00 può indicare una difesa che salva la partita; un calo non equivale a materiale perso.</p>
    {c.sameReply&&<p><strong>La stessa risposta cambia effetto? </strong>{c.sameReply.legalAfterAlternative
      ?`Dopo il tentativo: ${c.sameReply.attemptReply}. Dopo l’alternativa: ${c.sameReply.alternativeReply}. Puoi rivedere anche questo confronto sulla scacchiera.`
      :`${c.sameReply.attemptReply}, presente dopo il tentativo, non è legale dopo l’alternativa.`}</p>}
    <details className="comparison-replay"><summary>Rivedi le due idee sulla scacchiera</summary>
      <div className="comparison-controls">{(['actual','best',...(c.sameReply?.line?['reply']:[])] as ('actual'|'best'|'reply')[]).map(key=><button key={key} aria-pressed={branch===key} onClick={()=>select(key)}>{labels[key]}</button>)}</div>
      {branch==='reply'&&<p className="footnote">Qui imponiamo la stessa risposta per capire cosa cambia. Non è necessariamente la migliore difesa e non sostituisce la valutazione dell’alternativa.</p>}
      <div className="comparison-board"><Board fen={step?.fen??c.fen} orientation={c.turn} interactive={false} legalMoves={[]} onMove={()=>{}} lastMove={step?.uci} analysisArrows={cursor===0&&line.pv[0]?[{move:line.pv[0],source:branch==='actual'?'played':'stockfish',rank:1}]:[]}/></div>
      <div className="comparison-controls"><button onClick={()=>setCursor(0)} disabled={cursor===0}>Posizione iniziale</button><button aria-label="Passo precedente del confronto" disabled={cursor===0} onClick={()=>setCursor(n=>n-1)}>←</button><strong>{step?`${step.number}${step.side==='w'?'.':'…'} ${step.san}`:'Prima della scelta'}</strong><button aria-label="Passo successivo del confronto" disabled={cursor===line.steps.length} onClick={()=>setCursor(n=>n+1)}>→</button></div>
      {step?.checkmate&&<p className="hint">Scacco matto in questa variante.</p>}
    </details>
    <small>{c.verification.note} Le varianti mostrano risposte forti, non tutte le possibilità.</small>
  </section>
}
