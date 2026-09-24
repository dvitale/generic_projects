import { useEffect, useState } from 'react'
import { Chess, type Square } from 'chess.js'
import type { Color } from './types'

const symbols: Record<string, string> = {wk:'♚',wq:'♛',wr:'♜',wb:'♝',wn:'♞',wp:'♟',bk:'♚',bq:'♛',br:'♜',bb:'♝',bn:'♞',bp:'♟'}
const names: Record<string, string> = {k:'re',q:'donna',r:'torre',b:'alfiere',n:'cavallo',p:'pedone'}
export default function Board({fen, orientation, interactive, legalMoves, onMove, lastMove}: {fen:string; orientation:Color; interactive:boolean; legalMoves:string[]; onMove:(uci:string)=>void; lastMove?:string}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [promotion, setPromotion] = useState<string[]>([])
  useEffect(() => { setSelected(null); setPromotion([]) }, [fen])
  const board = new Chess(fen)
  const files = orientation === 'w' ? 'abcdefgh' : 'hgfedcba'
  const ranks = orientation === 'w' ? '87654321' : '12345678'
  const targets = selected ? legalMoves.filter(m => m.startsWith(selected)).map(m => m.slice(2,4)) : []
  function click(square: string) {
    if (!interactive) return
    if (selected) {
      const candidates = legalMoves.filter(m => m.startsWith(selected + square))
      if (candidates.length > 1) { setPromotion(candidates); return }
      if (candidates.length === 1) { setSelected(null); onMove(candidates[0]); return }
    }
    setSelected(legalMoves.some(m => m.startsWith(square)) ? square : null)
  }
  return <div className="board-wrap">
    <div className="board" role="group" aria-label="Scacchiera">
      {Array.from(ranks).flatMap((rank, ri) => Array.from(files).map((file, fi) => {
        const square = file + rank
        const piece = board.get(square as Square)
        const lit = lastMove?.slice(0,2) === square || lastMove?.slice(2,4) === square
        return <button key={square} type="button" data-square={square} aria-label={`${square}${piece ? ` ${names[piece.type]} ${piece.color === 'w' ? 'bianco' : 'nero'}` : ''}`} aria-pressed={selected === square}
          className={`square ${(ri+fi)%2 ? 'dark-square' : 'light-square'} ${selected === square ? 'selected-square' : ''} ${lit ? 'last-square' : ''}`} onClick={() => click(square)}>
          {fi === 0 && <span className="rank-label">{rank}</span>}
          {ri === 7 && <span className="file-label">{file}</span>}
          {piece && <span aria-hidden="true" className={`piece ${piece.color === 'w' ? 'white-piece' : 'black-piece'}`}>{symbols[piece.color + piece.type]}</span>}
          {targets.includes(square) && <span className={piece ? 'capture-ring' : 'move-dot'} aria-hidden="true"/>}
        </button>
      }))}
    </div>
    {promotion.length > 0 && <div className="promotion" role="dialog" aria-label="Scegli la promozione">
      <p>Promuovi il pedone</p><div className="row">{promotion.map(move => <button key={move} onClick={() => {setPromotion([]); onMove(move)}}>{names[move[4]]}</button>)}<button onClick={()=>setPromotion([])}>Annulla</button></div>
    </div>}
  </div>
}
