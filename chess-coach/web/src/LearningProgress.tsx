import {useEffect,useState} from 'react'
import {api} from './api'
import {QualityNumbers,qualityMethod,type Quality} from './DecisionQuality'
type Window=Quality&{games:number}
type Progress={groups:{kind:string;recent:Window;previous:Window}[];judgments:{total:number;fresh:number;matched:number;fearedLost:number;falseAlarms:number}}
export default function LearningProgress({onPractice}:{onPractice:()=>void}){
  const [data,setData]=useState<Progress|null>(null),[error,setError]=useState('')
  useEffect(()=>{let stale=false;api<Progress>('/learning-progress').then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[])
  return <>
    <section className="panel learning-progress"><span className="eyebrow">NELLE PARTITE E NEI DRILL</span><h2>Qualità delle decisioni nel tempo</h2>
      {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Caricamento…</p>}
      {data?.groups.map(g=><details key={g.kind} open={g.kind==='games'}><summary>{g.kind==='games'?'Partite':'Drill'} · ultime {g.recent.games} analizzate</summary>
        {g.recent.decisions?<><QualityNumbers data={g.recent}/><p className="footnote">Errori rilevanti ogni 100 decisioni: {(100*g.recent.errors/g.recent.decisions).toFixed(1)}. {g.previous.decisions?`Nelle ${g.previous.games} precedenti: ${(100*g.previous.errors/g.previous.decisions).toFixed(1)} su ${g.previous.decisions} decisioni.`:'Non ci sono ancora partite precedenti per il confronto.'}</p></>:<p>Nessuna decisione analizzata in questo gruppo.</p>}
      </details>)}
      <p className="footnote">Confronto descrittivo fra blocchi fino a 10 partite, ordinati per data di archiviazione. Avversari, posizioni e difficoltà possono cambiare: il confronto non dimostra da solo un miglioramento.</p>
      <details><summary>Soglie e limiti</summary><p className="footnote">{qualityMethod}</p></details>
    </section>
    <section className="panel"><span className="eyebrow">VALUTARE LE MINACCE</span><h2>La tua impressione e la posizione</h2>
      {data&&<><p>{data.judgments.matched} / {data.judgments.fresh} giudizi concordano con la fascia di Stockfish, su posizioni che hai indicato come non ricordate.</p><p>{data.judgments.falseAlarms} / {data.judgments.fearedLost} volte hai pensato “già persa” mentre il motore stimava almeno −1,00 dalla tua prospettiva.</p><p className="footnote">{data.judgments.total} valutazioni registrate in totale. Nessuna risposta raccolta significa dato mancante, non assenza di difficoltà. Le posizioni ricordate restano pratica; queste osservazioni non misurano ancora il trasferimento a partite nuove.</p></>}
      <button onClick={onPractice}>Valuta una posizione</button>
    </section>
  </>
}
