import {useEffect,useState} from 'react'
import {Chess} from 'chess.js'
import {api} from './api'
import InfoNote from './InfoNote'
import {gameAccuracy} from './accuracy'
import {evaluationSeries} from './evaluationSeries'
import {calibrationInfo,performanceFromAccuracies} from './performance'
import type {Game} from './types'
import type {Saved} from './GameArchive'

const RECENT=10
const standard=new Chess().fen()

/** The player's accuracy in an analysed game from the standard start, as the calibration games were; else null. */
export function playerAccuracy(game:Game){
  if(game.initialFen!==standard||game.drill)return null
  const assisted=new Set(game.assistedPlies??[])
  const own=game.moves.filter((_,ply)=>(ply%2===0)===(game.playerColor==='w')&&!assisted.has(ply)).length
  if(own<calibrationInfo.minMoves)return null
  return gameAccuracy(game,evaluationSeries(game).points,assisted)[game.playerColor]
}

export default function PerformanceProgress(){
  const [accuracies,setAccuracies]=useState<number[]|null>(null),[error,setError]=useState('')
  useEffect(()=>{
    let stale=false
    ;(async()=>{
      // Newest first: analysed games against Maia, read one by one until RECENT qualify.
      const candidates=(await api<Saved[]>('/games')).filter(g=>g.source==='maia'&&g.quality)
      const found:number[]=[]
      for(const saved of candidates){
        if(stale||found.length>=RECENT)break
        const value=playerAccuracy(await api<Game>('/games/'+saved.id))
        if(value!==null)found.push(value)
      }
      if(!stale)setAccuracies(found)
    })().catch(e=>{if(!stale)setError(e instanceof Error?e.message:'Caricamento non riuscito')})
    return()=>{stale=true}
  },[])
  const estimate=accuracies?performanceFromAccuracies(accuracies):null
  const mean=accuracies?.length?accuracies.reduce((a,b)=>a+b,0)/accuracies.length:null
  const tenGames=calibrationInfo.validation.find(v=>v.games===10)
  return <section className="panel performance-progress" aria-label="Prestazione stimata"><span className="eyebrow">CONTRO MAIA</span><h2>Prestazione stimata</h2>
    {error&&<p role="alert">{error}</p>}{!accuracies&&!error&&<p>Caricamento…</p>}
    {accuracies&&!estimate&&<p>Nessuna partita analizzata contro Maia dalla posizione iniziale, con almeno {calibrationInfo.minMoves} mosse tue.</p>}
    {estimate&&<>
      <p className="performance-value"><b>≈ {estimate.rating}</b><span>plausibile {estimate.low}–{estimate.high}</span></p>
      <p>{estimate.games===1?'Sull’unica partita analizzata':`Sulle ultime ${estimate.games} partite analizzate`} contro Maia, precisione media {Math.round(mean!)}%.{estimate.games<RECENT&&` Con ${RECENT} partite l’intervallo si restringe.`}</p>
    </>}
    <InfoNote summary="Come si calcola e quanto è affidabile"><p>Per ogni livello Lichess fra 600 e 2600 (partite rapid e classical) è noto quanto spesso si ottiene ciascuna precisione: lo abbiamo misurato su {calibrationInfo.games.toLocaleString('it-IT')} partite analizzate ({calibrationInfo.source}). La stima cerca il livello che spiega meglio le tue precisioni, partendo con tutti i livelli ugualmente possibili, e combina le partite.</p>
      <p>Sui giocatori tenuti da parte per la verifica{tenGames?.players?`, con 10 partite l’intervallo ha contenuto il rating vero nel ${Math.round(100*(tenGames.coverage??0))}% dei casi ed era largo in mediana ${tenGames.medianWidth} punti`:''}. Lo stile personale rende le partite di uno stesso giocatore simili fra loro: per questo l’intervallo si restringe lentamente. È una scala Lichess, non un rating FIDE o chess.com; la nostra analisi Stockfish è meno profonda di quella di Lichess, e le partite contro Maia senza orologio non sono le stesse di una partita a tempo. Escluse le partite da posizioni diverse da quella iniziale, i Drill e le mosse giocate dopo un suggerimento.</p></InfoNote>
  </section>
}
