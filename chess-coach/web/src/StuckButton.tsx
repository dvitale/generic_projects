import {useState} from 'react'
import {api} from './api'
import type {Game} from './types'

/** «Qui mi sento bloccato»: save the moment without help, or open the guided search on a separate board. */
export default function StuckButton({game,ply,origin,disabled,onGuide,onMarked}:{game:Game;ply:number;origin:'live'|'retrospective';disabled?:boolean;onGuide:(id:string)=>void;onMarked:(message:string)=>void}){
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const live=origin==='live'
  async function start(mode:'mark'|'guide'){
    setBusy(true);setError('')
    try{
      const episode=await api<{id:string}>('/alternatives/episodes',{game_id:game.id,ply,revision:game.revision,mode,origin})
      setOpen(false)
      if(mode==='guide')onGuide(episode.id)
      else onMarked(live?'Momento segnato senza aiuti: lo ritrovi in Trova un’alternativa. Continua pure la partita.':'Momento segnato: lo ritrovi in Trova un’alternativa.')
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  return <span className="stuck-control">
    <button className="stuck-button" aria-expanded={open} disabled={disabled||busy} title="Segnala una posizione in cui tutte le mosse ti sembrano perdenti" onClick={()=>setOpen(v=>!v)}>{live?'Qui mi sento bloccato':'Qui mi sentivo bloccato'}</button>
    {open&&<span className="stuck-menu" role="group" aria-label="Che cosa vuoi fare?">
      <button disabled={busy} onClick={()=>void start('mark')}>Segna e continua<small>Nessun aiuto: lo rivedi dopo</small></button>
      <button className="primary" disabled={busy} onClick={()=>void start('guide')}>Aiutami a ragionare<small>{live?'Su una scacchiera separata: la partita aspetta':'Su una scacchiera separata'}</small></button>
      {error&&<span role="alert" className="stuck-error">{error}</span>}
    </span>}
  </span>
}
