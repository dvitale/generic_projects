import {useEffect,useState} from 'react'
import Board,{type AnalysisArrow} from './Board'
import InfoNote from './InfoNote'
import LessonWalk,{type WalkItem} from './LessonWalk'
import {api} from './api'
import {SCORE_NOTE,objectiveScore} from './evalText'
import {useBoardOrientation} from './boardFlip'
import type {Color} from './types'

type WalkStart=Parameters<typeof LessonWalk>[0]['start']
type Status='new'|'due'|'waiting'
type Verdict='game'|'good'|'partial'|'weak'|'other'
interface Progress {status:Status;stage:number;dueAt:string|null;attempts:number;successes:number;lastSuccess:boolean|null}
interface Item extends Progress {id:string;title:string;theme:string;page:number;game:number}
interface Overview {path:{title:string;summary:string};source:{title:string;author:string;note:string};lessons:Item[];next:string|null;due:number;new:number;nextDue:string|null;intervalHours:number[]}
interface Game {white:string;black:string;event:string;opening:string;number:number;page:number;citation:string}
interface Lesson extends Progress {id:string;title:string;theme:string;question:string;hints:string[];fen:string;turn:Color;lastMove:string|null;line:string;legalMoves:string[];game:Game;counts:boolean}
interface Score {cp:number;mate:number|null}
interface Line extends Score {san:string;pv:string[]}
interface Considered extends Score {san:string;uci:string;verdict:Verdict;note:string}
interface Answer extends Progress {fenAfter:string;playedUci:string;walk:{id:string;ply:number;number:number}|null;success:boolean;verdict:Verdict;verdictLabel:string;move:string;uci:string;note:string|null;played:string;explanation:string;bookIdea:string;engineNote:string|null;counted:boolean;hints:number;moves:Considered[];engine:{depth:number;lines:Line[];move:Score&{san:string;loss:number;label:string;live:boolean}}}

const VERDICT:Record<Verdict,string>={game:'Partita',good:'Valida',partial:'Sensata',weak:'Debole',other:'Fuori lista'}
const when=(iso:string)=>new Date(iso).toLocaleString('it-IT',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})
const statusText=(i:Progress)=>i.status==='new'?'Nuova':i.status==='due'?'Da ripassare':`${i.stage?`Ripasso ${i.stage}`:'Da rifare'} · ${when(i.dueAt!)}`

/** Ragionamento mossa per mossa: guided lessons from a book, apart from the exercises built from your games. */
export default function Lessons(){
  const [overview,setOverview]=useState<Overview|null>(null),[lesson,setLesson]=useState<Lesson|null>(null)
  const [answer,setAnswer]=useState<Answer|null>(null),[shown,setShown]=useState(0)
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  const [walks,setWalks]=useState<WalkItem[]>([]),[walk,setWalk]=useState<{item:WalkItem;start:Parameters<typeof LessonWalk>[0]['start']}|null>(null)
  const orientation=useBoardOrientation(lesson?.turn??'w')
  const load=()=>Promise.all([api<Overview>('/lessons').then(setOverview),api<{walks:WalkItem[]}>('/lesson-walks').then(r=>setWalks(r.walks))]).catch(e=>setError(e.message))
  async function follow(item:WalkItem,resume:boolean,ply?:number){
    setBusy(true);setError('')
    try{setWalk({item,start:await (resume&&item.current?api<WalkStart>(`/lesson-walks/${item.id}/runs/${item.current.id}`):api<WalkStart>(`/lesson-walks/${item.id}/start`,ply===undefined?{}:{ply}))})
      setLesson(null);setAnswer(null)}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  useEffect(()=>{void load()},[])
  async function open(id:string){
    setBusy(true);setError('')
    try{setLesson(await api<Lesson>(`/lessons/${id}`));setAnswer(null);setShown(0)}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function play(uci:string){
    if(!lesson||answer)return
    setBusy(true);setError('')
    try{setAnswer(await api<Answer>(`/lessons/${lesson.id}/answer`,{move:uci,hints:shown}));void load()}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  const footer=overview&&<InfoNote summary="Fonte e metodo"><p>{overview.source.note}</p>
    <p>Le mosse accettate sono scelte per l’obiettivo della lezione: la mossa della partita e le alternative coerenti con la stessa idea. La valutazione di Stockfish (profondità fissa, punteggio oggettivo: positivo se è avanti il Bianco) è mostrata a parte e non decide l’esito: libro e motore non sempre coincidono.</p>
    <p>Ripasso: una risposta giusta senza indizi sposta la lezione al passo successivo ({overview.intervalHours.slice(0,4).map(h=>h<24?`${h} ore`:`${h/24} giorni`).join(', ')}…); un errore o un indizio la ripropone dopo 4 ore. Le risposte date prima della scadenza sono solo pratica.</p></InfoNote>
  if(walk)return <LessonWalk walk={walk.item} start={walk.start} onExit={()=>{setWalk(null);void load()}}/>
  if(!lesson)return <section className="panel lessons-intro">
    <span className="eyebrow">PERCORSO GUIDATO · DAL LIBRO</span>
    <h2>{overview?.path.title??'Ragionamento mossa per mossa'}</h2>
    {overview&&<><p>{overview.path.summary}</p>
      <p>{overview.due} da ripassare · {overview.new} nuove{overview.nextDue&&!overview.next?` · prossimo ripasso ${when(overview.nextDue)}`:''}</p></>}
    {error&&<p role="alert">{error}</p>}
    {overview?.next&&<button className="primary" disabled={busy} onClick={()=>void open(overview.next!)}>{overview.due?'Inizia il ripasso →':'Inizia la prossima →'}</button>}
    {overview&&<ol className="exercise-list lesson-list" aria-label="Lezioni">{overview.lessons.map(item=><li key={item.id}><button disabled={busy} onClick={()=>void open(item.id)}>
      <strong><span className={`kind-tag lesson-${item.status}`}>{statusText(item)}</span> {item.theme}</strong><small>{item.title} · partita {item.game}, p. {item.page}</small></button></li>)}</ol>}
    {walks.length>0&&<div className="walk-list"><h3>Segui la partita</h3>{walks.map(w=><div key={w.id} className="walk-card">
      <div><strong>Partita {w.game}: {w.title}</strong><small>{w.event} · {w.opening} · {w.result} · giochi con {w.side==='w'?'il Bianco':'il Nero'}, {w.total} mosse</small>
        <p>{w.summary}</p>
        {(w.current||w.best)&&<small>{w.current?`In corso${w.current.fromNumber>1?` dalla mossa ${w.current.fromNumber}`:''}: ${w.current.answered} di ${w.current.total} mosse, ${w.current.found} trovate.`:''}{w.best?` Migliore: ${w.best.found} su ${w.total}.`:''}</small>}</div>
      <div className="walk-actions">{w.current&&<button className="primary" disabled={busy} onClick={()=>void follow(w,true)}>Riprendi →</button>}
        <button className={w.current?undefined:'primary'} disabled={busy} onClick={()=>void follow(w,false)}>{w.current||w.last?'Ricomincia':'Segui la partita →'}</button></div></div>)}</div>}
    {footer}
  </section>
  const best=answer?.engine.lines[0]
  // After the answer the game move is played on the board; arrows show your move and Stockfish's when they differ from it.
  const arrows:AnalysisArrow[]=answer?[...(answer.uci!==answer.playedUci?[{move:answer.uci,source:'played' as const,rank:0}]:[]),
    ...(best?.pv[0]&&best.pv[0]!==answer.playedUci?[{move:best.pv[0],source:'stockfish' as const,rank:0}]:[])]:[]
  const walkItem=answer?.walk?walks.find(w=>w.id===answer.walk!.id):undefined
  return <div className="training-layout layout-prevention lessons">
    <section className="board-column">
      <div className="player-row"><div className="player-info"><strong>{lesson.game.white}–{lesson.game.black}</strong><small>{lesson.game.event} · {lesson.game.opening}</small></div></div>
      <Board fen={answer?.fenAfter??lesson.fen} orientation={orientation} interactive={!answer&&!busy} legalMoves={answer?[]:lesson.legalMoves} onMove={uci=>play(uci)} lastMove={answer?answer.playedUci:lesson.lastMove??undefined} analysisArrows={arrows}/>
    </section>
    <aside className="coach-column">
      <section className="panel lesson-question" aria-label="Lezione">
        <span className="eyebrow">{lesson.theme.toUpperCase()} · {lesson.turn==='w'?'MUOVE IL BIANCO':'MUOVE IL NERO'}</span>
        <p className="lesson-line">{lesson.line}</p>
        <h3>{lesson.question}</h3>
        {!lesson.counts&&!answer&&<p className="footnote">Il ripasso non è ancora in scadenza ({when(lesson.dueAt!)}): questa risposta è solo pratica.</p>}
        {shown>0&&<ol className="lesson-hints" aria-label="Indizi">{lesson.hints.slice(0,shown).map(h=><li key={h}>{h}</li>)}</ol>}
        {!answer&&shown<lesson.hints.length&&<button disabled={busy} onClick={()=>setShown(shown+1)}>Indizio {shown+1} di {lesson.hints.length}</button>}
        {!answer&&<p className="footnote">Gioca la tua mossa sulla scacchiera.{shown>0?' Con un indizio la lezione torna presto in ripasso.':''}</p>}
        {answer&&<div role="status" className={answer.success?'notice':'alert'}><span><b>{answer.success?'✓':'✗'} {answer.move}: {answer.verdictLabel}.</b> {answer.note??''}</span></div>}
        {answer&&<div className="lesson-actions">
        <p className="footnote">{answer.counted?(answer.status==='waiting'?`Prossimo ripasso: ${when(answer.dueAt!)}.`:''):'Risposta di pratica: il ripasso non cambia.'}</p>
        {walkItem&&<button className="primary" disabled={busy} title={`Segui la partita: dalla mossa ${answer.walk!.number} ${walkItem.side==="w"?"del Bianco":"del Nero"} alla fine`} onClick={()=>void follow(walkItem,false,answer.walk!.ply)}>Continua la partita →</button>}
        <button className={walkItem?undefined:'primary'} disabled={busy||!overview?.next} onClick={()=>overview?.next&&void open(overview.next)}>{overview?.next?'Prossima lezione →':'Nessuna lezione in scadenza'}</button>
        <button disabled={busy} onClick={()=>{setAnswer(null);setShown(0);void open(lesson.id)}}>Riprova</button>
        <button disabled={busy} onClick={()=>{setLesson(null);setAnswer(null)}}>Tutte le lezioni</button>
        </div>}
        {error&&<p role="alert">{error}</p>}
      </section>
      {answer&&<>
        <section className="panel lesson-book" aria-label="Idea del libro">
          <span className="eyebrow">L’IDEA · PARTITA {lesson.game.number}, P. {lesson.game.page}</span>
          <h3>Nella partita: {answer.played}</h3>
          <p>{answer.explanation}</p>
          <p className="footnote">{answer.bookIdea}</p>
        </section>
        <section className="panel lesson-engine" aria-label="Valutazione di Stockfish">
          <span className="eyebrow">STOCKFISH · PROFONDITÀ {answer.engine.depth}</span>
          <p>La tua mossa {answer.engine.move.san}: <b>{objectiveScore(answer.engine.move,lesson.turn)}</b> · {answer.engine.move.label}{answer.engine.move.live?' (analisi rapida)':''}. Migliore per il motore: <b>{best?.san} {best&&objectiveScore(best,lesson.turn)}</b>.</p>
          {answer.engineNote&&<p className="lesson-disagree">{answer.engineNote}</p>}
          <table className="lesson-moves"><thead><tr><th>Mossa</th><th>Lezione</th><th>Motore</th></tr></thead>
            <tbody>{answer.moves.map(m=><tr key={m.san} className={m.san===answer.move?'chosen':''}><td>{m.san}</td><td><span className={`kind-tag lesson-verdict-${m.verdict}`}>{VERDICT[m.verdict]}</span> {m.note}</td><td>{objectiveScore(m,lesson.turn)}</td></tr>)}</tbody></table>
          <p className="footnote">{SCORE_NOTE} Prime linee del motore: {answer.engine.lines.map(l=>`${l.san} ${objectiveScore(l,lesson.turn)}`).join(' · ')}.</p>
        </section>
      </>}
      <p className="footnote lesson-citation">{lesson.game.citation}</p>
    </aside>
  </div>
}
