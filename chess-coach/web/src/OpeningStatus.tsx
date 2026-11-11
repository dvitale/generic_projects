import {useMemo} from 'react'
import {Chess} from 'chess.js'
import type {Game} from './types'

/** Opening name and book exit at a ply, from the Lichess catalogue as in Play and Review; says who left the book. */
export function openingStatus(game:Game,ply:number){
  const opening=game.opening
  if(!opening)return null
  const book=opening.bookPlies
  const named=opening.positions?.filter(p=>p.ply<=ply).at(-1)??null
  if(ply<=book)return {named,inBook:true as const}
  const board=new Chess(game.initialFen)
  let san=''
  for(let i=0;i<book;i++){const m=game.moves[i];san=board.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]}).san}
  const number=board.moveNumber(),exitColor=board.turn()
  // The book move label is the last move still on a catalogue line; the next one, by exitColor, left the book.
  const last=book>0?`${exitColor==='w'?number-1:number}${exitColor==='w'?'…':'.'} ${san}`:'la posizione iniziale'
  return {named,inBook:false as const,last,byPlayer:exitColor===game.playerColor,exitPly:book}
}

export default function OpeningStatus({game,ply,engine='Maia'}:{game:Game;ply:number;engine?:string}){
  // Book exits inside the preset line of a drill were not chosen by anyone in the drill.
  const preset=game.drill?.startPly??0
  const status=useMemo(()=>openingStatus(game,ply),[game.id,game.version,game.opening,ply])
  if(!status)return null
  return <p className={`opening-status${status.inBook?' in-book':' out-of-book'}`} role="status" title="Catalogo delle aperture di Lichess: un elenco di nomi, non un libro completo. L’uscita è un’indicazione, non un errore.">
    {status.named&&<span><b>{status.named.eco}</b> {status.named.name}</span>}
    <small>{status.inBook?'In teoria':`Fuori teoria dopo ${status.last} · ${status.exitPly<preset?'già nella linea scelta':status.byPlayer?'ne sei uscito tu':`ne è uscito ${engine}`}`}</small>
  </p>
}
