import {useState} from 'react'
import type {Color} from './types'

export default function LichessAnalysis({fen,orientation}:{fen:string;orientation:Color}){
  const [openedUrl,setOpenedUrl]=useState('')
  const url=`https://lichess.org/analysis/standard/${fen.trim().split(/\s+/).map(encodeURIComponent).join('_').replaceAll('%2F','/')}?color=${orientation==='w'?'white':'black'}`
  function open(){
    // Open synchronously from the click, preserving browser popup activation.
    setOpenedUrl(url)
    window.open(url,'_blank','popup=yes,width=1100,height=850,resizable=yes,scrollbars=yes,noopener,noreferrer')
  }
  return <div className="lichess-analysis">
    <button onClick={open} title="Apri la posizione mostrata in una nuova finestra su lichess.org">Analizza con Lichess ↗</button>
    {openedUrl&&<small>Se la finestra non si apre, <a href={openedUrl} target="_blank" rel="noopener noreferrer">apri Lichess in una nuova scheda</a>.</small>}
  </div>
}
