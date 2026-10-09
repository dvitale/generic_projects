import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { maia } from './engine/maia'
import type { Game, Rating } from './types'

const RATING_METHOD='maia3-drill-match-v2'
interface Plan { version:number; revision:number; positions:{fen:string;move:string;ply:number}[]; levels:number[]; method:string; probabilityFloor:number; opponentMode:string }

export default function RatingPanel({game,disabled,onRated}:{game:Game;disabled:boolean;onRated:(rating:Rating)=>void}) {
  const [rating,setRating]=useState<Rating|null>(game.rating?.method===RATING_METHOD?game.rating:null)
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
      if(plan.method!==RATING_METHOD||plan.opponentMode!=='matched-level'||plan.probabilityFloor!==0.001)throw new Error('Il metodo di valutazione è cambiato: ricarica la pagina.')
      if(plan.positions.length<10)throw new Error(game.result
        ? `Partita troppo breve per confrontare i profili Maia: ${plan.positions.length} tue decisioni non obbligate, ne servono almeno 10.`
        : 'Servono almeno 10 tue decisioni non obbligate. Continua la partita e riprova.')
      const scores=plan.levels.map(()=>0)
      let completed=0
      for(const position of plan.positions){
        for(let i=0;i<plan.levels.length;i++){
          if(controller.signal.aborted)return
          // Match the official drill comparison: both conditioning ratings vary together.
          const prediction=await maia.predict(position.fen,plan.levels[i],plan.levels[i],controller.signal)
          if(controller.signal.aborted)return
          const probability=prediction.moves.find(m=>m.uci===position.move)?.probability
          if(probability===undefined||!Number.isFinite(probability))throw new Error('Maia non ha restituito una probabilità valida. Riprova.')
          scores[i]+=Math.log(Math.max(probability,plan.probabilityFloor))
          setProgress(Math.round(++completed/(plan.positions.length*plan.levels.length)*100))
        }
      }
      const result=await api<Rating>(`/games/${game.id}/rating`,{version:plan.version,revision:plan.revision,method:RATING_METHOD,log_scores:scores})
      if(!controller.signal.aborted){setRating(result);onRated(result)}
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Confronto non riuscito')}
    finally{if(!controller.signal.aborted)setBusy(false)}
  }
  function cancel(){active.current?.abort();setBusy(false);setProgress(0)}
  return <section className="panel rating-panel" aria-label="Somiglianza con Maia">
    <span className="eyebrow">CONFRONTO FACOLTATIVO</span><h3>Somiglianza delle mosse con Maia</h3>
    <p className="muted">Confronta quanto sono probabili le tue mosse ai diversi livelli Maia. Non misura la qualità della partita, il tuo Elo o i progressi: un valore più alto non significa aver giocato meglio.</p>
    {rating&&<div className="rating-result" role="status">
      {rating.estimate===null?<h3>Più livelli a pari punteggio</h3>:<p><strong>Profilo Maia {rating.estimate}</strong> · corrispondenza più alta fra i livelli confrontati</p>}
      <p>{rating.positions} tue decisioni confrontate con 21 livelli, a passi di 100 punti.</p>
      <p className="footnote">Scala di riferimento Maia/Lichess, non un rating FIDE o Chess.com. Indica lo stile più compatibile con questa partita; una singola partita non misura stabilmente la tua forza. {rating.boundary&&'Il risultato raggiunge il limite dei livelli confrontati.'}</p>
      <details><summary>Come si confrontano i livelli</summary><p className="footnote">Le tre migliori corrispondenze, ordinate dalla probabilità delle tue mosse. Valori vicini indicano che il punteggio può cambiare facilmente. Queste percentuali non sono la probabilità che tu abbia quel rating.</p><table><thead><tr><th>Livello</th><th>Probabilità delle mosse*</th></tr></thead><tbody>{[...(rating.comparisons||[])].sort((a,b)=>b.meanLogLikelihood-a.meanLogLikelihood).slice(0,3).map(c=><tr key={c.level}><td>{c.level}</td><td>{(c.geometricMoveProbability*100).toFixed(2)}%</td></tr>)}</tbody></table><p className="footnote">* Media geometrica delle probabilità, con lo stesso limite minimo del sito Maia. Non aggiungiamo una fascia ±150: sul sito è fissa, non ricavata dalla partita.</p></details>
      <small className="footnote">{new Date(rating.createdAt).toLocaleString('it-IT')} · salvata con questa partita</small>
    </div>}
    {busy?<div role="status"><p>Confronto delle tue mosse… {progress}%</p><progress value={progress} max={100}/><button className="full" onClick={cancel}>Interrompi confronto</button></div>:<button className="full" disabled={disabled||!game.version} onClick={estimate}>{rating?'Ricalcola somiglianza':'Confronta con i profili Maia'}</button>}
    {error&&<p className="alert" role="alert">{error}</p>}
    <p className="footnote">Calcolo locale su tutte le tue decisioni non obbligate, almeno 10. Nei Drill escludiamo la sequenza iniziale. Dopo una nuova mossa o un annullamento il punteggio va ricalcolato.</p>
  </section>
}
