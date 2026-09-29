import {useEffect,useMemo,useRef} from 'react'
import {Chess} from 'chess.js'
import type {Game} from './types'

export default function MoveHistory({game,ply,onPosition,onReview,reviewDisabled}:{game:Game;ply:number;onPosition:(ply:number)=>void;onReview:()=>void;reviewDisabled:boolean}) {
  const list=useRef<HTMLDivElement>(null)
  const rows=useMemo(()=>{
    const board=new Chess(game.initialFen)
    const result:{number:number;w?:{san:string;ply:number};b?:{san:string;ply:number}}[]=[]
    game.moves.forEach((uci,index)=>{
      const number=Number(board.fen().split(' ')[5])
      const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]})
      if(result.at(-1)?.number!==number)result.push({number})
      result[result.length-1][move.color]={san:move.san,ply:index+1}
    })
    return result
  },[game.initialFen,game.moves])
  useEffect(()=>{
    const container=list.current,active=container?.querySelector<HTMLElement>('[aria-current="step"]')
    if(!container)return
    if(!active){if(ply===0)container.scrollTop=0;return}
    const item=active.getBoundingClientRect(),box=container.getBoundingClientRect()
    if(item.top<box.top)container.scrollTop+=item.top-box.top
    else if(item.bottom>box.bottom)container.scrollTop+=item.bottom-box.bottom
  },[ply,game.version])
  const last=game.moves.length
  return <section className="panel move-history" aria-label="Mosse della partita" onKeyDown={event=>{
    const target=event.key==='ArrowLeft'?Math.max(0,ply-1):event.key==='ArrowRight'?Math.min(last,ply+1):event.key==='Home'?0:event.key==='End'?last:null
    if(target!==null){event.preventDefault();onPosition(target)}
  }}>
    <h2>Mosse della partita</h2>
    <p className="muted">Seleziona una mossa per rivedere la posizione.</p>
    <div className="move-history-list" ref={list}>
      {rows.length?rows.map(row=><div className="move-history-row" key={row.number}><span>{row.number}.</span>{(['w','b'] as const).map(color=>{
        const move=row[color]
        return move?<button key={color} aria-label={`${row.number}${color==='w'?'.':'…'} ${move.san}`} aria-current={ply===move.ply?'step':undefined} onClick={()=>onPosition(move.ply)}>{move.san}</button>:<span key={color}>—</span>
      })}</div>):<p className="empty-text">Le mosse appariranno qui.</p>}
    </div>
    <div className="review-controls" aria-label="Navigazione della partita">
      <button aria-label="Posizione iniziale" disabled={ply===0} onClick={()=>onPosition(0)}>⏮</button>
      <button aria-label="Mossa precedente" disabled={ply===0} onClick={()=>onPosition(ply-1)}>←</button>
      <span>{ply} / {last}</span>
      <button aria-label="Mossa successiva" disabled={ply===last} onClick={()=>onPosition(ply+1)}>→</button>
      <button aria-label="Posizione corrente" disabled={ply===last} onClick={()=>onPosition(last)}>⏭</button>
    </div>
    <p className="footnote">Puoi usare anche ← e → dopo aver selezionato una mossa.</p>
    <button className="full" disabled={reviewDisabled} onClick={onReview}>Rivedi questa partita</button>
  </section>
}
