import {useEffect,useRef} from 'react'
import type {Game} from './types'

const key=(g:Game)=>`sparringmate-turn:${g.id}:${g.revision}:${g.version}`
type Timer={key:string;milliseconds:number;started:number|null}

/** Active time on this board. Missing measurements stay unknown, never zero. */
export function useMoveTime(game:Game|null,active:boolean) {
  const timer=useRef<Timer|null>(null)
  const current=useRef({game,active});current.current={game,active}
  function persist(){
    const t=timer.current;if(!t)return
    if(t.started!==null){t.milliseconds+=performance.now()-t.started;t.started=null}
    try{sessionStorage.setItem(t.key,String(t.milliseconds))}catch{/* Timing remains usable in memory. */}
  }
  function resume(){
    const t=timer.current
    if(t&&current.current.active&&!document.hidden&&t.started===null)t.started=performance.now()
  }
  function begin(next:Game){
    persist()
    if(timer.current?.key.startsWith(`sparringmate-turn:${next.id}:`))try{sessionStorage.removeItem(timer.current.key)}catch{/* Optional cache. */}
    timer.current={key:key(next),milliseconds:0,started:null}
    try{sessionStorage.setItem(key(next),'0')}catch{/* Optional cache. */}
  }
  function elapsed(snapshot:Game):number|null{
    const t=timer.current
    if(!t||t.key!==key(snapshot))return null
    persist();const seconds=t.milliseconds/1000;resume()
    return Math.min(604800,Math.max(0,seconds))
  }
  useEffect(()=>{
    persist()
    if(!game){timer.current=null;return}
    const id=key(game)
    if(timer.current?.key!==id){
      let cached:string|null=null
      try{cached=sessionStorage.getItem(id)}catch{/* No recorded beginning for this turn. */}
      timer.current=cached!==null&&Number.isFinite(Number(cached))?{key:id,milliseconds:Math.max(0,Number(cached)),started:null}:null
    }
    resume()
    const visibility=()=>{persist();resume()}
    const hide=()=>persist()
    document.addEventListener('visibilitychange',visibility)
    window.addEventListener('pagehide',hide)
    return()=>{persist();document.removeEventListener('visibilitychange',visibility);window.removeEventListener('pagehide',hide)}
  },[game?.id,game?.version,game?.revision,active])
  return {begin,elapsed}
}
