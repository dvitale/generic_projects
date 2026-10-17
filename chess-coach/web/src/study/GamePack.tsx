import {useEffect,useState} from 'react'
import {api} from '../api'
import InfoNote from '../InfoNote'
import StudyBoard from './StudyBoard'
import GamePicker from './GamePicker'
import type {AnalysisArrow} from '../Board'
import type {Saved} from '../GameArchive'
import type {Moment,Pack,Refutation,StudyPosition} from './types'
import {pawns} from './types'

export interface PackActions {onPuzzle:(id:string)=>void;onPrevention:(id:string)=>void;onDrill:(id:string)=>void;onPlayMistake:(m:Refutation)=>void;onReview:(gameId:string,ply:number)=>void;onQuiz:()=>void;onAsk:(p:StudyPosition)=>void}

function LessonForm({gameId,moment,onSaved}:{gameId:string;moment:Moment;onSaved:()=>void}){
  const [lesson,setLesson]=useState('')
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  async function save(){
    setBusy(true);setMessage('')
    try{
      await api('/study/cards',{fen:moment.fen,lesson,move:moment.played,bestMove:moment.best[0]??null,theme:moment.theme??'La mia lezione',gameId,ply:moment.ply})
      setLesson('');setMessage('Scheda creata: la trovi in Flashcard.');onSaved()
    }catch(e){setMessage(e instanceof Error?e.message:'Scheda non salvata')}finally{setBusy(false)}
  }
  return <form className="lesson-form" onSubmit={e=>{e.preventDefault();void save()}}>
    <label htmlFor="pack-lesson" className="field-label">La mia lezione</label>
    <textarea id="pack-lesson" rows={3} maxLength={600} value={lesson} onChange={e=>setLesson(e.target.value)} placeholder="Per esempio: prima di catturare conto chi difende la casa d’arrivo."/>
    <button className="primary" disabled={busy||lesson.trim().length<3}>Crea flashcard</button>
    {message&&<p role="status" className="footnote">{message}</p>}
  </form>
}

export default function GamePack({games,gameId,onGame,actions}:{games:Saved[];gameId:string|null;onGame:(id:string)=>void;actions:PackActions}){
  const [pack,setPack]=useState<Pack|null>(null)
  const [selected,setSelected]=useState(0)
  const [error,setError]=useState('')
  const [reload,setReload]=useState(0)
  useEffect(()=>setSelected(0),[gameId])
  useEffect(()=>{
    if(!gameId){setPack(null);return}
    let stale=false
    api<Pack>(`/study/games/${gameId}/pack`).then(p=>{if(!stale){setPack(p);setError('');setSelected(s=>Math.min(s,Math.max(0,p.moments.length-1)))}})
      .catch(e=>{if(!stale){setPack(null);setError(e instanceof Error?e.message:'Partita non disponibile')}})
    return()=>{stale=true}
  },[gameId,reload])
  const moment=pack?.moments[selected]
  const arrows:AnalysisArrow[]=[]
  if(moment){if(moment.best[0])arrows.push({move:moment.best[0],source:'stockfish',rank:1});arrows.push({move:moment.played,source:'played',rank:1})}
  return <>
    <section className="panel study-toolbar"><GamePicker games={games} value={gameId} onChange={onGame}/>
      {pack&&<div className="pack-summary"><span><strong>{pack.quality.errors}</strong> errori</span><span><strong>{pack.quality.inaccuracies}</strong> imprecisioni</span><span><strong>{pack.quality.sound} / {pack.quality.decisions}</strong> decisioni solide</span>
        <button className="primary" onClick={actions.onQuiz}>{pack.quiz?`Quiz della partita · ${pack.quiz.score}/${pack.quiz.total}`:'Quiz della partita'} →</button></div>}
    </section>
    {error&&<div className="alert" role="alert">{error}<button onClick={()=>setReload(n=>n+1)}>Riprova</button></div>}
    {!gameId&&<section className="panel study-empty"><span className="eyebrow">IMPARA DA UNA PARTITA</span><h2>Tutto ciò che nasce da una partita, in un posto solo</h2><p>Per ogni errore: puzzle, Blunder prevention, drill dalla posizione, partita contro Stockfish con la tua mossa, domanda al tutor e una flashcard con la tua lezione.</p></section>}
    {pack&&!pack.moments.length&&<section className="panel"><p>Nessun errore o imprecisione rilevante in questa partita. Non significa gioco perfetto: l’analisi ha un budget limitato.</p></section>}
    {pack&&moment&&<div className="training-layout layout-study">
      <StudyBoard fen={moment.fen} side={moment.turn} arrows={arrows} caption="Posizione prima della tua mossa. Freccia bianca: la mossa giocata. Freccia blu: Stockfish."/>
      <aside className="coach-column">
        <section className="panel"><span className="eyebrow">MOMENTI DA STUDIARE</span><div className="pack-moments">{pack.moments.map((m,i)=><button key={m.ply} className={`moment ${i===selected?'chosen':''}`} aria-pressed={i===selected} onClick={()=>setSelected(i)}>
          <span>{m.moveNumber}{m.turn==='w'?'.':'…'} {m.playedSan}</span><span className={m.loss>=180?'error-text':''}>{m.label}</span><small>{m.insight||m.theme}{m.cards?` · ${m.cards} ${m.cards===1?'scheda':'schede'}`:''}</small></button>)}</div></section>
        <section className="panel" aria-label="Momento selezionato"><h2>{moment.moveNumber}{moment.turn==='w'?'.':'…'} {moment.playedSan} <small className="muted">{moment.lossCp!=null?`perde ${pawns(moment.lossCp)}`:'confronto con matto'}</small></h2>
          <p>Stockfish preferisce <strong>{moment.bestSan[0]??'—'}</strong>.</p><p className="variation">{moment.line.join(' ')}</p>
          {moment.refutation&&moment.refutation.length>1&&<p className="muted">Dopo {moment.playedSan} la risposta forte è <strong>{moment.refutation[1]}</strong>.</p>}
          <div className="pack-actions">
            <button disabled={!moment.exerciseId} title={moment.exerciseId?undefined:'Puzzle creati solo per i tre errori più costosi'} onClick={()=>moment.exerciseId&&actions.onPuzzle(moment.exerciseId)}>Puzzle</button>
            <button disabled={!moment.preventionId} title={moment.preventionId?undefined:'Solo per i blunder che rendono la posizione difficile da difendere'} onClick={()=>moment.preventionId&&actions.onPrevention(moment.preventionId)}>Blunder prevention</button>
            <button disabled={!moment.exerciseId} onClick={()=>moment.exerciseId&&actions.onDrill('personal:'+moment.exerciseId)}>Drill da qui</button>
            <button className="play-refutation" onClick={()=>actions.onPlayMistake({fen:moment.fen,move:moment.played,san:moment.playedSan})}><span aria-hidden="true">⚔</span> Gioca {moment.playedSan} contro Stockfish</button>
            <button onClick={()=>actions.onAsk({fen:moment.fen,title:`${pack.title} · ${moment.moveNumber}${moment.turn==='w'?'.':'…'}`,gameId:pack.gameId,ply:moment.ply,move:moment.played})}>Chiedi al tutor</button>
            <button className="quiet" onClick={()=>actions.onReview(pack.gameId,moment.ply)}>Rivedi nella partita</button>
          </div>
          <LessonForm key={moment.ply} gameId={pack.gameId} moment={moment} onSaved={()=>setReload(n=>n+1)}/>
        </section>
        <InfoNote summary="Da dove vengono le attività">Puzzle e Blunder prevention nascono automaticamente dall’analisi: i puzzle per i tre errori più costosi, Blunder prevention per le mosse che rendono la posizione difficile da difendere. Gli altri strumenti funzionano su ogni momento.</InfoNote>
      </aside>
    </div>}
  </>
}
