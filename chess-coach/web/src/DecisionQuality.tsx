import {useEffect,useState} from 'react'
import {api} from './api'
import type {Game} from './types'

export type Quality={decisions:number;sound:number;errors:number;inaccuracies:number;advantages:number;maintained:number}
type Flagged={ply:number;san:string;moveNumber:number;color:'w'|'b';kind:'error'|'inaccuracy';lossCp:number|null}
type Summary=Quality&{ready:boolean;moments:{ply:number;san:string;loss:number}[];flagged:Flagged[]}
export function QualityNumbers({data,onMistakes,expanded=false}:{data:Quality;onMistakes?:()=>void;expanded?:boolean}){
  const severity=data.errors?'error':data.inaccuracies?'inaccuracy':'none'
  const mistakes=<><strong className="quality-error-count">{data.errors}</strong><span><span className="quality-error-count">errori rilevanti</span> · <span className="quality-inaccuracy-count">{data.inaccuracies} imprecisioni</span></span></>
  return <div className="quality-stats">
    <div><strong>{data.sound} / {data.decisions}</strong><span>decisioni senza perdite rilevanti</span></div>
    {onMistakes?<button className={`quality-mistakes severity-${severity}`} onClick={onMistakes} aria-expanded={expanded} aria-controls="quality-mistake-details">{mistakes}<small>{expanded?'Nascondi le mosse ↑':'Mostra le mosse ↓'}</small></button>:<div className={`quality-mistakes severity-${severity}`}>{mistakes}</div>}
    <div><strong>{data.advantages?`${data.maintained} / ${data.advantages}`:'—'}</strong><span>decisioni che conservano il vantaggio</span></div>
  </div>
}
export const qualityMethod='Solo le tue decisioni non obbligate; nei drill escludiamo la sequenza iniziale. Imprecisione: perdita da 0,80 a meno di 1,80 punti; errore rilevante: almeno 1,80. Vantaggio conservato: almeno +1,50 prima e dopo la tua mossa, dalla tua prospettiva. Sono soglie operative, non punti Elo o pezzi necessariamente persi.'
export default function DecisionQuality({game,onPosition,onAnalyze,disabled}:{game:Game;onPosition:(ply:number)=>void;onAnalyze:()=>void;disabled:boolean}){
  const [data,setData]=useState<Summary|null>(null),[error,setError]=useState('')
  const [expanded,setExpanded]=useState(false)
  const [filter,setFilter]=useState<'all'|'error'|'inaccuracy'>('all')
  useEffect(()=>{let stale=false;setData(null);setError('');setExpanded(false);setFilter('all');api<Summary>(`/games/${game.id}/decision-quality`).then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[game.id,game.version,game.revision,game.analysis?.createdAt])
  const flagged=(data?.flagged??[]).filter(m=>filter==='all'||m.kind===filter)
  return <section className="panel" aria-label="Qualità delle decisioni">
    <span className="eyebrow">LE TUE DECISIONI</span><h2>Cosa hai mantenuto, cosa rivedere</h2>
    {game.result&&<p><strong>{game.result==='1/2-1/2'?'Partita patta':game.result===(game.playerColor==='w'?'1-0':'0-1')?'Hai vinto':'Hai perso'} · {game.result}</strong></p>}
    {error?<p role="alert">{error}</p>:!data?<p role="status">Raccolta delle decisioni…</p>:!data.ready?<><p>Completa l’analisi Stockfish per vedere la qualità delle tue scelte.</p><button disabled={disabled} onClick={onAnalyze}>{disabled?'Analisi in corso…':'Analizza le decisioni'}</button></>:<>
      <QualityNumbers data={data} onMistakes={()=>setExpanded(v=>!v)} expanded={expanded}/>
      <section id="quality-mistake-details" aria-label="Mosse da rivedere" hidden={!expanded}>
        <div className="quality-filters" role="group" aria-label="Filtra le mosse">
          <button aria-pressed={filter==='all'} onClick={()=>setFilter('all')}>Tutte ({data.errors+data.inaccuracies})</button>
          <button className="severity-error" aria-pressed={filter==='error'} onClick={()=>setFilter('error')}>Errori rilevanti ({data.errors})</button>
          <button className="severity-inaccuracy" aria-pressed={filter==='inaccuracy'} onClick={()=>setFilter('inaccuracy')}>Imprecisioni ({data.inaccuracies})</button>
        </div>
        {flagged.length?<><p className="footnote">Le tue mosse in ordine di partita. Selezionane una per aprire la posizione e il confronto con Stockfish e Maia.</p><ol className="quality-move-list">{flagged.map(m=><li key={m.ply}><button className={`moment quality-severity severity-${m.kind}`} onClick={()=>onPosition(m.ply)}><span>{m.moveNumber}{m.color==='w'?'.':'…'} {m.san} · {m.kind==='error'?'Errore rilevante':'Imprecisione'}</span><small>{m.lossCp===null?'Confronto con matto':`Perdita ${(m.lossCp/100).toFixed(2)} punti`} · Rivedi →</small></button></li>)}</ol></>:<p>Nessuna mossa in questa categoria.</p>}
      </section>
      {!data.decisions?<p>Nessuna decisione non obbligata da valutare.</p>:!data.errors?<p>Nessun errore rilevante rilevato in queste {data.decisions} decisioni. È un risultato utile, anche se il profilo Maia fosse 600.</p>:<p>Rivedi queste scelte e le risorse che avevi prima di giudicare l’intera partita.</p>}
      {!expanded&&data.moments.map(m=><button className={`moment quality-severity severity-${m.loss>=180?'error':'inaccuracy'}`} key={m.ply} onClick={()=>onPosition(m.ply)}><span>Rivedi {m.san} · {m.loss>=180?'Errore rilevante':'Imprecisione'}</span><small>Perdita {(m.loss/100).toFixed(2)} punti</small></button>)}
    </>}
    <details><summary>Come leggere questi dati</summary><p className="footnote">{qualityMethod} Analisi a budget limitato: le valutazioni possono cambiare approfondendo.</p><p className="footnote">“Senza perdite rilevanti” non dimostra che hai visto ed evitato una minaccia. Conservare il vantaggio misura singole scelte, non garantisce la vittoria finale.</p></details>
  </section>
}
