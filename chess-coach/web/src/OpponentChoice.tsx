import {useCallback,useEffect,useState} from 'react'
import {api} from './api'

export type Engine='maia'|'experimental'
export type ExperimentalStatus={enabled:boolean;available?:boolean;engine?:string;version?:string;ratingBounds?:[number,number];calibrated?:boolean;error?:string}

/** Experimental service state, checked again whenever the Play setup is shown or the player asks. */
export function useOpponents(active:boolean){
  const [status,setStatus]=useState<ExperimentalStatus|null>(null)
  const [checking,setChecking]=useState(false)
  const refresh=useCallback(()=>{
    setChecking(true)
    api<{experimental:ExperimentalStatus}>('/opponents').then(r=>setStatus(r.experimental)).catch(e=>setStatus({enabled:true,available:false,error:e instanceof Error?e.message:'Stato non disponibile'})).finally(()=>setChecking(false))
  },[])
  useEffect(()=>{if(active)refresh()},[active,refresh])
  return {status,checking,refresh}
}

/** Levels the experimental model was trained on, in steps of 100 like the slider. */
export function experimentalRange(status:ExperimentalStatus|null):[number,number]{
  const [low,high]=status?.ratingBounds??[600,2600]
  return [Math.max(600,Math.ceil(low/100)*100),Math.min(2600,Math.floor(high/100)*100)]
}

export default function OpponentChoice({engine,onEngine,status,checking,onRefresh,disabled}:{engine:Engine;onEngine:(engine:Engine)=>void;status:ExperimentalStatus|null;checking:boolean;onRefresh:()=>void;disabled?:boolean}){
  // The selector exists only where the reversible configuration option enables the experimental engine.
  if(!status?.enabled)return null
  return <div className="opponent-choice">
    <div className="field-label">Motore</div>
    <div className="segmented" role="group" aria-label="Motore">{([['maia','Maia'],['experimental','Sperimentale']] as const).map(([value,label])=>
      <button key={value} aria-pressed={engine===value} disabled={disabled} onClick={()=>onEngine(value)}>{label}</button>)}</div>
    {engine==='experimental'&&<div className="opponent-status" role="status">
      <p><span className={status.available?'status-dot':'status-dot waiting'}/>{checking?'Controllo del servizio…':status.available?`Servizio disponibile · ${status.version}`:`Servizio non disponibile: ${status.error}`}
        <button className="quiet" disabled={checking} onClick={onRefresh}>Ricontrolla</button></p>
      <p className="footnote">Livello Elo non ancora calibrato: il numero guida il modello, che è stato addestrato su rating Lichess rapid, ma non garantisce quella forza di gioco. Motore e versione restano fissati per tutta la partita.</p>
    </div>}
  </div>
}
