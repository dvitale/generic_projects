import {useEffect,useRef,useState} from 'react'
import {api} from './api'
import type {Game} from './types'

type Point={title:string;explanation:string;plies:number[]}
type Focus=Point&{kind:'tactical'|'positional'|'mixed'|'assessment';practice:string}
type Review={createdAt:string;cached:boolean;provider:string;model:string;result:string;scope:string;completeCoverage:boolean;
  references:{ply:number;label:string}[];commentary:{summary:string;course:string;strengths:Point[];focus:Focus[];uncertainty:string}}
const labels={tactical:'Tattica',positional:'Posizione e strategia',mixed:'Tattica e posizione',assessment:'Valutazione della posizione'}
export default function FinalReview({game,disabled,onPosition}:{game:Game;disabled:boolean;onPosition:(ply:number)=>void}){
  const [review,setReview]=useState<Review|null>(null),[configured,setConfigured]=useState(false)
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const epoch=useRef(0)
  useEffect(()=>{
    const current=++epoch.current
    setReview(null);setError('');setLoading(true);setBusy(false);setConfigured(false)
    Promise.all([api<{configured:boolean}>('/tutor/status'),api<Review|null>(`/games/${game.id}/final-review`)]).then(([status,saved])=>{
      if(current===epoch.current){setConfigured(status.configured);setReview(saved)}
    }).catch(e=>{if(current===epoch.current)setError(e.message)}).finally(()=>{if(current===epoch.current)setLoading(false)})
    return()=>{epoch.current++}
  },[game.id,game.version,game.revision,game.analysis?.createdAt])
  async function ask(){
    const current=epoch.current
    setBusy(true);setError('')
    try{const response=await api<Review>(`/games/${game.id}/final-review`,{version:game.version,revision:game.revision});if(current===epoch.current)setReview(response)}
    catch(e){if(current===epoch.current)setError(e instanceof Error?e.message:'Commento non disponibile: riprova.')}
    finally{if(current===epoch.current)setBusy(false)}
  }
  function links(point:Point){return <div className="row">{point.plies.map(ply=><button className="quiet" key={ply} onClick={()=>onPosition(ply)}>Rivedi {review?.references.find(r=>r.ply===ply)?.label??'la posizione'} ↗</button>)}</div>}
  return <section className="panel final-review" aria-label="Commento finale della partita">
    <span className="eyebrow">IL BILANCIO DELLA PARTITA</span><h2>Andamento e prossimi passi</h2>
    <p className="muted">Una lettura d’insieme: come è cambiata la partita, cosa ha funzionato e quali decisioni approfondire.</p>
    {!game.result&&<p className="footnote">{game.drill?'Bilancio della sessione di drill.':'La partita non ha un risultato conclusivo: il commento sarà provvisorio.'}</p>}
    {!review&&<button className="primary full" disabled={loading||busy||disabled||!game.analysis||!configured} onClick={()=>void ask()}>{busy?'Preparazione del commento…':'Genera commento finale'}</button>}
    {!game.analysis&&<p className="footnote">Completa prima l’analisi Stockfish della partita.</p>}
    {loading&&<p role="status">Caricamento del commento salvato…</p>}
    {busy&&<p role="status">Il tutor sta esaminando l’andamento e le decisioni di entrambi i colori…</p>}
    {!loading&&!configured&&!review&&!error&&<p className="footnote">DeepSeek non è configurato sul server.</p>}
    <p className="footnote">Solo al clic vengono inviati a DeepSeek l’andamento delle valutazioni e fino a sei posizioni con le varianti analizzate, senza nomi dei giocatori. Il commento viene salvato e riutilizzato finché la partita e l’analisi restano le stesse.</p>
    {error&&<p className="alert" role="alert">{error}</p>}
    {review&&<div className="tutor-response">
      {!review.completeCoverage&&<p className="notice">La copertura dell’analisi è parziale: alcuni tratti della partita non sono valutati.</p>}
      <p className="tutor-summary">{review.commentary.summary}</p>
      <article className="tutor-observation"><h3>Come si è sviluppata</h3><p className="final-review-text">{review.commentary.course}</p></article>
      {!!review.commentary.strengths.length&&<><h3>Scelte da conservare</h3>{review.commentary.strengths.map((point,i)=><article className="tutor-step" key={i}><h4>{point.title}</h4><p>{point.explanation}</p>{links(point)}</article>)}</>}
      <h3>Punti da approfondire</h3>{review.commentary.focus.map((point,i)=><article className="tutor-step" key={i}><h4>{i+1}. {point.title}</h4><span className="insight-badge">{labels[point.kind]}</span><p>{point.explanation}</p><p className="hint"><strong>Come allenarlo. </strong>{point.practice}</p>{links(point)}</article>)}
      <details><summary>Limiti del commento</summary><p>{review.commentary.uncertainty}</p></details>
      <p className="footnote">Valutazioni dalla tua prospettiva; interpretazione del tutor, non stima Elo né diagnosi delle tue capacità. {review.provider} · {review.model} · {new Date(review.createdAt).toLocaleString('it-IT')}{review.cached?' · commento salvato':''}</p>
    </div>}
  </section>
}
