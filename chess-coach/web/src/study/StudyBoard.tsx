import Board,{type AnalysisArrow} from '../Board'
import {useBoardOrientation} from '../boardFlip'
import type {Color} from '../types'

/** Board for the study panels: read-only unless a move handler and legal moves are given. */
export default function StudyBoard({fen,side,arrows=[],legalMoves=[],onMove,caption,lastMove}:{fen:string;side:Color;arrows?:AnalysisArrow[];legalMoves?:string[];onMove?:(uci:string)=>void;caption?:string;lastMove?:string}){
  const orientation=useBoardOrientation(side)
  return <section className="board-column">
    <Board fen={fen} orientation={orientation} interactive={!!onMove&&legalMoves.length>0} legalMoves={legalMoves} onMove={move=>onMove?.(move)} analysisArrows={arrows} lastMove={lastMove}/>
    {caption&&<p className="footnote">{caption}</p>}
  </section>
}

export const opposite=(color:Color):Color=>color==='w'?'b':'w'
