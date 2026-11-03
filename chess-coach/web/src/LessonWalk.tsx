import {useState} from 'react'
import Board,{type AnalysisArrow} from './Board'
import {api} from './api'
import {SCORE_NOTE,objectiveScore} from './evalText'
import {useBoardOrientation} from './boardFlip'
import type {Color} from './types'

type Verdict='game'|'good'|'partial'|'weak'|'other'
interface Score {cp:number;mate:number|null}
interface Judged extends Score {san:string;loss:number;label:string;best:string;bestScore:Score;live?:boolean}
export interface Run {firstPly:number;fromNumber:number;id:string;startedAt:string;finishedAt:string|null;nextPly:number;answered:number;found:number;clean:number;total:number}
export interface WalkItem {id:string;title:string;game:number;side:Color;event:string;opening:string;result:string|null;summary:string;total:number;current:Run|null;last:Run|null;best:Run|null}
interface Reply {ply:number;san:string;uci:string;number:number;white:boolean;note:string;page:number;engine:Judged}
interface Step {walk:string;ply:number;number:number;total:number;fen:string;turn:Color;line:string;lastMove:string|null;replies:Reply[];question:string;hints:string[];lesson:string|null;legalMoves:string[];run:Run}
interface Considered extends Score {san:string;uci:string;verdict:Verdict;note:string}
interface Answer {success:boolean;verdict:Verdict;verdictLabel:string;move:string;uci:string;note:string|null;counted:boolean;hints:number;played:string;playedUci:string;explanation:string;bookIdea:string|null;engineNote:string|null;page:number;lesson:string|null;
  engine:{depth:number;lines:(Score&{san:string;pv:string[]})[];move:Judged;played:Judged};moves:Considered[];nextPly:number|null;finished:boolean;tail:Reply[];result:string|null;ending:string|null;citation:string;run:Run;fenAfter:string;lastMove:string}

const VERDICT:Record<Verdict,string>={game:'Partita',good:'Valida',partial:'Sensata',weak:'Debole',other:'Fuori lista'}
const moveName=(r:Reply)=>`${r.number}${r.white?'.':'…'}${r.san}`
const judgement=(j:Judged,turn:Color)=>j.best===j.san?`la prima scelta del motore (${objectiveScore(j,turn)})`:`${j.label}, ${objectiveScore(j,turn)} · migliore ${j.best} ${objectiveScore(j.bestScore,turn)}`

/** Segui la partita: the player guesses every move of one side of a book game; the other side's moves are played for them. */
export default function LessonWalk({walk,start,onExit}:{walk:WalkItem;start:Step;onExit:()=>void}){
  const [current,setCurrent]=useState<Step>(start),[answer,setAnswer]=useState<Answer|null>(null),[shown,setShown]=useState(0)
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  const orientation=useBoardOrientation(walk.side)
  const side=walk.side==='w'?'il Bianco':'il Nero'
  async function call<T>(work:()=>Promise<T>,then:(v:T)=>void){
    setBusy(true);setError('')
    try{then(await work())}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  const play=(uci:string)=>{if(!answer)void call(()=>api<Answer>(`/lesson-walks/${walk.id}/answer`,{run:current.run.id,ply:current.ply,move:uci,hints:shown}),setAnswer)}
  const go=(ply:number)=>void call(()=>api<Step>(`/lesson-walks/${walk.id}/runs/${current.run.id}?ply=${ply}`),s=>{setCurrent(s);setAnswer(null);setShown(0)})
  const restart=()=>void call(()=>api<Step>(`/lesson-walks/${walk.id}/start`,{}),s=>{setCurrent(s);setAnswer(null);setShown(0)})
  const run=answer?.run??current.run
  const finished=answer?.finished
  const arrows:AnalysisArrow[]=answer?[...(answer.move!==answer.played?[{move:answer.uci,source:'played' as const,rank:0}]:[]),{move:answer.playedUci,source:'solution',rank:0},
    ...(answer.engine.lines[0]?.pv[0]?[{move:answer.engine.lines[0].pv[0],source:'stockfish' as const,rank:0}]:[])]:[]
  return <div className="training-layout layout-prevention lessons lesson-walk">
    <section className="board-column">
      <div className="player-row"><div className="player-info"><strong>{walk.title}</strong><small>{walk.event} · {walk.opening} · giochi con {side}</small></div>
        <span className="walk-score" aria-label="Punteggio">{run.found} su {run.answered} trovate</span></div>
      <Board fen={answer?.fenAfter??current.fen} orientation={orientation} interactive={!answer&&!busy} legalMoves={answer?[]:current.legalMoves} onMove={uci=>play(uci)}
        lastMove={answer?answer.lastMove:current.lastMove??undefined} analysisArrows={arrows}/>
    </section>
    <aside className="coach-column">
      <section className="panel lesson-question" aria-label="Segui la partita">
        <span className="eyebrow">PARTITA {walk.game} · MOSSA {current.number} DI {current.total}{current.lesson?' · LEZIONE':''}</span>
        <p className="lesson-line">{current.line||'Posizione iniziale'}</p>
        {current.replies.map(r=><div key={r.ply} className="walk-reply"><b>{r.white?'Il Bianco':'Il Nero'} gioca {moveName(r)}.</b> {r.note}
          <small> Stockfish: {judgement(r.engine,r.white?'w':'b')}.</small></div>)}
        <h3>{current.question}</h3>
        {shown>0&&<ol className="lesson-hints" aria-label="Indizi">{current.hints.slice(0,shown).map(h=><li key={h}>{h}</li>)}</ol>}
        {!answer&&shown<current.hints.length&&<button disabled={busy} onClick={()=>setShown(shown+1)}>Indizio {shown+1} di {current.hints.length}</button>}
        {!answer&&<p className="footnote">Gioca la mossa che sceglieresti per {side}.</p>}
        {answer&&<div role="status" className={answer.success?'notice':'alert'}><span><b>{answer.success?'✓':'✗'} {answer.move}: {answer.verdictLabel}.</b> {answer.note??''}</span></div>}
        <div className="lesson-actions">
        {answer&&!answer.counted&&<p className="footnote">Secondo tentativo: non cambia il punteggio.</p>}
        {answer&&!finished&&answer.nextPly!==null&&<button className="primary" disabled={busy} onClick={()=>go(answer.nextPly!)}>Continua →</button>}
        {finished&&<button className="primary" disabled={busy} onClick={restart}>Ricomincia la partita</button>}
        {answer&&<button disabled={busy} onClick={()=>{setAnswer(null);setShown(0)}}>Riprova questa mossa</button>}
        <button disabled={busy} title="Il percorso resta salvato: lo riprendi dall’elenco" onClick={onExit}>{answer?'Tutte le lezioni':'Interrompi'}</button>
        </div>
        {error&&<p role="alert">{error}</p>}
      </section>
      {answer&&<>
        <section className="panel lesson-book" aria-label="Idea del libro">
          <span className="eyebrow">L’IDEA · PARTITA {walk.game}, P. {answer.page}</span>
          <h3>Nella partita: {answer.played}</h3>
          <p>{answer.explanation}</p>
          {answer.bookIdea&&<p className="footnote">{answer.bookIdea}</p>}
        </section>
        <section className="panel lesson-engine" aria-label="Valutazione di Stockfish">
          <span className="eyebrow">STOCKFISH · PROFONDITÀ {answer.engine.depth}</span>
          <p>La tua mossa {answer.move}: <b>{objectiveScore(answer.engine.move,current.turn)}</b> · {answer.engine.move.label}{answer.engine.move.live?' (analisi rapida)':''}.
            {answer.move!==answer.played&&<> Mossa della partita {answer.played}: <b>{objectiveScore(answer.engine.played,current.turn)}</b> · {answer.engine.played.label}.</>} Migliore per il motore: <b>{answer.engine.lines[0].san} {objectiveScore(answer.engine.lines[0],current.turn)}</b>.</p>
          {answer.engineNote&&<p className="lesson-disagree">{answer.engineNote}</p>}
          {answer.moves.length>1&&<table className="lesson-moves"><thead><tr><th>Mossa</th><th>Giudizio</th><th>Motore</th></tr></thead>
            <tbody>{answer.moves.map(m=><tr key={m.san} className={m.san===answer.move?'chosen':''}><td>{m.san}</td><td><span className={`kind-tag lesson-verdict-${m.verdict}`}>{VERDICT[m.verdict]}</span> {m.note}</td><td>{objectiveScore(m,current.turn)}</td></tr>)}</tbody></table>}
          <p className="footnote">{SCORE_NOTE}</p>
        </section>
        {finished&&<section className="panel walk-end" aria-label="Fine della partita">
          <span className="eyebrow">FINE · {answer.result}</span>
          {answer.tail.map(r=><p key={r.ply}><b>{moveName(r)}</b> {r.note}</p>)}
          {answer.ending&&<p>{answer.ending}</p>}
          <h3>Hai trovato {run.found} mosse su {run.total}{run.fromNumber>1?` (dalla mossa ${run.fromNumber})`:''} al primo tentativo, {run.clean} senza indizi.</h3>
        </section>}
      </>}
      <p className="footnote lesson-citation">{answer?.citation??`Partita ${walk.game} del libro: ${walk.title}, ${walk.event}.`}</p>
    </aside>
  </div>
}

