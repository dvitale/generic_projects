import type {Color} from './types'
import {useBoardSettings} from './boardSettings'

/** Static, non-interactive thumbnail of a FEN position. */
export default function MiniBoard({fen,orientation='w'}:{fen:string;orientation?:Color}){
  const {theme}=useBoardSettings()
  const rows=fen.split(' ')[0].split('/').map(row=>row.replace(/\d/g,n=>'.'.repeat(Number(n))).split(''))
  const squares=rows.flatMap((row,r)=>row.map((piece,f)=>({piece,dark:(r+f)%2===1})))
  if(orientation==='b')squares.reverse()
  return <div className={`mini-board board-theme-${theme}`} aria-hidden="true">
    {squares.map((s,i)=><span key={i} className={s.dark?'mini-dark':'mini-light'}>{s.piece!=='.'&&<img src={`/pieces/neo/${s.piece===s.piece.toUpperCase()?'w':'b'}${s.piece.toLowerCase()}.png`} alt="" draggable={false}/>}</span>)}
  </div>
}
