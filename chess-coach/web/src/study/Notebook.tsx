import {useEffect,useState} from 'react'
import {api} from '../api'
import InfoNote from '../InfoNote'
import MiniBoard from '../MiniBoard'
import type {NotebookTheme,StudyPosition} from './types'
import {pawns} from './types'

export default function Notebook({onPack,onReview,onAsk}:{onPack:(gameId:string)=>void;onReview:(gameId:string,ply:number)=>void;onAsk:(p:StudyPosition)=>void}){
  const [themes,setThemes]=useState<NotebookTheme[]|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{api<{themes:NotebookTheme[]}>('/study/notebook').then(d=>setThemes(d.themes)).catch(e=>setError(e instanceof Error?e.message:'Quaderno non disponibile'))},[])
  return <div className="notebook">
    {error&&<div className="alert" role="alert">{error}</div>}
    <section className="panel study-toolbar"><div><span className="eyebrow">QUADERNO DEGLI ERRORI</span><h2>I tuoi errori, raggruppati per tema</h2><p className="muted">Lezioni salvate e gli esempi più costosi di ogni tema, dalle partite analizzate.</p></div>
      <a className="button-link" href="/api/study/notebook.pgn" download>↓ Esporta PGN annotato</a></section>
    {themes===null&&!error&&<p role="status">Caricamento del quaderno…</p>}
    {themes?.length===0&&<section className="panel"><p className="empty-text">Il quaderno si riempie quando analizzi partite con errori o imprecisioni.</p></section>}
    {themes?.map((t,index)=><details key={t.theme} className="panel notebook-theme" open={index===0}>
      <summary><h3>{t.theme}</h3><span className="count-chip">{t.count} {t.count===1?'decisione':'decisioni'}{t.errors?` · ${t.errors} errori`:''}</span></summary>
      {t.lessons.length>0?<><h4>Le tue lezioni</h4><ul className="study-list">{t.lessons.map(l=><li key={l}>{l}</li>)}</ul></>:<p className="muted">Nessuna lezione salvata per questo tema: creala dal pacchetto di una partita o da “Spiega motivo”.</p>}
      {t.examples.length>0&&<><h4>Esempi più costosi</h4><div className="notebook-examples">{t.examples.map(e=><article key={e.gameId+e.ply} className="notebook-example">
        <MiniBoard fen={e.fen} orientation={e.turn}/>
        <div><strong>{e.moveNumber}{e.turn==='w'?'.':'…'} {e.playedSan}</strong> <span className={e.loss>=180?'error-text':''}>{e.label} · perde {pawns(e.loss)}</span>
          <p className="muted">Meglio {e.bestSan[0]??'—'} · {e.gameTitle}</p>
          <div className="row"><button onClick={()=>onPack(e.gameId)}>Pacchetto della partita</button><button className="quiet" onClick={()=>onAsk({fen:e.fen,title:`${e.gameTitle} · ${e.moveNumber}${e.turn==='w'?'.':'…'}`,gameId:e.gameId,ply:e.ply,move:e.played})}>Chiedi al tutor</button><button className="quiet" onClick={()=>onReview(e.gameId,e.ply)}>Rivedi</button></div></div>
      </article>)}</div></>}
    </details>)}
    <InfoNote summary="Che cosa contiene il PGN">Un capitolo per ogni esempio: la posizione prima della tua mossa, la mossa giocata con perdita e lezioni come commento, e la variante di Stockfish come alternativa. Si apre in Lichess Studio, ChessBase o qualsiasi lettore PGN.</InfoNote>
  </div>
}
