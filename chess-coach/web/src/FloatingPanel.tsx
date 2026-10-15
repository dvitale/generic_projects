import {useEffect,useRef,useState,type ReactNode} from 'react'
import {createPortal} from 'react-dom'

interface Frame {x:number;y:number;w:number;h:number}
const KEY='chess-coach-floating-panel'
const clamp=(f:Frame):Frame=>{
  const w=Math.min(Math.max(f.w,300),innerWidth-16),h=Math.min(Math.max(f.h,220),innerHeight-16)
  return {w,h,x:Math.min(Math.max(f.x,8),innerWidth-w-8),y:Math.min(Math.max(f.y,8),innerHeight-h-8)}
}
function initial():Frame{
  try{const saved=JSON.parse(localStorage.getItem(KEY)??'null');if(saved)return clamp(saved)}catch{/* storage unavailable */}
  // Default: the right edge, where the coach column sits beside the board.
  const w=Math.min(460,innerWidth-16)
  return clamp({x:innerWidth-w-16,y:72,w,h:innerHeight-96})
}

/** Non-modal window fixed in the viewport: it stays beside the board while the page scrolls. */
export default function FloatingPanel({title,onClose,children}:{title:string;onClose:()=>void;children:ReactNode}){
  const [frame,setFrame]=useState(initial)
  const panel=useRef<HTMLElement>(null)
  const drag=useRef<{dx:number;dy:number}|null>(null)
  useEffect(()=>{try{localStorage.setItem(KEY,JSON.stringify(frame))}catch{/* storage unavailable */}},[frame])
  useEffect(()=>{
    const key=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()}
    const fit=()=>setFrame(f=>clamp(f))
    window.addEventListener('keydown',key);window.addEventListener('resize',fit)
    return()=>{window.removeEventListener('keydown',key);window.removeEventListener('resize',fit)}
  },[onClose])
  useEffect(()=>{
    // CSS resize changes the element size; keep the saved frame in step with it.
    const node=panel.current
    if(!node)return
    const observer=new ResizeObserver(()=>{if(!drag.current)setFrame(f=>f.w===node.offsetWidth&&f.h===node.offsetHeight?f:{...f,w:node.offsetWidth,h:node.offsetHeight})})
    observer.observe(node)
    return()=>observer.disconnect()
  },[])
  return createPortal(<section ref={panel} className="floating-panel" role="dialog" aria-modal="false" aria-label={title} style={{left:frame.x,top:frame.y,width:frame.w,height:frame.h}}>
    <header className="floating-head"
      onPointerDown={e=>{if((e.target as HTMLElement).closest('button'))return;drag.current={dx:e.clientX-frame.x,dy:e.clientY-frame.y};e.currentTarget.setPointerCapture(e.pointerId)}}
      onPointerMove={e=>{const d=drag.current;if(d)setFrame(f=>clamp({...f,x:e.clientX-d.dx,y:e.clientY-d.dy}))}}
      onPointerUp={()=>{drag.current=null}}>
      <strong>{title}</strong><span className="floating-hint" aria-hidden="true">⠿ trascina</span>
      <button aria-label="Chiudi spiegazione" onClick={onClose}>✕</button>
    </header>
    <div className="floating-body">{children}</div>
  </section>,document.body)
}
