import {useEffect,useMemo,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import RatingPanel from './RatingPanel'
import InfoNote from './InfoNote'
import {api} from './api'
import {useBoardOrientation} from './boardFlip'
import {evaluationSeries,evaluationText,type EvaluationPoint} from './evaluationSeries'
import {gameAccuracy,winPercent} from './accuracy'
import {classifyMove,MoveClassIcon,moveClassInfo,type MoveClass} from './moveClass'
import type {Decision,Game} from './types'
import OpeningStatus,{openingStatus} from './OpeningStatus'

const kinds:MoveClass[]=['best','good','inaccuracy','error','blunder','missedMate']
const critical:MoveClass[]=['inaccuracy','error','blunder','missedMate']

/** Drill review, as at the end of a Maia Chess drill: replay, evaluation chart, critical decisions, accuracy and Maia level. */
export default function DrillReview({game,onGame,onReview,onAgain,onNext}:{game:Game;onGame:(g:Game)=>void;onReview:()=>void;onAgain:()=>void;onNext:()=>void}){
  const drill=game.drill!
  const start=drill.startPly
  const ready=!!game.analysis&&game.analysis.version===game.version
  const [progress,setProgress]=useState(0)
  const [error,setError]=useState('')
  const [ply,setPly]=useState(game.version)
  const [playing,setPlaying]=useState(false)
  const orientation=useBoardOrientation(game.playerColor)
  // Stockfish started when the drill ended: follow the job, then reload the game with its analysis.
  useEffect(()=>{
    if(ready)return
    let stopped=false,timer:ReturnType<typeof setTimeout>
    async function poll(){
      try{
        let id=game.analysisJobId
        if(!id)id=(await api<{jobId:string}>(`/games/${game.id}/analysis`,{})).jobId
        const job=await api<{status:string;progress:number;error?:string}>('/jobs/'+id)
        if(stopped)return
        setProgress(job.progress)
        if(job.status==='complete'){onGame(await api<Game>('/games/'+game.id));return}
        if(job.status==='error')throw new Error(job.error||'Analisi non riuscita')
        timer=setTimeout(poll,700)
      }catch(e){if(!stopped)setError((e as Error).message)}
    }
    void poll()
    return()=>{stopped=true;clearTimeout(timer)}
  },[game.id,game.version,ready])
  const positions=useMemo(()=>{const c=new Chess(game.initialFen),out=[c.fen()];for(const m of game.moves){c.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]});out.push(c.fen())}return out},[game.initialFen,game.moves])
  useEffect(()=>{if(!playing)return;if(ply>=game.version){setPlaying(false);return}const t=setTimeout(()=>setPly(p=>p+1),900);return()=>clearTimeout(t)},[playing,ply,game.version])
  const {points}=useMemo(()=>evaluationSeries(game),[game.initialFen,game.moves,game.analysis])
  const drillPoints=points.filter(p=>p.position>=start)
  const assisted=new Set(game.assistedPlies??[])
  const mine=(game.analysis?.moves??[]).filter(d=>d.ply>=start&&game.moves[d.ply]===d.played&&d.fen.split(' ')[1]===game.playerColor&&!d.forced&&!assisted.has(d.ply))
  const count=Object.fromEntries(kinds.map(k=>[k,mine.filter(d=>classifyMove(d)===k).length])) as Record<MoveClass,number>
  const accuracy=ready?gameAccuracy(game,drillPoints,assisted)[game.playerColor]:null
  const sound=mine.length?Math.round(100*(count.best+count.good)/mine.length):null
  const moments=mine.filter(d=>critical.includes(classifyMove(d))).sort((a,b)=>a.ply-b.ply).slice(0,5)
  const first=drillPoints[0],last=drillPoints.at(-1)
  const feedback=accuracy===null?null:accuracy>=90?'Ottima prova: hai giocato con grande precisione.':accuracy>=70?'Buona prova: la maggior parte delle tue mosse era solida.':'Questa apertura va allenata ancora.'
  const serious=count.blunder+count.missedMate
  const exit=openingStatus(game,game.version)
  const exitPly=exit&&!exit.inBook?exit.exitPly:null
  const move=(d:Decision)=>{const f=d.fen.split(' ');return `${f[5]}${f[1]==='w'?'.':'…'} ${d.playedSan}`}
  const lost=(d:Decision)=>d.best.mate!==null||d.actual.mate!==null?'':` · perde ${(d.loss/100).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})}`
  return <div className="drill-review" aria-label="Valutazione del drill">
    <section className="panel drill-review-head"><span className="eyebrow">VALUTAZIONE DEL DRILL</span><h2>{drill.name}</h2>
      <OpeningStatus game={game} ply={game.version} engine={game.engineLabel??'Maia'}/>
      <p className="muted">{mine.length||drill.decisions} tue mosse analizzate · giochi col {game.playerColor==='w'?'Bianco':'Nero'} · Maia {game.elo}</p>
      {!ready&&!error&&<div role="status"><p>Stockfish analizza le tue mosse… {progress}%</p><progress value={progress} max={100}/></div>}
      {error&&<p className="alert" role="alert">{error}</p>}
    </section>
    <div className="drill-review-grid">
      <section className="panel drill-replay"><h3>Replica</h3>
        <Board fen={positions[ply]} orientation={orientation} legalMoves={[]} interactive={false} onMove={()=>{}} lastMove={ply>0?game.moves[ply-1]:undefined} animateMove/>
        <div className="review-controls"><button aria-label="Inizio del drill" onClick={()=>{setPlaying(false);setPly(start)}} disabled={ply<=start}>⏮</button><button aria-label="Mossa precedente" onClick={()=>{setPlaying(false);setPly(p=>Math.max(start,p-1))}} disabled={ply<=start}>◀</button>
          <button aria-label={playing?'Pausa':'Riproduci'} onClick={()=>{if(!playing&&ply>=game.version)setPly(start);setPlaying(p=>!p)}}>{playing?'⏸':'▶ Riproduci'}</button>
          <button aria-label="Mossa successiva" onClick={()=>{setPlaying(false);setPly(p=>Math.min(game.version,p+1))}} disabled={ply>=game.version}>▶</button><button aria-label="Fine del drill" onClick={()=>{setPlaying(false);setPly(game.version)}} disabled={ply>=game.version}>⏭</button></div>
        <p className="footnote">{ply<=start?'Fine della linea: da qui il drill.':`Dopo la semimossa ${ply-start} del drill.`}</p>
      </section>
      <section className="panel drill-review-body">
        {ready&&<>
          <h3>Andamento della valutazione</h3>
          <DrillChart points={drillPoints} decisions={mine} cursor={ply} onPosition={p=>{setPlaying(false);setPly(p)}}/>
          {first&&last&&<p className="drill-review-swing">All’inizio del drill <b>{evaluationText(first)}</b>, alla fine <b>{evaluationText(last)}</b> (dal lato del Bianco).</p>}
          <div className="drill-review-scores"><div><b className="score-chip">{accuracy===null?'—':`${Math.round(accuracy)}%`}</b><small>Precisione</small></div><div><b>{sound===null?'—':`${sound}%`}</b><small>Senza perdite rilevanti</small></div></div>
          {feedback&&<p role="status"><strong>{feedback}</strong>{serious>0&&` Attento: ${serious} ${serious===1?'errore grave':'errori gravi'}.`}</p>}
          <ul className="drill-review-counts">{kinds.map(k=><li key={k}><MoveClassIcon kind={k}/> {moveClassInfo[k].label} <b>{count[k]}</b></li>)}</ul>
          <h3>Decisioni critiche</h3>
          {moments.length?<ol className="drill-moments">{moments.map(d=>{const k=classifyMove(d);return <li key={d.ply}><button onClick={()=>{setPlaying(false);setPly(d.ply)}} aria-label={`Vai a ${move(d)} · ${moveClassInfo[k].label}`}><MoveClassIcon kind={k}/> <b>{move(d)}</b> · {moveClassInfo[k].label}{lost(d)}{d.best.san[0]&&d.best.pv[0]!==d.played?` · meglio ${d.best.san[0]}`:''}{d.ply===exitPly?' · prima mossa fuori teoria':''}</button></li>})}</ol>:<p className="muted">Nessuna imprecisione: ogni tua mossa ha perso meno di 0,80.</p>}
        </>}
      </section>
      <div className="drill-review-side">
        {ready&&<RatingPanel game={game} disabled={false} auto onRated={rating=>onGame({...game,rating})}/>}
        <section className="panel"><button className="primary full" onClick={onAgain}>Rigioca la stessa linea →</button><button className="full" onClick={onNext}>Prossimo drill</button><button className="full" onClick={onReview}>Rivedi nel dettaglio →</button>
          <InfoNote summary="Come si legge">Precisione e classi sono quelle di Rivedi, calcolate solo sulle tue mosse dopo la linea, senza le mosse obbligate e quelle giocate dopo un suggerimento. Su Maia Chess un errore grave è una perdita di almeno 10 punti di probabilità di vittoria; qui valgono le soglie del resto dell’app (imprecisione da 0,80, errore da 1,80, errore grave da 3,00). Il confronto con Maia dice a quale livello le tue mosse somigliano di più, non quanto sei forte.</InfoNote></section>
      </div>
    </div>
  </div>
}

function DrillChart({points,decisions,cursor,onPosition}:{points:EvaluationPoint[];decisions:Decision[];cursor:number;onPosition:(ply:number)=>void}){
  if(points.length<2)return <p className="muted">Troppe poche posizioni per il grafico.</p>
  const W=320,H=90,first=points[0].position,last=points.at(-1)!.position
  const x=(p:number)=>(p-first)/Math.max(1,last-first)*W,y=(p:EvaluationPoint)=>H-winPercent(p)/100*H
  const line=points.map((p,i)=>`${i?'L':'M'} ${x(p.position).toFixed(1)} ${y(p).toFixed(1)}`).join(' ')
  const at=new Map(points.map(p=>[p.position,p]))
  return <div className="drill-chart">
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Probabilità di vittoria del Bianco durante il drill">
      <path d={`${line} L ${W} ${H} L 0 ${H} Z`} className="spark-white"/><line x1="0" x2={W} y1={H/2} y2={H/2} className="spark-zero"/>
      {cursor>=first&&cursor<=last&&<line x1={x(cursor)} x2={x(cursor)} y1="0" y2={H} className="spark-cursor"/>}
    </svg>
    {decisions.map(d=>{const p=at.get(d.ply+1);if(!p)return null;const k=classifyMove(d)
      return <button key={d.ply} className={`spark-mark move-class-${k}`} style={{left:`${x(p.position)/W*100}%`,top:`${y(p)/H*100}%`}} title={`${d.playedSan} · ${moveClassInfo[k].label}`} aria-label={`Grafico: ${d.playedSan} · ${moveClassInfo[k].label}`} onClick={()=>onPosition(d.ply)}/>})}
  </div>
}
