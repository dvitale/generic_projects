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
  const autoAttempted=useRef(false)
  useEffect(()=>()=>{active.current?.abort()},[])
  useEffect(()=>{
    if(game.result&&!disabled&&!rating&&!autoAttempted.current){
      autoAttempted.current=true
      void estimate()
    }
  },[game.result,disabled,rating])
  async function estimate(){
    const controller=new AbortController()
    active.current=controller
    setBusy(true);setProgress(0);setError('')
    try{
      const plan=await api<Plan>(`/games/${game.id}/rating-positions`)
      if(controller.signal.aborted)return
      if(plan.method!==RATING_METHOD||plan.opponentMode!=='matched-level'||plan.probabilityFloor!==0.001)throw new Error('Il metodo di valutazione è cambiato: ricarica la pagina.')
      if(plan.positions.length<10)throw new Error(game.result
        ? `Partita troppo breve per stimare il livello: ${plan.positions.length} tue decisioni non obbligate, ne servono almeno 10.`
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
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Stima non riuscita')}
    finally{if(!controller.signal.aborted)setBusy(false)}
  }
  function cancel(){active.current?.abort();setBusy(false);setProgress(0)}
  return <section className="panel rating-panel" aria-label="Valutazione Elo della partita">
    {game.result&&<p className="rating-outcome"><strong>{game.result==='1/2-1/2'?'Partita patta':game.result===(game.playerColor==='w'?'1-0':'0-1')?'Hai vinto':'Hai perso'} · {game.result}</strong></p>}
    <span className="eyebrow">IL LIVELLO DI QUESTA PARTITA</span><h2>Elo indicativo · metodo Maia</h2>
    <p className="muted">Il livello Maia che meglio descrive le tue mosse, con il criterio usato nei Drill del sito ufficiale.</p>
    {rating&&<div className="rating-result" role="status">
      {rating.estimate===null?<h3>Più livelli a pari punteggio</h3>:<h3 className="rating-value">≈ {rating.estimate} <small>profilo Maia più compatibile</small></h3>}
      <p>{rating.positions} tue decisioni confrontate con 21 livelli, a passi di 100 punti.</p>
      <p className="footnote">Scala di riferimento Maia/Lichess, non un rating FIDE o Chess.com. Indica lo stile più compatibile con questa partita; una singola partita non misura stabilmente la tua forza. {rating.boundary&&'Il risultato raggiunge il limite dei livelli confrontati.'}</p>
      <details><summary>Come si confrontano i livelli</summary><p className="footnote">Le tre migliori corrispondenze, ordinate dalla probabilità delle tue mosse. Valori vicini indicano che il punteggio può cambiare facilmente. Queste percentuali non sono la probabilità che tu abbia quel rating.</p><table><thead><tr><th>Livello</th><th>Probabilità delle mosse*</th></tr></thead><tbody>{[...(rating.comparisons||[])].sort((a,b)=>b.meanLogLikelihood-a.meanLogLikelihood).slice(0,3).map(c=><tr key={c.level}><td>{c.level}</td><td>{(c.geometricMoveProbability*100).toFixed(2)}%</td></tr>)}</tbody></table><p className="footnote">* Media geometrica delle probabilità, con lo stesso limite minimo del sito Maia. Non aggiungiamo una fascia ±150: sul sito è fissa, non ricavata dalla partita.</p></details>
      <small className="footnote">{new Date(rating.createdAt).toLocaleString('it-IT')} · salvata con questa partita</small>
    </div>}
    {busy?<div role="status"><p>Confronto delle tue mosse… {progress}%</p><progress value={progress} max={100}/><button className="full" onClick={cancel}>Interrompi stima</button></div>:<button className="full" disabled={disabled||!game.version} onClick={estimate}>{rating?'Ricalcola stima Elo':'Stima Elo della partita'}</button>}
    {error&&<p className="alert" role="alert">{error}</p>}
    <p className="footnote">Calcolo locale su tutte le tue decisioni non obbligate, almeno 10. Nei Drill escludiamo la sequenza iniziale. Dopo una nuova mossa o un annullamento il punteggio va ricalcolato.</p>
  </section>
}
