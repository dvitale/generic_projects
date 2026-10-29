import {useState} from 'react'
import MiniBoard from './MiniBoard'
import type {Color} from './types'
import type {Quality} from './DecisionQuality'

export type Saved={id:string;number?:number|null;title:string;createdAt:string;plies:number;source:string;engineLabel?:string|null;engineVersion?:string|null;playerColor?:Color;elo?:number;result?:string|null;fen?:string;quality?:Quality|null}
type Outcome='win'|'loss'|'draw'|'open'
type Filter='all'|Outcome

export function outcome(g:Saved):Outcome{
  if(!g.result)return 'open'
  if(g.result==='1/2-1/2')return 'draw'
  return g.result===(g.playerColor==='b'?'0-1':'1-0')?'win':'loss'
}
const outcomeLabel:Record<Outcome,string>={win:'Vinta',loss:'Persa',draw:'Patta',open:'In corso'}
const filters:{id:Filter;label:string}[]=[{id:'all',label:'Tutte'},{id:'win',label:'Vinte'},{id:'loss',label:'Perse'},{id:'draw',label:'Patte'},{id:'open',label:'In corso'}]

export default function GameArchive({games,disabled,onOpen}:{games:Saved[];disabled:boolean;onOpen:(id:string)=>void}){
  const [filter,setFilter]=useState<Filter>('all')
  const [preview,setPreview]=useState<string|null>(null)
  const shown=games.filter(g=>filter==='all'||outcome(g)===filter)
  return <section className="archive">
    <div className="section-head"><h2>Le tue partite</h2><div className="row">{shown.length>0&&<a className="button-link" href={`/api/games/pgn?ids=${shown.map(g=>encodeURIComponent(g.id)).join(',')}`} download title="Un unico file PGN con le partite elencate, tempi inclusi">↓ Esporta PGN ({shown.length})</a>}<span>{games.length} salvate</span></div></div>
    {games.length?<>
      <div className="segmented archive-filters" role="group" aria-label="Filtra le partite">{filters.map(f=><button key={f.id} aria-pressed={filter===f.id} onClick={()=>setFilter(f.id)}>{f.label}<small>{f.id==='all'?games.length:games.filter(g=>outcome(g)===f.id).length}</small></button>)}</div>
      <div className="game-table-head" aria-hidden="true"><span>Esito</span><span>Partita</span><span>Colore</span><span>Qualità</span><span>Mosse</span><span>Data</span></div>
      <div className="game-list">{shown.map(item=>{
        const result=outcome(item),q=item.quality
        return <div className="game-row" key={item.id}><button onClick={()=>onOpen(item.id)} disabled={disabled} onPointerEnter={()=>setPreview(item.id)} onPointerLeave={()=>setPreview(p=>p===item.id?null:p)} onFocus={()=>setPreview(item.id)} onBlur={()=>setPreview(p=>p===item.id?null:p)}>
          <span className={`result-badge result-${result}`}>{outcomeLabel[result]}</span>
          <span className="game-title"><strong>{item.number!=null&&<span className="game-number">#{item.number}</span>}{item.title}</strong><small>{item.source==='pgn'?'Importata da PGN':item.source==='drill'?'Drill':item.source==='stockfish'?'Contro Stockfish':`Contro ${item.engineLabel??'Maia'}${item.engineVersion&&item.engineLabel!=='Maia'?` (${item.engineVersion})`:''}`}{item.result?` · ${item.result}`:''}</small></span>
          <span className="game-color">{item.playerColor&&<><i className={`side-dot side-dot-${item.playerColor}`} aria-hidden="true"/>{item.playerColor==='w'?'Bianco':'Nero'}</>}</span>
          <span className="game-quality">{q&&q.decisions?<><b>{Math.round(100*q.sound/q.decisions)}%</b><small>{q.errors===1?'1 errore':q.errors?`${q.errors} errori`:'nessun errore'}</small></>:<small>da analizzare</small>}</span>
          <span className="game-plies">{Math.ceil(item.plies/2)}</span>
          <span className="game-date">{new Date(item.createdAt).toLocaleDateString('it-IT',{day:'2-digit',month:'short',year:'2-digit'})}</span>
          <span className="arrow" aria-hidden="true">→</span>
          {preview===item.id&&item.fen&&<span className="game-preview"><MiniBoard fen={item.fen} orientation={item.playerColor}/></span>}
        </button><a className="row-download" href={`/api/games/${encodeURIComponent(item.id)}/pgn`} download aria-label={`Esporta PGN di ${item.title}`} title="Esporta PGN (tempi inclusi)">↓ PGN</a></div>
      })}</div>
      {!shown.length&&<p className="empty-text">Nessuna partita in questa categoria.</p>}
      <p className="footnote">Qualità: quota delle tue decisioni non obbligate senza perdite rilevanti, quando l’analisi Stockfish è completa. Non è un punteggio Elo.</p>
    </>:<p className="empty-text">Le partite vengono salvate automaticamente, mossa dopo mossa.</p>}
  </section>
}
