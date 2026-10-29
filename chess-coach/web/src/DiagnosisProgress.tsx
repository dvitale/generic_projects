import {useEffect,useState} from 'react'
import InfoNote from './InfoNote'
import {api} from './api'
import {diagnosisLabels,solutionLabels} from './FailureDiagnosis'

type Window={total:number;counts:Record<string,number>;solutions?:Record<string,number>}
type Summary={total:number;window:number;recent:Window;previous:Window;byKind:Record<string,number>;
  calibration:Record<string,{total:number;matched:number}>;
  themes:{theme:string;total:number;missed:number;rejected:number;misread:number}[]}
const order=['missed_solution','rejected_solution','ignored_threat','phantom_threat','pessimistic','optimistic','accurate']
const confidence:Record<string,string>={uncertain:'Poco sicuro',moderate:'Abbastanza sicuro',confident:'Molto sicuro'}
const share=(n:number,total:number)=>total?Math.round(100*n/total):0

export default function DiagnosisProgress(){
  const [data,setData]=useState<Summary|null>(null),[error,setError]=useState('')
  useEffect(()=>{let stale=false;api<Summary>('/diagnoses/summary').then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[])
  // The most frequent problem in the recent window, excluding the neutral "accurate" reading.
  const top=data?.recent.total?order.filter(l=>l!=='accurate').sort((a,b)=>data.recent.counts[b]-data.recent.counts[a])[0]:null
  return <section className="panel diagnosis-progress"><span className="eyebrow">QUANDO NON TROVI LA SOLUZIONE</span><h2>Diagnosi degli errori</h2>
    {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Caricamento…</p>}
    {data&&!data.total&&<p>Nessuna diagnosi ancora. Quando chiedi la soluzione in Puzzle, Problemi o Blunder prevention, poche domande rapide registrano cosa vedevi.</p>}
    {data&&data.total>0&&<>
      <p>Ultime {data.recent.total} diagnosi{data.previous.total?`, confrontate con le ${data.previous.total} precedenti`:''}. Puzzle {data.byKind.puzzle} · Problemi {data.byKind.problem} · Blunder prevention {data.byKind.prevention}.</p>
      <ul className="bar-list">{order.map(label=>{const now=share(data.recent.counts[label],data.recent.total),before=share(data.previous.counts[label],data.previous.total)
        return <li key={label}><div className="bar-label"><span>{diagnosisLabels[label].title}</span><b>{now}%{data.previous.total>0&&<small> prima {before}%</small>}</b></div><div className="bar-track" aria-hidden="true"><span style={{width:`${Math.max(2,now)}%`}}/></div></li>})}</ul>
      {top&&data.recent.counts[top]>0&&<p className="notice">Su cosa lavorare: <b>{diagnosisLabels[top].title.toLowerCase()}</b>. {diagnosisLabels[top].practice}</p>}
      {data.recent.solutions&&data.recent.counts.missed_solution>0&&<><h3>Soluzioni non viste, per tipo</h3>
        <ul className="bar-list">{(Object.keys(solutionLabels) as (keyof typeof solutionLabels)[]).map(kind=>{const n=data.recent.solutions![kind]??0,now=share(n,data.recent.counts.missed_solution)
          return <li key={kind}><div className="bar-label"><span>{solutionLabels[kind].title}</span><b>{n}</b></div><div className="bar-track" aria-hidden="true"><span style={{width:`${Math.max(2,now)}%`}}/></div></li>})}</ul>
        <p className="footnote">Se prevalgono le mosse tranquille, la profilassi o i miglioramenti, la ricerca si ferma a scacchi, catture e minacce dirette.</p></>}
      <h3>Sicurezza e precisione</h3>
      <ul className="diagnosis-calibration">{Object.entries(data.calibration).filter(([,c])=>c.total).map(([level,c])=><li key={level}>{confidence[level]}: fascia giusta {c.matched} / {c.total} ({share(c.matched,c.total)}%)</li>)}</ul>
      {data.themes.length>0&&<><h3>Per tema (Problemi)</h3><table className="diagnosis-themes"><thead><tr><th>Tema</th><th>Diagnosi</th><th>Non vista</th><th>Scartata</th><th>Lettura errata</th></tr></thead>
        <tbody>{data.themes.map(t=><tr key={t.theme}><td>{t.theme}</td><td>{t.total}</td><td>{t.missed}</td><td>{t.rejected}</td><td>{t.misread}</td></tr>)}</tbody></table></>}
      <InfoNote summary="Come leggere questi dati"><p>Ogni diagnosi ha due assi: la ricerca (soluzione non vista o vista e scartata) e la lettura della posizione (pessimista, ottimista, minaccia non vista, minaccia fantasma o corretta). Una diagnosi può avere più problemi di lettura, quindi le percentuali non sommano a 100. Stockfish classifica anche la soluzione: forzante, mossa tranquilla con una minaccia, profilassi o miglioramento posizionale; il conteggio per tipo riguarda le soluzioni non viste.</p><p>Le risposte sono date dopo aver sbagliato e possono essere razionalizzate; con meno di 20–30 diagnosi le percentuali oscillano molto. I temi compaiono da 3 diagnosi in su.</p></InfoNote>
    </>}
  </section>
}
