import {useEffect,useSyncExternalStore} from 'react'
import type {Color} from './types'

// Session-only: a flipped board is a viewing choice, not a saved preference.
let flipped=false
const listeners=new Set<()=>void>()

function setFlip(value:boolean){flipped=value;listeners.forEach(listener=>listener())}
export function toggleBoardFlip(){setFlip(!flipped)}
/** The new game already puts the chosen side at the bottom. */
export function resetBoardFlip(){setFlip(false)}

export function useBoardFlip(){
  return useSyncExternalStore(listener=>{listeners.add(listener);return()=>listeners.delete(listener)},()=>flipped)
}

/** The side shown at the bottom, after the user's flip. */
export function useBoardOrientation(base:Color):Color{
  return useBoardFlip()?(base==='w'?'b':'w'):base
}

/** "F" flips the board when the focus is not in a field, as on Lichess. */
export function useFlipShortcut(){
  useEffect(()=>{
    const key=(event:KeyboardEvent)=>{
      if(event.key.toLowerCase()!=='f'||event.defaultPrevented||event.altKey||event.ctrlKey||event.metaKey)return
      if((event.target as HTMLElement).closest?.('input,select,textarea,[contenteditable=true]'))return
      event.preventDefault();toggleBoardFlip()
    }
    window.addEventListener('keydown',key)
    return()=>window.removeEventListener('keydown',key)
  },[])
}

export function FlipBoardButton(){
  const on=useBoardFlip()
  return <button className="pill flip-button" aria-pressed={on} aria-label="Inverti scacchiera" title="Inverti scacchiera (F)" onClick={toggleBoardFlip}><span aria-hidden="true">⇅</span> <span className="label-long">Inverti</span></button>
}
