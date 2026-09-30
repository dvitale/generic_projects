import {useLayoutEffect, useRef, useState} from 'react'

const pause=(ms:number)=>new Promise<void>(resolve=>window.setTimeout(resolve,ms))
type Frame={move:string|null;lastMove?:string;reverse:boolean;phase:'idle'|'checking'|'hold'|'returning'}
const initial:Frame={move:null,reverse:false,phase:'idle'}

/** Keep the attempted position visible, then replay the inverse transition on failure. */
export function useTrainingMove(key:string){
  const [frame,setFrame]=useState<Frame>(initial)
  const generation=useRef(0)
  const pending=useRef(false)
  useLayoutEffect(()=>{generation.current++;pending.current=false;setFrame(initial);return()=>{generation.current++;pending.current=false}},[key])
  function start(move:string){
    if(pending.current)return null
    pending.current=true
    const ticket=++generation.current
    setFrame({move,lastMove:move,reverse:false,phase:'checking'})
    return ticket
  }
  const current=(ticket:number)=>ticket===generation.current
  async function finish(ticket:number,accepted:boolean){
    if(!current(ticket))return
    if(accepted){setFrame(f=>({...f,phase:'idle'}));pending.current=false;return}
    setFrame(f=>({...f,phase:'hold'}))
    await pause(1100)
    if(!current(ticket))return
    setFrame(f=>({...f,move:null,reverse:true,phase:'returning'}))
    await pause(window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:700)
    if(!current(ticket))return
    setFrame(f=>({...f,phase:'idle'}));pending.current=false
  }
  function show(move:string|null){generation.current++;pending.current=false;setFrame({move,lastMove:move??undefined,reverse:false,phase:'idle'})}
  return {...frame,start,finish,current,show,
    message:frame.phase==='hold'?'Osserva la mossa: tra poco torniamo alla posizione iniziale.':frame.phase==='returning'?'Ritorno alla posizione iniziale…':null}
}
