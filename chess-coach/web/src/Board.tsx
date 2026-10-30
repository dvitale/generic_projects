import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { Chess, type Square } from 'chess.js'
import type { Color } from './types'
import {useBoardSettings} from './boardSettings'
import {playMoveSound} from './sound'
import {moveClassInfo,type MoveClass} from './moveClass'

const symbols: Record<string, string> = {wk:'♚',wq:'♛',wr:'♜',wb:'♝',wn:'♞',wp:'♟',bk:'♚',bq:'♛',br:'♜',bb:'♝',bn:'♞',bp:'♟'}
const names: Record<string, string> = {k:'re',q:'donna',r:'torre',b:'alfiere',n:'cavallo',p:'pedone'}
type Gesture = {id:number;from:string;startX:number;startY:number;fen:string;orientation:Color;code:string;size:number;active:boolean;element:HTMLButtonElement}
type Annotation = {from:string;to:string}
type Drawing = {id:number;from:string;fen:string;orientation:Color;element:HTMLButtonElement}
export type AnalysisArrow = {move:string;source:'stockfish'|'maia'|'played'|'solution';rank:number}

function squareCenter(square:string,orientation:Color){
    const file=square.charCodeAt(0)-97,rank=Number(square[1])-1
    return [(orientation==='w'?file:7-file)*100+50,(orientation==='w'?7-rank:rank)*100+50]
}
// Arrow geometry and brushes follow chessground, the board used by maiachess.com:
// widths in 64ths of a square, round caps, marker heads, a 60% shapes layer.
type Brush={key:string;color:string;opacity:number;width:number}
const brushes:Record<string,Brush>={
  annotation:{key:'g',color:'#15781B',opacity:1,width:10},
  stockfish:{key:'b',color:'#003088',opacity:1,width:8},
  maia:{key:'r',color:'#882020',opacity:1,width:10},
  // The move that solved a puzzle: green, never Maia's red, even when Maia would play it too.
  solution:{key:'s',color:'#2f8f46',opacity:1,width:10},
  playedOutline:{key:'po',color:'#4A8FB3',opacity:.95,width:11},
  played:{key:'pw',color:'#FFFFFF',opacity:.98,width:8},
}
const unit=100/64
function ArrowMarkers(){
  return <defs>{Object.values(brushes).map(b=><marker key={b.key} id={'arrowhead-'+b.key} orient="auto" markerWidth="4" markerHeight="8" refX="2.05" refY="2.01"><path d="M0,0 V4 L3,2 Z" fill={b.color}/></marker>)}</defs>
}
function BoardAnnotation({from,to,orientation,brush=brushes.annotation,extra=0,shorten=false,preview=false,automatic=false}:Annotation&{orientation:Color;brush?:Brush;extra?:number;shorten?:boolean;preview?:boolean;automatic?:boolean}) {
  const [x1,y1]=squareCenter(from,orientation),[x2,y2]=squareCenter(to,orientation)
  const attributes={'data-from':from,'data-to':to,className:automatic?'analysis-arrow-shape':preview?'annotation-preview':'board-annotation',opacity:brush.opacity*(preview?.9:1)}
  if(from===to)return <circle {...attributes} cx={x1} cy={y1} r={50-(preview?3:4)*unit/2} fill="none" stroke={brush.color} strokeWidth={(preview?3:4)*unit}/>
  const margin=(shorten&&!preview?20:10)*unit
  const stroke={stroke:brush.color,strokeWidth:(brush.width+extra)*unit*(preview?.85:1),strokeLinecap:'round' as const,markerEnd:`url(#arrowhead-${brush.key})`}
  const horizontal=Math.abs(x2-x1),vertical=Math.abs(y2-y1)
  if((horizontal===100&&vertical===200)||(horizontal===200&&vertical===100)){
    // Knight: follow the two-square leg first, then turn toward the destination.
    const bendX=horizontal===200?x2:x1,bendY=vertical===200?y2:y1
    const dx=Math.sign(x2-bendX),dy=Math.sign(y2-bendY)
    return <path {...attributes} d={`M ${x1} ${y1} L ${bendX} ${bendY} L ${x2-dx*margin} ${y2-dy*margin}`} fill="none" strokeLinejoin="miter" strokeMiterlimit={4} {...stroke}/>
  }
  const angle=Math.atan2(y2-y1,x2-x1)
  return <line {...attributes} x1={x1} y1={y1} x2={x2-Math.cos(angle)*margin} y2={y2-Math.sin(angle)*margin}
    {...stroke}/>
}
// Stacking order as on maiachess.com: Maia, Stockfish, then the played move on top. Arrows of the same
// move from different sources hide each other, so `turn` rotates which one is in the foreground.
const arrowOrder={maia:0,solution:1,stockfish:2,played:3}
const arrowKey=(a:AnalysisArrow)=>a.move.slice(0,4)
const overlapping=(arrows:AnalysisArrow[])=>arrows.some((a,i)=>arrows.some((b,j)=>j>i&&arrowKey(a)===arrowKey(b)&&a.source!==b.source))
function stackArrows(arrows:AnalysisArrow[],turn:number){
  const sorted=[...arrows].sort((a,b)=>b.rank-a.rank||arrowOrder[a.source]-arrowOrder[b.source])
  const groups=new Map<string,AnalysisArrow[]>()
  sorted.forEach(a=>groups.set(arrowKey(a),[...groups.get(arrowKey(a))??[],a]))
  const next=new Map([...groups].map(([key,group])=>[key,group.map((_,i)=>group[(i+turn)%group.length])]))
  return sorted.map(a=>next.get(arrowKey(a))!.shift()!)
}
function Piece({code}:{code:string}) {
  const [missing,setMissing]=useState(false)
  return missing?<span aria-hidden="true" className={`piece ${code[0]==='w'?'white-piece':'black-piece'}`}>{symbols[code]}</span>:
    <img className="piece-image" src={`/pieces/neo/${code}.png`} alt="" aria-hidden="true" draggable={false} onError={()=>setMissing(true)}/>
}
export default function Board({fen, orientation, interactive:enabled, legalMoves, onMove, lastMove, animateMove=false,reverseMove=false,analysisArrows=[],badge,highlights=[]}: {fen:string; orientation:Color; interactive:boolean; legalMoves:string[]; onMove:(uci:string)=>void|Promise<unknown>; lastMove?:string;animateMove?:boolean;reverseMove?:boolean;analysisArrows?:AnalysisArrow[];badge?:{square:string;kind:MoveClass};highlights?:string[]}) {
  const {theme}=useBoardSettings()
  const [selected, setSelected] = useState<string | null>(null)
  const [promotion, setPromotion] = useState<string[]>([])
  const [drag, setDrag] = useState<{from:string;code:string;x:number;y:number;size:number}|null>(null)
  const [annotations,setAnnotations]=useState<Annotation[]>([])
  const [arrowTurn,setArrowTurn]=useState(0)
  const rotating=overlapping(analysisArrows)
  useEffect(()=>{
    setArrowTurn(0)
    if(!rotating)return
    let id=0
    const schedule=()=>{id=window.setTimeout(()=>{setArrowTurn(t=>t+1);schedule()},2000+Math.random()*2000)}
    schedule();return()=>clearTimeout(id)
  },[rotating,analysisArrows.map(a=>a.source+a.move).join()])
  const [preview,setPreview]=useState<Annotation|null>(null)
  const drawing=useRef<Drawing|null>(null)
  const boardElement=useRef<HTMLDivElement>(null)
  const previousFen=useRef(fen)
  const gesture=useRef<Gesture|null>(null)
  const suppressClick=useRef(false)
  // The move just played here stays on the board until the parent has handled it: by then a
  // new position has arrived, or the same position means it was rejected (or repeated).
  const [pending,setPending]=useState<{base:string;move:string;fen:string}|null>(null)
  const dropped=useRef<{base:string;move:string}|null>(null)
  const optimistic=pending?.base===fen?pending:null
  const shownFen=optimistic?.fen??fen,shownLastMove=optimistic?.move??lastMove
  const interactive=enabled&&!optimistic
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
  useEffect(()=>{setPending(null)},[fen,orientation])
  useEffect(()=>{
    const cancel=()=>{cancelDrag();cancelDrawing()}
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')clearAnnotations()}
    window.addEventListener('blur',cancel)
    window.addEventListener('keydown',escape)
    return()=>{window.removeEventListener('blur',cancel);window.removeEventListener('keydown',escape);gesture.current=null;drawing.current=null}
  },[])
  const board = new Chess(shownFen)
  const files = orientation === 'w' ? 'abcdefgh' : 'hgfedcba'
  const ranks = orientation === 'w' ? '87654321' : '12345678'
  useLayoutEffect(()=>{
    const previous=previousFen.current,fen=shownFen,lastMove=shownLastMove
    previousFen.current=fen
    const drop=dropped.current
    dropped.current=null
    if(previous===fen||!lastMove)return
    const from=lastMove.slice(0,2),to=lastMove.slice(2,4)
    let castling=false
    try {
      const before=new Chess(reverseMove?fen:previous)
      const moved=before.move({from,to,promotion:lastMove[4]})
      if(before.fen()!==(reverseMove?previous:fen))return
      castling=moved.isKingsideCastle()||moved.isQueensideCastle()
      // Sound only for moves played forward, never for a puzzle resetting.
      if(!reverseMove)playMoveSound(before.inCheck()?'check':moved.captured?'capture':'move')
    }catch{return}
    // A dragged piece is already on its destination: sliding it from the origin looks like a jump back.
    if(!reverseMove&&drop?.base===previous&&drop.move===lastMove)return
    if(!animateMove||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return
    const animations:Animation[]=[]
    function slide(origin:string,destination:string){
      const start=boardElement.current?.querySelector<HTMLElement>(`[data-square="${origin}"]`)
      const end=boardElement.current?.querySelector<HTMLElement>(`[data-square="${destination}"]`)
      const piece=end?.querySelector<HTMLElement>('.piece-image,.piece')
      if(!start||!end||!piece)return
      const a=start.getBoundingClientRect(),b=end.getBoundingClientRect()
      animations.push(piece.animate([{transform:`translate(${a.left-b.left}px,${a.top-b.top}px)`,zIndex:4},{transform:'translate(0,0)',zIndex:4}],{duration:reverseMove?650:260,easing:'cubic-bezier(.2,.65,.3,1)'}))
    }
    slide(reverseMove?to:from,reverseMove?from:to)
    if(castling){
      const rookFrom=(to[0]==='g'?'h':'a')+to[1],rookTo=(to[0]==='g'?'f':'d')+to[1]
      slide(reverseMove?rookTo:rookFrom,reverseMove?rookFrom:rookTo)
    }
    if(reverseMove){
      // Captured pieces (including en passant) reappear after the moving piece returns.
      const before=new Chess(previous),after=new Chess(fen)
      for(const rank of '12345678')for(const file of 'abcdefgh'){
        const square=(file+rank) as Square
        if(square===from||!after.get(square)||before.get(square)?.color===after.get(square)?.color)continue
        const piece=boardElement.current?.querySelector<HTMLElement>(`[data-square="${square}"] .piece-image,[data-square="${square}"] .piece`)
        if(piece)animations.push(piece.animate([{opacity:0,offset:0},{opacity:0,offset:.8},{opacity:1,offset:1}],{duration:650}))
      }
    }
    return()=>animations.forEach(animation=>animation.cancel())
  },[shownFen,orientation,shownLastMove,animateMove,reverseMove])
  const targets = selected ? legalMoves.filter(m => m.startsWith(selected)).map(m => m.slice(2,4)) : []
  function play(move:string,dragged=false){
    let mine:typeof pending=null
    try{
      const next=new Chess(fen)
      next.move({from:move.slice(0,2),to:move.slice(2,4),promotion:move[4]})
      mine={base:fen,move,fen:next.fen()}
      setPending(mine)
      if(dragged)dropped.current={base:fen,move}
    }catch{/* the parent decides on moves the board cannot replay */}
    const done=()=>setPending(current=>current===mine?null:current)
    Promise.resolve(onMove(move)).then(done,done)
  }
  function submit(from:string,to:string,dragged=false) {
      const candidates = legalMoves.filter(m => m.startsWith(from + to))
      if (candidates.length > 1) { setPromotion(candidates); return }
      if (candidates.length === 1) { setSelected(null); play(candidates[0],dragged); return }
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
    if(to)submit(current.from,to,true)
  }
  function squareAtPoint(x:number,y:number){
    const rect=boardElement.current?.getBoundingClientRect()
    if(!rect||x<rect.left||x>=rect.right||y<rect.top||y>=rect.bottom)return null
    return files[Math.floor((x-rect.left)/rect.width*8)]+ranks[Math.floor((y-rect.top)/rect.height*8)]
  }
  return <div className="board-wrap">
    <div ref={boardElement} className={`board board-theme-${theme}`} role="group" aria-label="Scacchiera"
      onContextMenu={event=>event.preventDefault()}
      onKeyDown={event=>{if(event.key==='Escape'){cancelDrag();clearAnnotations();setPromotion([])}}}>
      {Array.from(ranks).flatMap((rank, ri) => Array.from(files).map((file, fi) => {
        const square = file + rank
        const piece = board.get(square as Square)
        const checked = piece?.type==='k' && piece.color===board.turn() && board.inCheck()
        const lit = shownLastMove?.slice(0,2) === square || shownLastMove?.slice(2,4) === square
        return <button key={square} type="button" data-square={square} aria-label={`${square}${piece ? ` ${names[piece.type]} ${piece.color === 'w' ? 'bianco' : 'nero'}` : ''}`} aria-pressed={selected === square}
          className={`square ${(ri+fi)%2 ? 'dark-square' : 'light-square'} ${selected === square ? 'selected-square' : ''} ${lit ? 'last-square' : ''} ${checked ? 'check-square' : ''} ${highlights.includes(square)?'hint-square':''} ${drag?.from===square?'drag-origin':''} ${interactive&&!promotion.length&&legalMoves.some(m=>m.startsWith(square))?'can-drag':''}`}
          draggable={false} onDragStart={event=>event.preventDefault()}
          onPointerDown={event=>pointerDown(event,square)} onPointerMove={pointerMove} onPointerUp={pointerUp}
          onPointerCancel={event=>{if(gesture.current?.id===event.pointerId)cancelDrag();if(drawing.current?.id===event.pointerId)cancelDrawing()}}
          onLostPointerCapture={event=>{if(gesture.current?.id===event.pointerId)cancelDrag();if(drawing.current?.id===event.pointerId)cancelDrawing()}}
          onClick={event=>{clearAnnotations();if(suppressClick.current&&event.detail!==0){suppressClick.current=false;return}click(square)}}>
          {fi === 0 && <span className="rank-label">{rank}</span>}
          {ri === 7 && <span className="file-label">{file}</span>}
          {piece && <Piece key={piece.color+piece.type} code={piece.color+piece.type}/>}
          {targets.includes(square) && <span className={piece ? 'capture-ring' : 'move-dot'} aria-hidden="true"/>}
          {!optimistic&&badge?.square===square&&<span className={`move-badge move-class-${badge.kind}`} title={moveClassInfo[badge.kind].label} aria-hidden="true">{moveClassInfo[badge.kind].symbol}</span>}
        </button>
      }))}
      <svg className="board-annotations" viewBox="0 0 800 800" aria-hidden="true">
        <ArrowMarkers/>
        {(()=>{
          const sorted=stackArrows(optimistic?[]:analysisArrows,arrowTurn)
          const all=[...sorted.map(a=>({from:a.move.slice(0,2),to:a.move.slice(2,4)})),...annotations]
          return sorted.map(arrow=>{
            const from=arrow.move.slice(0,2),to=arrow.move.slice(2,4)
            const same=sorted.filter(a=>a.move.slice(0,4)===arrow.move.slice(0,4))
            const extra=(same.length-same.indexOf(arrow)-1)*1.25
            const shorten=all.some(a=>a.to===to&&a.from!==from)
            const props={from,to,orientation,extra,shorten,automatic:true}
            return <g key={arrow.source+arrow.rank+arrow.move} className={`analysis-arrow source-${arrow.source}`} data-source={arrow.source} data-rank={arrow.rank} data-move={arrow.move} opacity={arrow.rank===1?1:arrow.rank===2?.7:.5}>
              {arrow.source==='played'?<><BoardAnnotation {...props} brush={brushes.playedOutline}/><BoardAnnotation {...props} brush={brushes.played}/></>:<BoardAnnotation {...props} brush={brushes[arrow.source]}/>}
            </g>
          })
        })()}
        {annotations.map(a=><BoardAnnotation key={a.from+a.to} {...a} orientation={orientation} shorten={[...annotations,...(optimistic?[]:analysisArrows).map(x=>({from:x.move.slice(0,2),to:x.move.slice(2,4)}))].some(b=>b.to===a.to&&b.from!==a.from)}/>)}
        {preview&&<BoardAnnotation {...preview} orientation={orientation} preview/>}
      </svg>
    </div>
    {drag&&<div className="dragged-piece" aria-hidden="true" style={{left:drag.x,top:drag.y,width:drag.size,height:drag.size,fontSize:drag.size*.82}}><Piece code={drag.code}/></div>}
    {promotion.length > 0 && <div className={`promotion board-theme-${theme}`} role="dialog" aria-label="Scegli la promozione">
      <p>Promuovi il pedone</p><div className="promotion-choices">{promotion.map(move => <button key={move} className="promotion-piece" aria-label={names[move[4]]} title={names[move[4]]} onClick={() => {setPromotion([]); setSelected(null); if(interactive&&legalMoves.includes(move))play(move)}}><Piece code={board.turn()+move[4]}/></button>)}</div><button className="promotion-cancel" onClick={()=>{setPromotion([]);setSelected(null)}}>Annulla</button>
    </div>}
  </div>
}
