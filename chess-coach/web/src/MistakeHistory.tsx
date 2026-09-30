import {useEffect,useState} from 'react'
import {api} from './api'
import type {Evaluation} from './types'

interface Mistake {id:number;san:string;createdAt:string;lossCp:number|null;actual:Evaluation;reference:Pick<Evaluation,'cp'|'mate'>}
interface Explanation {explanation:{reason:string;continuation:string;lesson:string};cached:boolean;provider:string}
const score=(e:Pick<Evaluation,'cp'|'mate'>)=>e.mate!==null?e.mate>0?`Matto a favore in ${e.mate}`:`Matto contro in ${Math.abs(e.mate)}`:`${e.cp>=0?'+':''}${(e.cp/100).toFixed(2)}`

function MistakeRow({mistake:m,path}:{mistake:Mistake;path:string}){
  const [response,setResponse]=useState<Explanation|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [expanded,setExpanded]=useState(false)
  async function explain(){
    if(response){setExpanded(v=>!v);return}
    if(busy)return
    setBusy(true);setError('')
    try{setResponse(await api<Explanation>(`${path}/${m.id}/explain`,{}));setExpanded(true)}
    catch(e){setError(e instanceof Error?e.message:'Spiegazione non disponibile. Riprova.')}
    finally{setBusy(false)}
  }
  return <li className="mistake-row">
    <div className="mistake-heading"><strong>{m.san}</strong><span>{m.lossCp===null?'Confronto con matto: perdita non esprimibile in pedoni':`Perdita ${(m.lossCp/100).toFixed(2)} pedoni`}</span><button disabled={busy} aria-expanded={expanded} onClick={()=>void explain()}>{busy?'Sto preparando…':expanded?'Nascondi spiegazione':'Spiega motivo'}</button></div>
    <small>Migliore alternativa: {score(m.reference)} → tua scelta: {score(m.actual)}</small><small>{new Date(m.createdAt).toLocaleString('it-IT')}</small>
    <details><summary>Variante Stockfish</summary><p className="variation">{m.actual.san.join(' ')}</p></details>
    {error&&<p role="alert" className="error-text">{error}</p>}
    {expanded&&response&&<div className="mistake-explanation" role="status"><strong>Perché peggiora la posizione</strong><p>{response.explanation.reason}</p><p>{response.explanation.continuation}</p><p className="hint">{response.explanation.lesson}</p><small>Spiegazione DeepSeek basata sulla variante Stockfish. Può contenere imprecisioni.</small></div>}
  </li>
}

export default function MistakeHistory({kind,targetId,revision}:{kind:'prevention'|'puzzle';targetId:string;revision:number}){
  const [items,setItems]=useState<Mistake[]>([])
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const path=`/training/${kind}/${targetId}/mistakes`
  useEffect(()=>{
    let stale=false
    api<Mistake[]>(path).then(data=>{if(!stale){setItems(data);setError('')}}).catch(e=>{if(!stale)setError(e.message)})
    return()=>{stale=true}
  },[path,revision,retry])
  return <section className="panel mistake-history" aria-label="Tentativi sbagliati"><span className="eyebrow">IMPARA DAI TENTATIVI</span><h3>Tentativi sbagliati ({items.length})</h3>
    {error&&<p role="alert">{error} <button onClick={()=>setRetry(n=>n+1)}>Ricarica tentativi</button></p>}
    {!items.length?<p className="muted">Qui ritroverai gli errori di questa posizione, anche nelle prossime sessioni.</p>:<>
      <p className="footnote">Perdita rispetto alla migliore alternativa; valori dal tuo punto di vista. “Spiega motivo” invia a DeepSeek questa posizione e le varianti Stockfish. La spiegazione può svelare una mossa migliore e viene conservata.</p>
      <ol className="mistake-list">{items.map(m=><MistakeRow key={m.id} mistake={m} path={path}/>)}</ol></>}
  </section>
}
