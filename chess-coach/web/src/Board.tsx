import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { Chess, type Square } from 'chess.js'
import type { Color } from './types'

const symbols: Record<string, string> = {wk:'♚',wq:'♛',wr:'♜',wb:'♝',wn:'♞',wp:'♟',bk:'♚',bq:'♛',br:'♜',bb:'♝',bn:'♞',bp:'♟'}
const names: Record<string, string> = {k:'re',q:'donna',r:'torre',b:'alfiere',n:'cavallo',p:'pedone'}
type Gesture = {id:number;from:string;startX:number;startY:number;fen:string;orientation:Color;code:string;size:number;active:boolean;element:HTMLButtonElement}
function Piece({code}:{code:string}) {
  const [missing,setMissing]=useState(false)
  return missing?<span aria-hidden="true" className={`piece ${code[0]==='w'?'white-piece':'black-piece'}`}>{symbols[code]}</span>:
    <img className="piece-image" src={`/pieces/neo/${code}.png`} alt="" aria-hidden="true" draggable={false} onError={()=>setMissing(true)}/>
}
export default function Board({fen, orientation, interactive, legalMoves, onMove, lastMove, animateMove=false}: {fen:string; orientation:Color; interactive:boolean; legalMoves:string[]; onMove:(uci:string)=>void; lastMove?:string;animateMove?:boolean}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [promotion, setPromotion] = useState<string[]>([])
  const [drag, setDrag] = useState<{from:string;code:string;x:number;y:number;size:number}|null>(null)
  const boardElement=useRef<HTMLDivElement>(null)
  const previousFen=useRef(fen)
  const gesture=useRef<Gesture|null>(null)
  const suppressClick=useRef(false)
  function clearDrag() {
    const current=gesture.current
    gesture.current=null
    if(current?.active)suppressClick.current=true
    setDrag(null)
    if(current?.element.hasPointerCapture(current.id))current.element.releasePointerCapture(current.id)
  }
  function cancelDrag(){clearDrag();setSelected(null)}
  useEffect(() => { clearDrag(); setSelected(null); setPromotion([]) }, [fen,orientation,interactive])
  useEffect(()=>{
    const cancel=()=>cancelDrag()
    window.addEventListener('blur',cancel)
    return()=>{window.removeEventListener('blur',cancel);gesture.current=null}
  },[])
  const board = new Chess(fen)
  const files = orientation === 'w' ? 'abcdefgh' : 'hgfedcba'
  const ranks = orientation === 'w' ? '87654321' : '12345678'
  useLayoutEffect(()=>{
    const previous=previousFen.current
    previousFen.current=fen
    if(previous===fen||!animateMove||!lastMove||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return
    const from=lastMove.slice(0,2),to=lastMove.slice(2,4)
    let castling=false
    try {
      const before=new Chess(previous)
      const moved=before.move({from,to,promotion:lastMove[4]})
      if(before.fen()!==fen)return
      castling=moved.isKingsideCastle()||moved.isQueensideCastle()
    }catch{return}
    const animations:Animation[]=[]
    function slide(origin:string,destination:string){
      const start=boardElement.current?.querySelector<HTMLElement>(`[data-square="${origin}"]`)
      const end=boardElement.current?.querySelector<HTMLElement>(`[data-square="${destination}"]`)
      const piece=end?.querySelector<HTMLElement>('.piece-image,.piece')
      if(!start||!end||!piece)return
      const a=start.getBoundingClientRect(),b=end.getBoundingClientRect()
      animations.push(piece.animate([{transform:`translate(${a.left-b.left}px,${a.top-b.top}px)`},{transform:'translate(0,0)'}],{duration:260,easing:'cubic-bezier(.2,.65,.3,1)'}))
    }
    slide(from,to)
    if(castling)slide((to[0]==='g'?'h':'a')+to[1],(to[0]==='g'?'f':'d')+to[1])
    return()=>animations.forEach(animation=>animation.cancel())
  },[fen,orientation,lastMove,animateMove])
  const targets = selected ? legalMoves.filter(m => m.startsWith(selected)).map(m => m.slice(2,4)) : []
  function submit(from:string,to:string) {
      const candidates = legalMoves.filter(m => m.startsWith(from + to))
      if (candidates.length > 1) { setPromotion(candidates); return }
      if (candidates.length === 1) { setSelected(null); onMove(candidates[0]); return }
      setSelected(null)
  }
  function click(square: string) {
    if (!interactive || promotion.length) return
    if (selected && legalMoves.some(m=>m.startsWith(selected+square))) {
      submit(selected,square)
      return
    }
    setSelected(legalMoves.some(m => m.startsWith(square)) ? square : null)
  }
  function pointerDown(event:ReactPointerEvent<HTMLButtonElement>,from:string) {
    if(gesture.current)return
    suppressClick.current=false
    if(!interactive||promotion.length||event.button!==0||!event.isPrimary||!legalMoves.some(m=>m.startsWith(from)))return
    const piece=board.get(from as Square)
    if(!piece)return
    gesture.current={id:event.pointerId,from,startX:event.clientX,startY:event.clientY,fen,orientation,
      code:piece.color+piece.type,size:event.currentTarget.getBoundingClientRect().width,active:false,element:event.currentTarget}
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  function pointerMove(event:ReactPointerEvent<HTMLButtonElement>) {
    const current=gesture.current
    if(!current||current.id!==event.pointerId)return
    if(!interactive||fen!==current.fen||orientation!==current.orientation){cancelDrag();return}
    if(!current.active&&Math.hypot(event.clientX-current.startX,event.clientY-current.startY)<6)return
    current.active=true
    event.preventDefault()
    setSelected(current.from)
    setDrag({from:current.from,code:current.code,x:event.clientX,y:event.clientY,size:current.size})
  }
  function pointerUp(event:ReactPointerEvent<HTMLButtonElement>) {
    const current=gesture.current
    if(!current||current.id!==event.pointerId)return
    clearDrag()
    if(!current.active)return
    event.preventDefault()
    setSelected(null)
    if(!interactive||fen!==current.fen||orientation!==current.orientation)return
    const rect=boardElement.current?.getBoundingClientRect()
    if(!rect||event.clientX<rect.left||event.clientX>=rect.right||event.clientY<rect.top||event.clientY>=rect.bottom)return
    const file=Math.floor((event.clientX-rect.left)/rect.width*8)
    const rank=Math.floor((event.clientY-rect.top)/rect.height*8)
    submit(current.from,files[file]+ranks[rank])
  }
  return <div className="board-wrap">
    <div ref={boardElement} className="board theme-chesscom" role="group" aria-label="Scacchiera"
      onKeyDown={event=>{if(event.key==='Escape'){cancelDrag();setPromotion([])}}}>
      {Array.from(ranks).flatMap((rank, ri) => Array.from(files).map((file, fi) => {
        const square = file + rank
        const piece = board.get(square as Square)
        const lit = lastMove?.slice(0,2) === square || lastMove?.slice(2,4) === square
        return <button key={square} type="button" data-square={square} aria-label={`${square}${piece ? ` ${names[piece.type]} ${piece.color === 'w' ? 'bianco' : 'nero'}` : ''}`} aria-pressed={selected === square}
          className={`square ${(ri+fi)%2 ? 'dark-square' : 'light-square'} ${selected === square ? 'selected-square' : ''} ${lit ? 'last-square' : ''} ${drag?.from===square?'drag-origin':''} ${interactive&&!promotion.length&&legalMoves.some(m=>m.startsWith(square))?'can-drag':''}`}
          draggable={false} onDragStart={event=>event.preventDefault()}
          onPointerDown={event=>pointerDown(event,square)} onPointerMove={pointerMove} onPointerUp={pointerUp}
          onPointerCancel={event=>{if(gesture.current?.id===event.pointerId)cancelDrag()}}
          onLostPointerCapture={event=>{if(gesture.current?.id===event.pointerId)cancelDrag()}}
          onClick={event=>{if(suppressClick.current&&event.detail!==0){suppressClick.current=false;return}click(square)}}>
          {fi === 0 && <span className="rank-label">{rank}</span>}
          {ri === 7 && <span className="file-label">{file}</span>}
          {piece && <Piece key={piece.color+piece.type} code={piece.color+piece.type}/>}
          {targets.includes(square) && <span className={piece ? 'capture-ring' : 'move-dot'} aria-hidden="true"/>}
        </button>
      }))}
    </div>
    {drag&&<div className="dragged-piece" aria-hidden="true" style={{left:drag.x,top:drag.y,width:drag.size,height:drag.size,fontSize:drag.size*.82}}><Piece code={drag.code}/></div>}
    {promotion.length > 0 && <div className="promotion" role="dialog" aria-label="Scegli la promozione">
      <p>Promuovi il pedone</p><div className="row">{promotion.map(move => <button key={move} onClick={() => {setPromotion([]); setSelected(null); if(interactive&&legalMoves.includes(move))onMove(move)}}>{names[move[4]]}</button>)}<button onClick={()=>{setPromotion([]);setSelected(null)}}>Annulla</button></div>
    </div>}
  </div>
}
