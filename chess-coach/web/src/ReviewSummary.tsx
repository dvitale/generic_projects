import {useEffect,useMemo,useRef} from 'react'
import {Chess} from 'chess.js'
import type {Color,Decision,Game} from './types'
import {classifyMove,MoveClassIcon,moveClassInfo,type MoveClass} from './moveClass'
import {evaluationSeries} from './evaluationSeries'

const kinds:MoveClass[]=['best','good','inaccuracy','error']

function Sparkline({game,cursor,onPosition}:{game:Game;cursor:number;onPosition:(ply:number)=>void}){
  const {points}=useMemo(()=>evaluationSeries(game),[game.initialFen,game.moves,game.analysis])
  if(points.length<2)return null
  const W=300,H=56,first=points[0].position,last=points.at(-1)!.position
  const x=(p:number)=>(p-first)/Math.max(1,last-first)*W
  const y=(cp:number|null,mate:Color|null)=>{const v=mate?(mate==='w'?6:-6):Math.max(-6,Math.min(6,(cp??0)/100));return H/2-v/6*(H/2-3)}
  const line=points.map((p,i)=>`${i?'L':'M'} ${x(p.position).toFixed(1)} ${y(p.cp,p.mate).toFixed(1)}`).join(' ')
  const area=`${line} L ${W} ${H} L 0 ${H} Z`
  const selected=points.find(p=>p.position===cursor)
  return <svg className="review-sparkline" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true"
    onPointerUp={e=>{const r=e.currentTarget.getBoundingClientRect(),at=(e.clientX-r.left)/r.width*W;onPosition(points.reduce((a,b)=>Math.abs(x(a.position)-at)<=Math.abs(x(b.position)-at)?a:b).position)}}>
    <path d={area} className="spark-white"/>
    <line x1="0" x2={W} y1={H/2} y2={H/2} className="spark-zero"/>
    {selected&&<line x1={x(selected.position)} x2={x(selected.position)} y1="0" y2={H} className="spark-cursor"/>}
  </svg>
}

export default function ReviewSummary({game,cursor,onPosition}:{game:Game;cursor:number;onPosition:(ply:number)=>void}){
  const list=useRef<HTMLOListElement>(null)
  const reviewed=game.analysis?.moves?.length?game.analysis.moves:null
  const byPly=useMemo(()=>new Map((reviewed??[]).filter(d=>game.moves[d.ply]===d.played).map(d=>[d.ply,d] as [number,Decision])),[reviewed,game.moves])
  const rows=useMemo(()=>{
    const board=new Chess(game.initialFen)
    const result:{number:number;w?:{san:string;ply:number};b?:{san:string;ply:number}}[]=[]
    game.moves.forEach((uci,ply)=>{
      const number=board.moveNumber()
      const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]})
      if(result.at(-1)?.number!==number)result.push({number})
      result[result.length-1][move.color]={san:move.san,ply}
    })
    return result
  },[game.initialFen,game.moves])
  const start=game.drill?.startPly??0
  const assisted=new Set(game.assistedPlies??[])
  const sides=(['w','b'] as Color[]).map(color=>{
    const moves=[...byPly.values()].filter(d=>d.ply>=start&&!d.forced&&!assisted.has(d.ply)&&d.fen.split(' ')[1]===color)
    const count=Object.fromEntries(kinds.map(k=>[k,moves.filter(d=>classifyMove(d)===k).length])) as Record<MoveClass,number>
    return {color,name:color===game.playerColor?'Tu':game.source==='pgn'?(color==='w'?'Bianco':'Nero'):`Maia ${game.elo}`,total:moves.length,count,
      sound:moves.length?Math.round(100*(count.best+count.good)/moves.length):null}
  })
  useEffect(()=>{
    const box=list.current,active=box?.querySelector<HTMLElement>('[aria-current="step"]')
    if(!box||!active)return
    const a=active.getBoundingClientRect(),b=box.getBoundingClientRect()
    if(a.top<b.top)box.scrollTop+=a.top-b.top
    else if(a.bottom>b.bottom)box.scrollTop+=a.bottom-b.bottom
  },[cursor])
  return <section className="panel review-summary" aria-label="Riepilogo della partita">
    {reviewed?<div className="review-sides">{sides.map(side=><div key={side.color} className={`review-side side-${side.color}`}>
      <div className="review-side-head"><span className={`side-dot side-dot-${side.color}`} aria-hidden="true"/><strong>{side.name}</strong></div>
      <div className="review-score"><b>{side.sound===null?'—':`${side.sound}%`}</b><small>scelte senza perdite rilevanti</small></div>
      <ul className="review-counts">{kinds.map(k=><li key={k}><MoveClassIcon kind={k}/><span>{moveClassInfo[k].label}</span><b>{side.count[k]}</b></li>)}</ul>
    </div>)}</div>:<p className="muted">Analizza la partita per classificare le mosse di entrambi i lati.</p>}
    <Sparkline game={game} cursor={cursor} onPosition={onPosition}/>
    <ol className="review-moves" ref={list} aria-label="Elenco delle mosse">
      {rows.map(row=><li key={row.number}><span className="move-number">{row.number}.</span>{(['w','b'] as const).map(color=>{
        const move=row[color]
        if(!move)return <span key={color}/>
        const d=byPly.get(move.ply),kind=d?classifyMove(d):null
        return <button key={color} className={kind?`move-cell has-${kind}`:'move-cell'} aria-current={cursor===move.ply?'step':undefined}
          aria-label={`Vai a ${row.number}${color==='w'?'.':'…'} ${move.san}${kind?` · ${moveClassInfo[kind].label}`:''}${assisted.has(move.ply)?' · dopo un suggerimento':''}`} onClick={()=>onPosition(move.ply)}>
          <span>{move.san}{assisted.has(move.ply)&&<span className="assisted-mark" title="Giocata dopo un suggerimento: esclusa dalle statistiche"> 💡</span>}</span>{kind&&kind!=='good'&&<MoveClassIcon kind={kind}/>}
        </button>
      })}</li>)}
    </ol>
    <p className="footnote">Seleziona una mossa: la scacchiera mostra la posizione prima della scelta, con le frecce di confronto.</p>
  </section>
}
