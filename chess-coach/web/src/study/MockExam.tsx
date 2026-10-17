import {useEffect,useRef,useState} from 'react'
import {api} from '../api'
import InfoNote from '../InfoNote'
import BarList from '../BarList'
import StudyBoard from './StudyBoard'
import type {AnalysisArrow} from '../Board'
import type {Exam,ExamHistory} from './types'

const date=(iso:string)=>new Date(iso).toLocaleDateString('it-IT',{day:'numeric',month:'short'})
const clock=(seconds:number)=>`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`

/** Past mock exams, also shown in Progressi as a measure separate from daily practice. */
export function ExamHistoryList({data}:{data:ExamHistory|null}){
  if(!data?.history.length)return <p className="empty-text">Nessun esame di prova completato.</p>
  return <ol className="exam-history">{data.history.map(h=><li key={h.id}><span>{date(h.createdAt)}</span><div className="bar-track" aria-hidden="true"><span style={{width:`${Math.max(3,100*h.score/h.size)}%`}}/></div><strong>{h.score} / {h.size}</strong></li>)}</ol>
}

export function ExamProgress(){
  const [data,setData]=useState<ExamHistory|null>(null)
  useEffect(()=>{api<ExamHistory>('/study/exams').then(setData).catch(()=>setData(null))},[])
  return <section className="panel"><span className="eyebrow">ESAMI DI PROVA</span><h2>Posizioni risolte senza aiuti</h2><ExamHistoryList data={data}/>
    <InfoNote summary="Perché è una misura separata">Gli esami mescolano temi diversi, hanno un tempo limite e non danno indizi né riscontri durante la prova. Non cambiano i ripassi dei puzzle: misurano quanto riesci a trasferire, mentre i successi della pratica quotidiana misurano anche la memoria della singola posizione.</InfoNote></section>
}

export default function MockExam({onPuzzle,onReview}:{onPuzzle:(id:string)=>void;onReview:(gameId:string,ply:number)=>void}){
  const [history,setHistory]=useState<ExamHistory|null>(null)
  const [exam,setExam]=useState<Exam|null>(null)
  const [current,setCurrent]=useState(0)
  const [size,setSize]=useState(8)
  const [minutes,setMinutes]=useState(12)
  const [now,setNow]=useState(()=>Date.now())
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [shown,setShown]=useState<number|null>(null)
  const finishing=useRef(false)
  async function load(){
    try{const data=await api<ExamHistory>('/study/exams');setHistory(data);if(data.active){setExam(data.active);setCurrent(Math.max(0,data.active.items.findIndex(i=>!i.answered)))}}
    catch(e){setError(e instanceof Error?e.message:'Esami non disponibili')}
  }
  useEffect(()=>{void load()},[])
  const running=!!exam&&!exam.finishedAt
  const remaining=exam?Math.max(0,Math.round((new Date(exam.deadline).getTime()-now)/1000)):0
  useEffect(()=>{if(!running)return;const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer)},[running])
  useEffect(()=>{if(running&&remaining===0)void finish()},[running,remaining])
  async function start(){
    setBusy(true);setError('')
    try{const next=await api<Exam>('/study/exams',{size,minutes});setExam(next);setCurrent(0);setShown(null);setNow(Date.now())}
    catch(e){setError(e instanceof Error?e.message:'Esame non avviato')}finally{setBusy(false)}
  }
  async function finish(){
    if(!exam||finishing.current)return
    finishing.current=true;setBusy(true)
    try{setExam(await api<Exam>(`/study/exams/${exam.id}/finish`,{}));setShown(null);setHistory(await api<ExamHistory>('/study/exams'))}
    catch(e){setError(e instanceof Error?e.message:'Consegna non riuscita')}finally{finishing.current=false;setBusy(false)}
  }
  function nextOpen(items:Exam['items'],from:number){
    for(let step=1;step<=items.length;step++){const i=(from+step)%items.length;if(!items[i].answered)return i}
    return -1
  }
  async function answer(move:string){
    if(!exam||busy)return
    setBusy(true);setError('')
    try{
      await api(`/study/exams/${exam.id}/answers`,{item:current,move})
      const items=exam.items.map(i=>i.index===current?{...i,answered:true}:i)
      const updated={...exam,items,answered:exam.answered+1}
      setExam(updated)
      const next=nextOpen(items,current)
      if(next<0){setBusy(false);await finish();return}
      setCurrent(next)
    }catch(e){setError(e instanceof Error?e.message:'Risposta non registrata');void load()}
    finally{setBusy(false)}
  }
  const item=exam?.items[running?current:shown??0]
  const arrows:AnalysisArrow[]=[]
  if(exam?.finishedAt&&item&&shown!==null){
    if(item.best?.pv[0])arrows.push({move:item.best.pv[0],source:'stockfish',rank:1})
    if(item.move&&item.move!==item.best?.pv[0])arrows.push({move:item.move,source:'played',rank:1})
  }
  return <>
    {error&&<div className="alert" role="alert">{error}<button onClick={()=>{setError('');void load()}}>Riprova</button></div>}
    {!exam?<div className="progress-layout">
      <section className="panel study-empty"><span className="eyebrow">ESAME DI PROVA</span><h2>Verifica senza aiuti</h2>
        <p>Posizioni dai tuoi puzzle, con temi mescolati e un tempo limite. Niente indizi e nessun riscontro fino alla consegna: misura cosa sai riconoscere da solo.</p>
        <div className="field-label">Posizioni</div><div className="chip-row" role="group" aria-label="Numero di posizioni">{[6,8,10].map(n=><button key={n} className="chip" aria-pressed={size===n} onClick={()=>setSize(n)}>{n}</button>)}</div>
        <div className="field-label">Tempo</div><div className="chip-row" role="group" aria-label="Tempo a disposizione">{[8,12,20].map(n=><button key={n} className="chip" aria-pressed={minutes===n} onClick={()=>setMinutes(n)}>{n} min</button>)}</div>
        <button className="primary full big" disabled={busy} onClick={()=>void start()}>Inizia l’esame →</button>
        {history?.nextRecommended&&<p className="footnote">{new Date(history.nextRecommended).getTime()>Date.now()?`Prossimo esame consigliato dal ${date(history.nextRecommended)}: ogni ${history.cadenceDays} giorni bastano a misurare i progressi.`:'È passato abbastanza tempo dall’ultimo esame: buon momento per misurarti.'}</p>}
      </section>
      <section className="panel"><span className="eyebrow">STORICO</span><h2>Esami completati</h2><ExamHistoryList data={history}/></section>
    </div>:<div className="training-layout layout-study">
      {item&&<StudyBoard fen={item.fen} side={item.turn} arrows={arrows} legalMoves={running&&!item.answered?item.legalMoves:[]} onMove={running?move=>void answer(move):undefined}
        caption={running?(item.answered?'Risposta registrata.':'Muovi: la risposta viene registrata senza riscontro.'):'Freccia blu: Stockfish. Freccia bianca: la tua mossa.'}/>}
      <aside className="coach-column">
        {running?<section className="panel exam-status" aria-label="Esame in corso">
          <div className="exam-clock" role="timer" aria-live="off"><span className="eyebrow">TEMPO</span><strong className={remaining<60?'urgent':''}>{clock(remaining)}</strong></div>
          <p>Posizione <strong>{current+1}</strong> di {exam.size} · {exam.answered} risposte registrate</p>
          <p className="muted">Muove il {item?.turn==='w'?'Bianco':'Nero'}. Trova una buona mossa: sono accettate anche alternative che perdono meno di 0,70 rispetto a Stockfish.</p>
          <nav className="quiz-steps" aria-label="Posizioni">{exam.items.map(i=><button key={i.index} aria-current={i.index===current?'step':undefined} className={i.answered?'done':''} disabled={i.answered} onClick={()=>setCurrent(i.index)}>{i.index+1}</button>)}</nav>
          <div className="row"><button disabled={busy||[current,-1].includes(nextOpen(exam.items,current))} onClick={()=>{const next=nextOpen(exam.items,current);if(next>=0)setCurrent(next)}}>Salta per ora</button><button className="primary" disabled={busy} onClick={()=>{if(window.confirm('Consegnare l’esame? Le posizioni senza risposta contano come non risolte.'))void finish()}}>Consegna</button></div>
        </section>:<>
          <section className="panel" role="status"><span className="eyebrow">RISULTATO</span><h2>{exam.score} posizioni risolte su {exam.size}</h2><p className="muted">Esame del {date(exam.createdAt)}. Le posizioni non risolte restano nei puzzle con i loro ripassi: l’esame non li modifica.</p>
            {exam.themes&&<BarList unit="risolte" items={exam.themes.map(t=>({key:t.theme,label:`${t.theme} (${t.solved}/${t.total})`,value:t.solved}))}/>}
            <button className="primary" onClick={()=>{setExam(null);setShown(null)}}>Chiudi risultati</button></section>
          <section className="panel"><h3>Le posizioni</h3><ol className="exam-results">{exam.items.map(i=><li key={i.index}><button className={'exam-result '+(i.success?'correct':'wrong')+(shown===i.index?' chosen':'')} onClick={()=>setShown(i.index)}>
            <span>{i.success?'✓':'✗'} {i.index+1}. {i.theme}</span><small>{i.san?`Tua mossa ${i.san}`:'Senza risposta'} · Stockfish {i.best?.san[0]??'—'}</small></button>
            {shown===i.index&&<div className="row">{i.exerciseId&&<button onClick={()=>onPuzzle(i.exerciseId!)}>Apri come puzzle</button>}{i.gameId&&i.ply!==undefined&&<button className="quiet" onClick={()=>onReview(i.gameId!,i.ply!)}>Rivedi nella partita</button>}</div>}
            {shown===i.index&&i.best&&<p className="variation">{i.best.san.join(' ')}</p>}</li>)}</ol></section>
        </>}
      </aside>
    </div>}
  </>
}
