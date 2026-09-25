import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { maia } from './engine/maia'
import type { Game, Rating } from './types'

interface Plan { version:number; revision:number; positions:{fen:string;move:string;ply:number}[]; levels:number[]; opponentElo:number }

export default function RatingPanel({game,disabled,onRated}:{game:Game;disabled:boolean;onRated:(rating:Rating)=>void}) {
  const [rating,setRating]=useState<Rating|null>(game.rating)
  const [busy,setBusy]=useState(false)
  const [progress,setProgress]=useState(0)
  const [error,setError]=useState('')
  const active=useRef<AbortController|null>(null)
  useEffect(()=>()=>{active.current?.abort()},[])
  async function estimate(){
    const controller=new AbortController()
    active.current=controller
    setBusy(true);setProgress(0);setError('')
    try{
      const plan=await api<Plan>(`/games/${game.id}/rating-positions`)
      if(controller.signal.aborted)return
      if(plan.positions.length<10)throw new Error('Servono almeno 10 tue decisioni non obbligate. Continua la partita e riprova.')
      const scores=plan.levels.map(()=>0)
      let completed=0
      for(const position of plan.positions){
        for(let i=0;i<plan.levels.length;i++){
          if(controller.signal.aborted)return
          const prediction=await maia.predict(position.fen,plan.levels[i],plan.opponentElo)
          if(controller.signal.aborted)return
          const probability=prediction.moves.find(m=>m.uci===position.move)?.probability
          if(probability===undefined||!Number.isFinite(probability))throw new Error('Maia non ha restituito una probabilità valida. Riprova.')
          scores[i]+=Math.log(Math.max(probability,1e-12))
          setProgress(Math.round(++completed/(plan.positions.length*plan.levels.length)*100))
        }
      }
      const result=await api<Rating>(`/games/${game.id}/rating`,{version:plan.version,revision:plan.revision,log_scores:scores})
      if(!controller.signal.aborted){setRating(result);onRated(result)}
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Stima non riuscita')}
    finally{if(!controller.signal.aborted)setBusy(false)}
  }
  function cancel(){active.current?.abort();setBusy(false);setProgress(0)}
  return <section className="panel rating-panel" aria-label="Valutazione Elo della partita">
    <span className="eyebrow">IL LIVELLO DI QUESTA PARTITA</span><h2>Elo stimato</h2>
    <p className="muted">Confrontiamo le tue scelte con Maia a diversi livelli. È una stima sperimentale dello stile di gioco, non un rating ufficiale o una misura certificata della tua forza.</p>
    {rating&&<div className="rating-result" role="status">
      {rating.estimate===null?<h3>Livello non distinguibile</h3>:<h3 className="rating-value">{rating.estimate} <small>Elo indicativo</small></h3>}
      <p>{rating.estimate===null?'Le tue mosse non distinguono abbastanza i livelli Maia. ':''}Fascia compatibile: <strong>{rating.low}–{rating.high}</strong>.</p>
      <p className="footnote">{rating.positions} tue decisioni confrontate su {rating.totalPositions}. {rating.opponentAssumed?`Per il PGN assumiamo un avversario di ${rating.opponentElo} Elo.`:`Avversario Maia: ${rating.opponentElo}.`} La fascia esprime compatibilità con il modello, non un intervallo di confidenza. {rating.boundary&&'Il risultato raggiunge il limite dei livelli confrontati.'}</p>
      <small className="footnote">{new Date(rating.createdAt).toLocaleString('it-IT')} · salvata con questa partita</small>
    </div>}
    {busy?<div role="status"><p>Confronto delle tue mosse… {progress}%</p><progress value={progress} max={100}/><button className="full" onClick={cancel}>Interrompi stima</button></div>:<button className="full" disabled={disabled||!game.version} onClick={estimate}>{rating?'Ricalcola stima Elo':'Stima Elo della partita'}</button>}
    {error&&<p className="alert" role="alert">{error}</p>}
    <p className="footnote">Calcolo locale con Maia: almeno 10 decisioni, fino a 40 posizioni distribuite nella partita. Nei Drill escludiamo la sequenza iniziale. Dopo una nuova mossa o un annullamento la stima va ricalcolata.</p>
  </section>
}
