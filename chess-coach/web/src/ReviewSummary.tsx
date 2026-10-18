import {useEffect,useMemo,useRef} from 'react'
import {Chess} from 'chess.js'
import type {Color,Decision,Evaluation,Game} from './types'
import {classifyMove,MoveClassIcon,moveClassInfo,type MoveClass} from './moveClass'
import {evaluationSeries,type EvaluationPoint} from './evaluationSeries'
import {gameAccuracy} from './accuracy'

const kinds:MoveClass[]=['best','good','inaccuracy','error']

function moveName(d:Decision){const f=d.fen.split(' ');return `${f[5]}${f[1]==='w'?'.':'…'} ${d.playedSan}`}

/** Score from White's side, as on the evaluation bar. */
function whiteScore(e:Evaluation,mover:Color){
  const sign=(e.perspective??mover)==='w'?1:-1
  if(e.mate!==null){const m=e.mate*sign;return {text:`${m>0?'':'-'}#${Math.abs(m)}`,side:m>0?'w':'b'}}
  const v=e.cp*sign/100
  return {text:`${v>0?'+':''}${v.toFixed(2)}`,side:v>=0?'w':'b'}
}

function lineText(d:Decision,san:string[]){
  const f=d.fen.split(' ');let number=Number(f[5]),white=f[1]==='w'
  return san.slice(0,10).map((m,i)=>{const s=white?`${number}. ${m}`:i===0?`${number}… ${m}`:m;if(!white)number++;white=!white;return s}).join(' ')
}

function Sparkline({points,marks,cursor,onPosition}:{points:EvaluationPoint[];marks:Decision[];cursor:number;onPosition:(ply:number)=>void}){
  if(points.length<2)return null
  const W=300,H=64,first=points[0].position,last=points.at(-1)!.position
  const x=(p:number)=>(p-first)/Math.max(1,last-first)*W
  const y=(cp:number|null,mate:Color|null)=>{const v=mate?(mate==='w'?6:-6):Math.max(-6,Math.min(6,(cp??0)/100));return H/2-v/6*(H/2-3)}
  const line=points.map((p,i)=>`${i?'L':'M'} ${x(p.position).toFixed(1)} ${y(p.cp,p.mate).toFixed(1)}`).join(' ')
  const area=`${line} L ${W} ${H} L 0 ${H} Z`
  const selected=points.find(p=>p.position===cursor)
  const at=new Map(points.map(p=>[p.position,p]))
  return <div className="review-graph">
    <svg className="review-sparkline" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true"
      onPointerUp={e=>{const r=e.currentTarget.getBoundingClientRect(),to=(e.clientX-r.left)/r.width*W;onPosition(points.reduce((a,b)=>Math.abs(x(a.position)-to)<=Math.abs(x(b.position)-to)?a:b).position)}}>
      <path d={area} className="spark-white"/>
      <line x1="0" x2={W} y1={H/2} y2={H/2} className="spark-zero"/>
      {selected&&<line x1={x(selected.position)} x2={x(selected.position)} y1="0" y2={H} className="spark-cursor"/>}
    </svg>
    {marks.map(d=>{const p=at.get(d.ply+1);if(!p)return null;const kind=classifyMove(d)
      return <button key={d.ply} className={`spark-mark move-class-${kind}`} style={{left:`${x(p.position)/W*100}%`,top:`${y(p.cp,p.mate)/H*100}%`}}
        title={`${moveName(d)} · ${moveClassInfo[kind].label}`} aria-label={`Grafico: ${moveName(d)} · ${moveClassInfo[kind].label}`} aria-current={cursor===d.ply?'step':undefined} onClick={()=>onPosition(d.ply)}/>})}
  </div>
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
    return {color,name:color===game.playerColor?'Tu':game.source==='pgn'?(color==='w'?'Bianco':'Nero'):game.source==='stockfish'?'Stockfish':`Maia ${game.elo}`,total:moves.length,count,
      sound:moves.length?Math.round(100*(count.best+count.good)/moves.length):null}
  })
  const {points}=useMemo(()=>evaluationSeries(game),[game.initialFen,game.moves,game.analysis])
  const accuracy=useMemo(()=>gameAccuracy(game,points.filter(p=>p.position>=start),new Set(game.assistedPlies??[])),[points,start,game.initialFen,game.assistedPlies])
  const marks=[...byPly.values()].filter(d=>d.ply>=start&&!assisted.has(d.ply)&&['inaccuracy','error'].includes(classifyMove(d)))
  const current=byPly.get(cursor)
  const lines=current?(current.stockfishCandidates??[current.best]).filter(e=>e.san.length):[]
  const mover:Color=current?.fen.split(' ')[1]==='b'?'b':'w'
  const percent=(v:number|null)=>v===null?'—':`${Math.round(v)}%`
  useEffect(()=>{
    const box=list.current,active=box?.querySelector<HTMLElement>('[aria-current="step"]')
    if(!box||!active)return
    const a=active.getBoundingClientRect(),b=box.getBoundingClientRect()
    if(a.top<b.top)box.scrollTop+=a.top-b.top
    else if(a.bottom>b.bottom)box.scrollTop+=a.bottom-b.bottom
  },[cursor])
  return <section className="panel review-summary" aria-label="Riepilogo della partita">
    {reviewed?<table className="review-table" aria-label="Confronto tra i due lati">
      <thead><tr><th scope="col"><span className="side-dot side-dot-w" aria-hidden="true"/>{sides[0].name}</th><td/><th scope="col"><span className="side-dot side-dot-b" aria-hidden="true"/>{sides[1].name}</th></tr></thead>
      <tbody>
        <tr className="review-score"><td><b className="score-chip score-chip-w">{percent(accuracy.w)}</b></td><th scope="row" title="Formula di Lichess: deriva dalla probabilità di vittoria stimata persa a ogni mossa, con più peso ai momenti tesi. Non è un Elo.">Precisione</th><td><b className="score-chip score-chip-b">{percent(accuracy.b)}</b></td></tr>
        <tr className="review-score"><td><b>{percent(sides[0].sound)}</b></td><th scope="row">Senza perdite rilevanti</th><td><b>{percent(sides[1].sound)}</b></td></tr>
        {kinds.map(k=><tr key={k} className={`review-count count-${k}`}><td>{sides[0].count[k]}</td><th scope="row"><MoveClassIcon kind={k}/>{moveClassInfo[k].label}</th><td>{sides[1].count[k]}</td></tr>)}
      </tbody>
    </table>:<p className="muted">Analizza la partita per classificare le mosse di entrambi i lati.</p>}
    <Sparkline points={points} marks={marks} cursor={cursor} onPosition={onPosition}/>
    {reviewed&&<ol className="review-lines" aria-label="Scelte di Stockfish nella posizione mostrata">{lines.length?lines.map((e,i)=>{const s=whiteScore(e,mover)
      return <li key={i}><span className={`score-chip score-chip-${s.side}`}>{s.text}</span><span className="line-moves" title={lineText(current!,e.san)}>{lineText(current!,e.san)}</span></li>
    }):<li className="muted">{cursor>=game.moves.length?'Posizione finale: nessuna scelta da confrontare.':'Nessuna analisi per questa posizione.'}</li>}</ol>}
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
