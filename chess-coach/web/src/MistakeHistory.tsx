import InfoNote from './InfoNote'
import {useEffect,useState} from 'react'
import {api} from './api'
import type {Evaluation} from './types'
import ChessInsights,{ReasoningSections,type Insight,type Reasoning} from './ChessInsights'
import MistakeComparison,{type Comparison} from './MistakeComparison'
import FloatingPanel from './FloatingPanel'

export interface Mistake {id:number;fen:string;move:string;san:string;createdAt:string;lossCp:number|null;actual:Evaluation;reference:Pick<Evaluation,'cp'|'mate'>;insight?:Insight}
interface Explanation {explanation:{reason:string;continuation:string;lesson:string;sharedIdea?:string;difference?:string;alternative?:string}&Reasoning;comparison?:Comparison;explanationSource?:string;cached:boolean;provider:string}
const score=(e:Pick<Evaluation,'cp'|'mate'>)=>e.mate!==null?e.mate>0?`Matto a favore in ${e.mate}`:`Matto contro in ${Math.abs(e.mate)}`:`${e.cp>=0?'+':''}${(e.cp/100).toFixed(2)}`

function MistakeRow({mistake:m,path,onPlay}:{mistake:Mistake;path:string;onPlay?:(mistake:Mistake)=>void}){
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
    <div className="mistake-heading"><strong>{m.san}</strong><span>{m.lossCp===null?'Confronto con matto: perdita non esprimibile in pedoni':`Calo ${(m.lossCp/100).toFixed(2)} punti`}</span><button disabled={busy} aria-expanded={expanded} onClick={()=>void explain()}>{busy?'Sto preparando…':expanded?'Nascondi spiegazione':'Spiega motivo'}</button></div>
    <small>Migliore alternativa: {score(m.reference)} → tua scelta: {score(m.actual)}</small><small>{new Date(m.createdAt).toLocaleString('it-IT')}</small>
    <details><summary>Variante Stockfish</summary><p className="variation">{m.actual.san.join(' ')}</p></details>
    <ChessInsights insight={m.insight} compact/>
    {onPlay&&<button className="play-refutation" onClick={()=>onPlay(m)} title="Nuova partita da questa posizione, dopo la tua mossa: Stockfish a piena forza cerca la confutazione"><span aria-hidden="true">⚔</span> Gioca {m.san} contro Stockfish</button>}
    {error&&<p role="alert" className="error-text">{error}</p>}
    {expanded&&response&&<FloatingPanel title={`Perché ${m.san} non va`} onClose={()=>setExpanded(false)}><div className="mistake-explanation"><strong>Che cosa cambia rispetto all’alternativa</strong>
      {response.explanation.sharedIdea&&<p><strong>Perché possono sembrare simili. </strong>{response.explanation.sharedIdea}</p>}
      {response.explanation.difference&&<p className="hint"><strong>Il dettaglio decisivo. </strong>{response.explanation.difference}</p>}
      <p>{response.explanation.reason}</p>
      {response.explanation.alternative&&<p><strong>Perché funziona l’alternativa. </strong>{response.explanation.alternative}</p>}
      {response.comparison&&<MistakeComparison value={response.comparison}/>}
      <details><summary>Tattica, posizione e piano</summary><ReasoningSections value={response.explanation}/></details><details><summary>Come leggere la variante</summary><p>{response.explanation.continuation}</p></details><p className="hint">{response.explanation.lesson}</p><small>{response.explanationSource==='verified-mate-contrast'?'Spiegazione del matto ricostruita dalle risposte legali e dalle valutazioni Stockfish, senza generazione LLM.':'Spiegazione DeepSeek basata sulle varianti Stockfish. Può contenere imprecisioni.'}</small></div></FloatingPanel>}
  </li>
}

export default function MistakeHistory({kind,targetId,revision,onPlay}:{kind:'prevention'|'puzzle';targetId:string;revision:number;onPlay?:(mistake:Mistake)=>void}){
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
      <InfoNote summary="Come leggere i tentativi">Calo registrato rispetto alla migliore alternativa, dal tuo punto di vista: non equivale a materiale perso. “Spiega motivo” approfondisce la verifica Stockfish e confronta le varianti. Nei casi di matto direttamente verificabili usa le risposte legali; negli altri casi invia a DeepSeek questa posizione e le varianti da confrontare. La spiegazione può svelare una mossa migliore e viene conservata. “Gioca contro Stockfish” apre una partita dopo il tuo tentativo: difendilo e guarda come il motore lo punisce.</InfoNote>
      <ol className="mistake-list">{items.map(m=><MistakeRow key={m.id} mistake={m} path={path} onPlay={onPlay}/>)}</ol></>}
  </section>
}
