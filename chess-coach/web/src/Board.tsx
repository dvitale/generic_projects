import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { Chess, type Square } from 'chess.js'
import type { Color } from './types'

const symbols: Record<string, string> = {wk:'♚',wq:'♛',wr:'♜',wb:'♝',wn:'♞',wp:'♟',bk:'♚',bq:'♛',br:'♜',bb:'♝',bn:'♞',bp:'♟'}
const names: Record<string, string> = {k:'re',q:'donna',r:'torre',b:'alfiere',n:'cavallo',p:'pedone'}
type Gesture = {id:number;from:string;startX:number;startY:number;fen:string;orientation:Color;code:string;size:number;active:boolean;element:HTMLButtonElement}
type Annotation = {from:string;to:string}
type Drawing = {id:number;from:string;fen:string;orientation:Color;element:HTMLButtonElement}

function BoardAnnotation({from,to,orientation,preview=false}:Annotation&{orientation:Color;preview?:boolean}) {
  function center(square:string){
    const file=square.charCodeAt(0)-97,rank=Number(square[1])-1
    return [(orientation==='w'?file:7-file)*100+50,(orientation==='w'?7-rank:rank)*100+50]
  }
  const [x1,y1]=center(from),[x2,y2]=center(to)
  const attributes={'data-from':from,'data-to':to,className:preview?'annotation-preview':'board-annotation'}
  if(from===to)return <circle {...attributes} cx={x1} cy={y1} r="36" fill="none" stroke="currentColor" strokeWidth="9"/>
  const length=Math.hypot(x2-x1,y2-y1),dx=(x2-x1)/length,dy=(y2-y1)/length
  const baseX=x2-dx*30,baseY=y2-dy*30
  const points=[[x1-dy*8,y1+dx*8],[baseX-dy*8,baseY+dx*8],[baseX-dy*24,baseY+dx*24],[x2,y2],[baseX+dy*24,baseY-dx*24],[baseX+dy*8,baseY-dx*8],[x1+dy*8,y1-dx*8]]
  return <polygon {...attributes} points={points.map(p=>p.join(',')).join(' ')} fill="currentColor"/>
}
function Piece({code}:{code:string}) {
  const [missing,setMissing]=useState(false)
  return missing?<span aria-hidden="true" className={`piece ${code[0]==='w'?'white-piece':'black-piece'}`}>{symbols[code]}</span>:
    <img className="piece-image" src={`/pieces/neo/${code}.png`} alt="" aria-hidden="true" draggable={false} onError={()=>setMissing(true)}/>
}
export default function Board({fen, orientation, interactive, legalMoves, onMove, lastMove, animateMove=false}: {fen:string; orientation:Color; interactive:boolean; legalMoves:string[]; onMove:(uci:string)=>void; lastMove?:string;animateMove?:boolean}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [promotion, setPromotion] = useState<string[]>([])
  const [drag, setDrag] = useState<{from:string;code:string;x:number;y:number;size:number}|null>(null)
  const [annotations,setAnnotations]=useState<Annotation[]>([])
  const [preview,setPreview]=useState<Annotation|null>(null)
  const drawing=useRef<Drawing|null>(null)
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
  function cancelDrawing(){
    const current=drawing.current
    drawing.current=null;setPreview(null)
    if(current?.element.hasPointerCapture(current.id))current.element.releasePointerCapture(current.id)
  }
  function clearAnnotations(){cancelDrawing();setAnnotations([])}
  useEffect(() => { clearDrag(); setSelected(null); setPromotion([]) }, [fen,orientation,interactive])
  useEffect(()=>{clearAnnotations()},[fen,orientation])
  useEffect(()=>{
    const cancel=()=>{cancelDrag();cancelDrawing()}
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')clearAnnotations()}
    window.addEventListener('blur',cancel)
    window.addEventListener('keydown',escape)
    return()=>{window.removeEventListener('blur',cancel);window.removeEventListener('keydown',escape);gesture.current=null;drawing.current=null}
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
    if(gesture.current||drawing.current)return
    suppressClick.current=false
    if(event.button===2&&event.isPrimary&&!promotion.length){
      event.preventDefault();setSelected(null)
      drawing.current={id:event.pointerId,from,fen,orientation,element:event.currentTarget}
      setPreview({from,to:from})
      event.currentTarget.setPointerCapture(event.pointerId)
      return
    }
    if(event.button===0)clearAnnotations()
    if(!interactive||promotion.length||event.button!==0||!event.isPrimary||!legalMoves.some(m=>m.startsWith(from)))return
    const piece=board.get(from as Square)
    if(!piece)return
    gesture.current={id:event.pointerId,from,startX:event.clientX,startY:event.clientY,fen,orientation,
      code:piece.color+piece.type,size:event.currentTarget.getBoundingClientRect().width,active:false,element:event.currentTarget}
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  function pointerMove(event:ReactPointerEvent<HTMLButtonElement>) {
    const annotation=drawing.current
    if(annotation?.id===event.pointerId){
      if(!(event.buttons&2)||fen!==annotation.fen||orientation!==annotation.orientation){cancelDrawing();return}
      event.preventDefault()
      const to=squareAtPoint(event.clientX,event.clientY)
      setPreview(to?{from:annotation.from,to}:null)
      return
    }
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
    const annotation=drawing.current
    if(annotation?.id===event.pointerId){
      event.preventDefault();cancelDrawing()
      if(event.button!==2||fen!==annotation.fen||orientation!==annotation.orientation)return
      const to=squareAtPoint(event.clientX,event.clientY)
      if(to)setAnnotations(current=>current.some(a=>a.from===annotation.from&&a.to===to)?current.filter(a=>a.from!==annotation.from||a.to!==to):[...current,{from:annotation.from,to}])
      return
    }
    const current=gesture.current
    if(!current||current.id!==event.pointerId)return
    clearDrag()
    if(!current.active)return
    event.preventDefault()
    setSelected(null)
    if(!interactive||fen!==current.fen||orientation!==current.orientation)return
    const to=squareAtPoint(event.clientX,event.clientY)
    if(to)submit(current.from,to)
  }
  function squareAtPoint(x:number,y:number){
    const rect=boardElement.current?.getBoundingClientRect()
    if(!rect||x<rect.left||x>=rect.right||y<rect.top||y>=rect.bottom)return null
    return files[Math.floor((x-rect.left)/rect.width*8)]+ranks[Math.floor((y-rect.top)/rect.height*8)]
  }
  return <div className="board-wrap">
    <div ref={boardElement} className="board theme-chesscom" role="group" aria-label="Scacchiera"
      onContextMenu={event=>event.preventDefault()}
      onKeyDown={event=>{if(event.key==='Escape'){cancelDrag();clearAnnotations();setPromotion([])}}}>
      {Array.from(ranks).flatMap((rank, ri) => Array.from(files).map((file, fi) => {
        const square = file + rank
        const piece = board.get(square as Square)
        const lit = lastMove?.slice(0,2) === square || lastMove?.slice(2,4) === square
        return <button key={square} type="button" data-square={square} aria-label={`${square}${piece ? ` ${names[piece.type]} ${piece.color === 'w' ? 'bianco' : 'nero'}` : ''}`} aria-pressed={selected === square}
          className={`square ${(ri+fi)%2 ? 'dark-square' : 'light-square'} ${selected === square ? 'selected-square' : ''} ${lit ? 'last-square' : ''} ${drag?.from===square?'drag-origin':''} ${interactive&&!promotion.length&&legalMoves.some(m=>m.startsWith(square))?'can-drag':''}`}
          draggable={false} onDragStart={event=>event.preventDefault()}
          onPointerDown={event=>pointerDown(event,square)} onPointerMove={pointerMove} onPointerUp={pointerUp}
          onPointerCancel={event=>{if(gesture.current?.id===event.pointerId)cancelDrag();if(drawing.current?.id===event.pointerId)cancelDrawing()}}
          onLostPointerCapture={event=>{if(gesture.current?.id===event.pointerId)cancelDrag();if(drawing.current?.id===event.pointerId)cancelDrawing()}}
          onClick={event=>{clearAnnotations();if(suppressClick.current&&event.detail!==0){suppressClick.current=false;return}click(square)}}>
          {fi === 0 && <span className="rank-label">{rank}</span>}
          {ri === 7 && <span className="file-label">{file}</span>}
          {piece && <Piece key={piece.color+piece.type} code={piece.color+piece.type}/>}
          {targets.includes(square) && <span className={piece ? 'capture-ring' : 'move-dot'} aria-hidden="true"/>}
        </button>
      }))}
      <svg className="board-annotations" viewBox="0 0 800 800" aria-hidden="true">
        {annotations.map(a=><BoardAnnotation key={a.from+a.to} {...a} orientation={orientation}/>)}
        {preview&&<BoardAnnotation {...preview} orientation={orientation} preview/>}
      </svg>
    </div>
    {drag&&<div className="dragged-piece" aria-hidden="true" style={{left:drag.x,top:drag.y,width:drag.size,height:drag.size,fontSize:drag.size*.82}}><Piece code={drag.code}/></div>}
    {promotion.length > 0 && <div className="promotion" role="dialog" aria-label="Scegli la promozione">
      <p>Promuovi il pedone</p><div className="row">{promotion.map(move => <button key={move} onClick={() => {setPromotion([]); setSelected(null); if(interactive&&legalMoves.includes(move))onMove(move)}}>{names[move[4]]}</button>)}<button onClick={()=>{setPromotion([]);setSelected(null)}}>Annulla</button></div>
    </div>}
  </div>
}
