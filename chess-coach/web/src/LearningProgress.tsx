import InfoNote from './InfoNote'
import DiagnosisProgress from './DiagnosisProgress'
import {useEffect,useState} from 'react'
import {api} from './api'
import {QualityNumbers,qualityMethod,type Quality} from './DecisionQuality'
type Window=Quality&{games:number}
type Progress={groups:{kind:string;recent:Window;previous:Window}[];judgments:{total:number;fresh:number;matched:number;fearedLost:number;falseAlarms:number}}
function Trend({recent,previous}:{recent:Window;previous:Window}){
  const now=100*recent.errors/recent.decisions
  if(!previous.decisions)return <p className="footnote">Errori rilevanti ogni 100 decisioni: {now.toFixed(1)}. Non ci sono ancora partite precedenti per il confronto.</p>
  const before=100*previous.errors/previous.decisions,delta=now-before
  return <p className="trend-line"><span className={`trend-badge ${delta<0?'trend-better':delta>0?'trend-worse':''}`} title="Variazione rispetto al blocco precedente">{delta<0?'▼':delta>0?'▲':'='} {Math.abs(delta).toFixed(1)}</span><span>Errori rilevanti ogni 100 decisioni: <b>{now.toFixed(1)}</b>. Nelle {previous.games} precedenti: {before.toFixed(1)} su {previous.decisions} decisioni.</span></p>
}
export default function LearningProgress({onPractice}:{onPractice:()=>void}){
  const [data,setData]=useState<Progress|null>(null),[error,setError]=useState('')
  useEffect(()=>{let stale=false;api<Progress>('/learning-progress').then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[])
  return <>
    <section className="panel learning-progress"><span className="eyebrow">NELLE PARTITE E NEI DRILL</span><h2>Qualità delle decisioni nel tempo</h2>
      {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Caricamento…</p>}
      {data?.groups.map(g=><details key={g.kind} open={g.kind==='games'}><summary>{g.kind==='games'?'Partite':'Drill'} · ultime {g.recent.games} analizzate</summary>
        {g.recent.decisions?<><QualityNumbers data={g.recent}/><Trend recent={g.recent} previous={g.previous}/></>:<p>Nessuna decisione analizzata in questo gruppo.</p>}
      </details>)}
      <InfoNote summary="Soglie e limiti"><p>{qualityMethod}</p><p>Confronto descrittivo fra blocchi fino a 10 partite, ordinati per data di archiviazione. Avversari, posizioni e difficoltà possono cambiare: il confronto non dimostra da solo un miglioramento.</p></InfoNote>
    </section>
    <section className="panel"><span className="eyebrow">VALUTARE LE MINACCE</span><h2>Il tuo giudizio contro Stockfish</h2>
      {data&&<><p>{data.judgments.matched} / {data.judgments.fresh} giudizi concordano con la fascia di Stockfish, su posizioni che hai indicato come non ricordate.</p><p>{data.judgments.falseAlarms} / {data.judgments.fearedLost} volte hai pensato “già persa” mentre il motore stimava almeno −1,00 dalla tua prospettiva.</p><p className="footnote">{data.judgments.total} valutazioni registrate in totale. Nessuna risposta raccolta significa dato mancante, non assenza di difficoltà. Le posizioni ricordate restano pratica; queste osservazioni non misurano ancora il trasferimento a partite nuove.</p></>}
      <button onClick={onPractice}>Valuta una posizione</button>
    </section>
    <DiagnosisProgress/>
  </>
}
