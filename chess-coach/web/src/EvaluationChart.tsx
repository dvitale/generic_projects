import {useId,useMemo,useState,type KeyboardEvent,type PointerEvent} from 'react'
import type {Game} from './types'
import {evaluationSeries,evaluationText,type EvaluationPoint} from './evaluationSeries'

const W=680,H=310,L=64,R=20,T=28,B=52

export default function EvaluationChart({game,cursor,onPosition,analyzing,onAnalyze}:{game:Game;cursor:number;onPosition:(ply:number)=>void;analyzing:boolean;onAnalyze:()=>void}){
  const {points,start,complete}=useMemo(()=>evaluationSeries(game),[game.initialFen,game.moves,game.analysis])
  const [hover,setHover]=useState<number|null>(null)
  const id=useId()
  const first=points[0]?.position??0,last=points.at(-1)?.position??game.moves.length
  const limit=Math.max(2,Math.ceil(Math.max(0,...points.filter(p=>!p.mate).map(p=>Math.abs(p.cp??0)))/100))
  const x=(position:number)=>L+(position-first)/Math.max(1,last-first)*(W-L-R)
  const y=(p:EvaluationPoint)=>T+(limit-(p.mate?(p.mate==='w'?limit:-limit):(p.cp??0)/100))/(2*limit)*(H-T-B)
  const zero=T+(H-T-B)/2
  const selected=points.find(p=>p.position===cursor)
  const preview=points.find(p=>p.position===hover)??selected
  const paths:string[]=[]
  points.forEach((p,i)=>{
    if(i===0||p.position!==points[i-1].position+1)paths.push(`M ${x(p.position)} ${y(p)}`)
    else paths[paths.length-1]+=` L ${x(p.position)} ${y(p)}`
  })
  const ticks=Array.from(new Set(Array.from({length:Math.min(7,points.length)},(_,i)=>Math.round(i*(points.length-1)/Math.max(1,Math.min(7,points.length)-1))))).map(i=>points[i])
  function nearest(event:PointerEvent<SVGSVGElement>){
    const rect=event.currentTarget.getBoundingClientRect()
    const at=(event.clientX-rect.left)/rect.width*W
    return points.reduce((a,b)=>Math.abs(x(a.position)-at)<=Math.abs(x(b.position)-at)?a:b,points[0])
  }
  function keyboard(event:KeyboardEvent<SVGSVGElement>){
    const index=points.findIndex(p=>p.position===cursor)
    const target=event.key==='Home'?0:event.key==='End'?points.length-1:event.key==='ArrowLeft'?Math.max(0,index-1):event.key==='ArrowRight'?Math.min(points.length-1,index+1):-1
    if(target<0)return
    event.preventDefault();setHover(null);onPosition(points[target].position)
  }
  return <section className="panel evaluation-chart" aria-label="Andamento della valutazione">
    <span className="eyebrow">LA PARTITA, MOSSA DOPO MOSSA</span><h2>Valutazione Stockfish</h2>
    <p className="muted">Sopra lo zero è in vantaggio il Bianco; sotto, il Nero. Ogni punto mostra la posizione dopo una mossa, oltre alla posizione iniziale.</p>
    {analyzing&&<p role="status">Analisi in corso: il grafico si aggiornerà al termine.{points.length>0?' Per ora sono mostrati i risultati precedenti.':''}</p>}
    {!points.length?<><p>Analizza la partita per visualizzare la valutazione di tutte le mosse, di entrambi i colori.</p><button disabled={analyzing||!game.moves.length} onClick={onAnalyze}>Calcola andamento</button></>:<>
      {!complete&&<p className="notice">Questa analisi contiene solo alcune mosse. I tratti mancanti non vengono inventati. <button disabled={analyzing} onClick={onAnalyze}>Completa il grafico</button></p>}
      {start>0&&<p className="footnote">Il grafico inizia dalla parte analizzata della partita{game.drill?', dopo la preparazione del Drill':''}.</p>}
      <svg viewBox={`0 0 ${W} ${H}`} className="evaluation-plot" role="group" aria-roledescription="grafico interattivo" aria-label="Grafico della valutazione: clicca una mossa o usa le frecce sinistra e destra" tabIndex={0} onKeyDown={keyboard}
        onPointerMove={e=>{if(e.pointerType==='mouse')setHover(nearest(e).position)}} onPointerLeave={()=>setHover(null)}
        onPointerUp={e=>{if(e.button===0){setHover(null);onPosition(nearest(e).position)}}}>
        <title>Valutazione dal punto di vista del Bianco</title>
        <desc>Asse orizzontale: mosse giocate. Asse verticale: punti di valutazione Stockfish. M indica un matto, senza valore numerico.</desc>
        <rect x={L} y={T} width={W-L-R} height={zero-T} className="chart-white-zone"/>
        <rect x={L} y={zero} width={W-L-R} height={H-B-zero} className="chart-black-zone"/>
        {[-limit,-limit/2,0,limit/2,limit].map(value=>{
          const cy=T+(limit-value)/(2*limit)*(H-T-B)
          return <g key={value} aria-hidden="true"><line x1={L} x2={W-R} y1={cy} y2={cy} className={value===0?'chart-zero':'chart-grid'}/><text x={L-10} y={cy+4} textAnchor="end">{value>0?'+':''}{value.toLocaleString('it-IT')}</text></g>
        })}
        <text x={L} y={16} className="chart-axis-label">Punti · Bianco + / Nero −</text>
        {ticks.map(p=><g key={p.position} aria-hidden="true"><line x1={x(p.position)} x2={x(p.position)} y1={T} y2={H-B} className="chart-grid"/><text x={x(p.position)} y={H-B+22} textAnchor="middle">{p.initial?'Inizio':p.label.split(' ')[0]}</text></g>)}
        <text x={(L+W-R)/2} y={H-6} textAnchor="middle" className="chart-axis-label">Mosse · numero con … = mossa del Nero</text>
        {paths.map((d,i)=><path key={i} d={d} className="chart-line"/>)}
        {selected&&<line x1={x(selected.position)} x2={x(selected.position)} y1={T} y2={H-B} className="chart-selection"/>}
        {points.map(p=><g key={p.position} data-position={p.position} data-score={p.cp===null?'mate':p.cp} aria-label={`${p.label}: ${evaluationText(p)}`}>
          <title>{p.label} · {evaluationText(p)}</title>
          {p.mate?<path d={`M ${x(p.position)} ${y(p)-5} l 5 5 l -5 5 l -5 -5 Z`} className="chart-mate"/>:<circle cx={x(p.position)} cy={y(p)} r={p.position===cursor?5:3} className={p.position===cursor?'chart-point active':'chart-point'}/>}
        </g>)}
        {preview&&<circle cx={x(preview.position)} cy={y(preview)} r="7" className="chart-hover"/>}
      </svg>
      <div className="chart-readout" aria-live="polite"><strong>{selected?`${selected.label} · ${evaluationText(selected)}`:'La posizione selezionata non ha una valutazione disponibile.'}</strong></div>
      {hover!==null&&preview&&<p className="chart-preview">{preview.label} · {evaluationText(preview)} — clicca per rivedere</p>}
      <label className="field-label" htmlFor={id}>Posizione sul grafico<select id={id} aria-label="Posizione sul grafico" value={selected?.position??''} onChange={e=>{setHover(null);onPosition(Number(e.target.value))}}>{!selected&&<option value="">Scegli una posizione</option>}{points.map(p=><option key={p.position} value={p.position}>{p.label} · {evaluationText(p)}</option>)}</select></label>
      <p className="footnote">Clicca o tocca il grafico per aggiornare la scacchiera. Puoi usare anche ← →, Home e Fine. I rombi sul bordo indicano matto: non rappresentano un punteggio numerico. La scala si adatta ai valori disponibili.</p>
      <details><summary>Tutte le valutazioni</summary><div className="evaluation-table"><table><thead><tr><th>Mossa</th><th>Valutazione · Bianco</th><th>Posizione</th></tr></thead><tbody>{points.map(p=><tr key={p.position}><td>{p.label}</td><td>{evaluationText(p)}</td><td><button onClick={()=>onPosition(p.position)} aria-label={`Rivedi ${p.label}`}>Rivedi</button></td></tr>)}</tbody></table></div></details>
      <p className="footnote">Stima Stockfish, non Elo né materiale perso. Sono riutilizzate le valutazioni salvate per la mossa effettivamente giocata; il riferimento resta il Bianco anche quando ruoti la scacchiera.</p>
    </>}
  </section>
}
