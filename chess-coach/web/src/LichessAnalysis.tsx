import {useMemo,useState} from 'react'
import {Chess} from 'chess.js'
import type {Color,Game} from './types'

type History=Pick<Game,'initialFen'|'moves'>
export function lichessTarget(fen:string,orientation:Color,game?:History|null,ply?:number){
  const color=orientation==='w'?'white':'black'
  const positionUrl=`https://lichess.org/analysis/standard/${fen.trim().split(/\s+/).map(encodeURIComponent).join('_').replaceAll('%2F','/')}?color=${color}`
  if(!game?.moves.length)return {url:positionUrl,mode:'position' as const,pgn:''}
  try{
    const board=new Chess(game.initialFen)
    const start=board.fen().split(' ')
    const startPly=(Number(start[5])-1)*2+(start[1]==='b'?1:0)
    const selected=ply??game.moves.length
    if(!Number.isInteger(selected)||selected<0||selected>game.moves.length)throw new Error('Invalid cursor')
    let selectedFen=board.fen()
    const sans:string[]=[]
    for(const [i,uci] of game.moves.entries()){
      const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]})
      sans.push(move.san)
      if(i+1===selected)selectedFen=board.fen()
    }
    if(selectedFen!==new Chess(fen).fen())throw new Error('Different displayed position')
    // Only chess data: omit player names, clocks and private PGN comments.
    // Lichess normalizes '+' to spaces; SAN check suffixes are optional.
    const headers=game.initialFen===new Chess().fen()?'':`[SetUp "1"]\n[FEN "${game.initialFen}"]\n\n`
    const pgn=headers+sans.join(' ').replaceAll('+','')+' *'
    const encoded=encodeURIComponent(pgn)
    // Lichess limits the PGN URL path to 5000 characters before decoding.
    if(encoded.length>5000)return {url:`https://lichess.org/analysis?color=${color}`,mode:'manual' as const,pgn:board.pgn()}
    return {url:`https://lichess.org/analysis/pgn/${encoded}?color=${color}#${startPly+selected}`,mode:'game' as const,pgn}
  }catch{
    return {url:positionUrl,mode:'unavailable' as const,pgn:''}
  }
}

export default function LichessAnalysis({fen,orientation,game,ply}:{fen:string;orientation:Color;game?:History|null;ply?:number}){
  const [openedUrl,setOpenedUrl]=useState('')
  const [copyStatus,setCopyStatus]=useState('')
  const target=useMemo(()=>lichessTarget(fen,orientation,game,ply),[fen,orientation,game,ply])
  function open(){
    // Open synchronously from the click, preserving browser popup activation.
    setOpenedUrl(target.url)
    window.open(target.url,'_blank','popup=yes,width=1100,height=850,resizable=yes,scrollbars=yes,noopener,noreferrer')
  }
  async function copy(){
    try{await navigator.clipboard.writeText(target.pgn);setCopyStatus('PGN copiato: incollalo nel campo PGN di Lichess e premi Importa PGN.')}
    catch{setCopyStatus('Seleziona e copia il PGN dal campo qui sotto.')}
  }
  return <div className="lichess-analysis">
    <button onClick={open} title={target.mode==='game'?'Apri tutte le mosse su Lichess, dalla posizione mostrata':'Apri l’analisi in una nuova finestra su lichess.org'}>Analizza con Lichess ↗</button>
    {target.mode==='game'&&<small>Intera partita navigabile · apertura sulla posizione mostrata.</small>}
    {target.mode==='position'&&<small>Posizione singola: nessuna cronologia disponibile.</small>}
    {target.mode==='unavailable'&&<small>La posizione mostrata non coincide con la cronologia: verrà aperta solo la posizione.</small>}
    {target.mode==='manual'&&<><small>La partita supera il limite del collegamento Lichess. Copia il PGN completo e importalo nella finestra di analisi.</small><button onClick={()=>void copy()}>Copia PGN per Lichess</button><textarea aria-label="PGN completo per Lichess" readOnly value={target.pgn}/>{copyStatus&&<small role="status">{copyStatus}</small>}</>}
    {openedUrl&&<small>Se la finestra non si apre, <a href={openedUrl} target="_blank" rel="noopener noreferrer">apri Lichess in una nuova scheda</a>.</small>}
  </div>
}
