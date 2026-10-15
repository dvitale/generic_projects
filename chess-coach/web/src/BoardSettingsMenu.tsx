import {useEffect,useRef,useState} from 'react'
import {boardThemes,updateBoardSettings,useBoardSettings} from './boardSettings'

export default function BoardSettingsMenu(){
  const settings=useBoardSettings()
  const [open,setOpen]=useState(false)
  const root=useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!open)return
    const close=(event:Event)=>{if(event instanceof KeyboardEvent?event.key==='Escape':!root.current?.contains(event.target as Node))setOpen(false)}
    document.addEventListener('pointerdown',close);document.addEventListener('keydown',close)
    return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',close)}
  },[open])
  return <div className="settings-menu" ref={root}>
    <button className="pill" aria-expanded={open} aria-controls="board-settings" onClick={()=>setOpen(v=>!v)}><span aria-hidden="true">⚙</span> Scacchiera</button>
    {open&&<div className="settings-popover" id="board-settings" role="group" aria-label="Impostazioni della scacchiera">
      <span className="eyebrow">TEMA</span>
      <div className="theme-options">{boardThemes.map(t=><button key={t.id} className={`theme-option board-theme-${t.id}`} aria-pressed={settings.theme===t.id} onClick={()=>updateBoardSettings({theme:t.id})}><span className="theme-swatch" aria-hidden="true"/>{t.label}</button>)}</div>
      <label className="switch"><input type="checkbox" checked={settings.sound} onChange={e=>updateBoardSettings({sound:e.target.checked})}/>Suoni delle mosse</label>
      <label className="switch"><input type="checkbox" checked={settings.evalBar} onChange={e=>updateBoardSettings({evalBar:e.target.checked})}/>Barra di valutazione</label>
    </div>}
  </div>
}
