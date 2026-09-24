import { useEffect, useState } from 'react'
import { api } from './api'
import type { Game } from './types'

interface Review {
  provider:string; model:string; createdAt:string; reflection:string; cached:boolean;
  evidence:{ply:number;playedSan:string;bestSan:string[];theme:string}[];
  coaching:{summary:string;observations:{ply:number;explanation:string;hypothesis:string;question:string}[];
    plan:{title:string;minutes:number;description:string;exerciseId:string|null;drillId:string|null}[]};
}
export default function TutorPanel({game,disabled,onPosition,onPuzzle,onDrill}:{game:Game;disabled:boolean;onPosition:(ply:number)=>void;onPuzzle:(id:string)=>void;onDrill:(id:string)=>void}){
  const [configured,setConfigured]=useState(false)
  const [reflection,setReflection]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [review,setReview]=useState<Review|null>(null)
  useEffect(()=>{
    let cancelled=false
    Promise.all([api<{configured:boolean}>('/tutor/status'),api<Review|null>(`/games/${game.id}/tutor`)]).then(([status,saved])=>{
      if(!cancelled){setConfigured(status.configured);setReview(saved);if(saved)setReflection(saved.reflection)}
    }).catch(e=>{if(!cancelled)setError(e.message)})
    return()=>{cancelled=true}
  },[game.id])
  async function ask(){
    setBusy(true);setError('')
    try{setReview(await api<Review>(`/games/${game.id}/tutor`,{version:game.version,reflection}))}
    catch(e){setError(e instanceof Error?e.message:'Il tutor non ha risposto.')}
    finally{setBusy(false)}
  }
  return <section className="panel tutor-panel">
    <span className="eyebrow">TUTOR DEEPSEEK</span><h2>Ragioniamo sulle tue scelte</h2>
    <p className="muted">Stockfish verifica le varianti. Il tutor ti aiuta a interpretarle e a scegliere cosa allenare.</p>
    <label className="field-label">Che cosa avevi in mente? <small>Facoltativo: indica anche la mossa.</small>
      <textarea aria-label="Il tuo ragionamento" maxLength={2000} rows={3} value={reflection} disabled={busy} onChange={e=>setReflection(e.target.value)} placeholder="Per esempio: volevo attaccare il re, ma non avevo previsto la risposta…"/>
    </label>
    <button className="primary full" disabled={busy||disabled||!configured} onClick={ask}>{busy?'Il tutor sta ragionando…':review?'Aggiorna il confronto':'Chiedi al tutor DeepSeek'}</button>
    {!game.analysis&&<p className="footnote">Avvia prima l'analisi Stockfish.</p>}
    {!configured&&!error&&<p className="footnote">DeepSeek non configurato sul server.</p>}
    <p className="footnote">Al clic invii a DeepSeek fino a tre posizioni analizzate, la tua riflessione e un riepilogo dei progressi. Le risposte sono salvate qui; richieste identiche riusano la risposta disponibile.</p>
    {error&&<p className="alert" role="alert">{error}</p>}
    {busy&&<p role="status">Preparazione della spiegazione e del piano…</p>}
    {review&&<div className="tutor-response">
      <p className="tutor-summary">{review.coaching.summary}</p>
      {review.coaching.observations.map((o,i)=>{
        const evidence=review.evidence.find(e=>e.ply===o.ply)
        return <article className="tutor-observation" key={i}><button className="quiet" onClick={()=>onPosition(o.ply)}>Rivedi la decisione {o.ply+1}{evidence?' · '+evidence.playedSan:''} ↗</button><p>{o.explanation}</p><p><strong>Ipotesi da verificare. </strong>{o.hypothesis}</p><p className="hint">{o.question}</p>{evidence&&<small>Variante Stockfish: {evidence.bestSan.join(' ')}</small>}</article>
      })}
      <h3>Il tuo prossimo allenamento</h3>
      {review.coaching.plan.map((step,i)=><article className="tutor-step" key={i}><h4>{step.title} · {step.minutes} min</h4><p>{step.description}</p><div className="row">{step.exerciseId&&<button onClick={()=>onPuzzle(step.exerciseId!)}>Apri il Puzzle</button>}{step.drillId&&<button onClick={()=>onDrill(step.drillId!)}>Avvia il Drill</button>}</div></article>)}
      <p className="footnote">Interpretazione del tutor, non diagnosi delle tue competenze. {review.model} · {new Date(review.createdAt).toLocaleString('it-IT')}{review.cached?' · risposta salvata':''}</p>
    </div>}
  </section>
}
