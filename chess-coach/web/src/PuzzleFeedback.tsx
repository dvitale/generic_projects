import { useEffect, useRef } from 'react'
import type { Attempt } from './types'

export default function PuzzleFeedback({attempt,busy,ready,hasNext,onNext,onRestart,motionMessage,comparing,canRestart=true}:{attempt:Attempt|null;busy:boolean;ready:boolean;hasNext:boolean;onNext:()=>void;onRestart:()=>void;motionMessage?:string|null;comparing?:boolean;canRestart?:boolean}){
  const feedback=useRef<HTMLElement>(null)
  useEffect(()=>{if(attempt)feedback.current?.scrollIntoView({block:'nearest',behavior:'smooth'})},[attempt])
  const checking=busy&&!attempt?.closed&&!motionMessage
  const title=checking?(ready?'Verifica della mossa…':'Preparazione del puzzle…'):attempt?.success?'✓ Mossa corretta!':attempt?.closed?'Soluzione mostrata':attempt?'↻ Mossa da migliorare':'Trova una buona mossa'
  return <section ref={feedback} className={`puzzle-feedback ${attempt?.success?'solved':attempt&&!attempt.closed?'retry':''}`} aria-label="Esito del puzzle">
    <div role="status" aria-live="polite" aria-atomic="true"><h3>{title}</h3><p>{motionMessage||(checking?'Attendi un momento.':attempt?.success?(comparing?'Puzzle risolto. Confronta le frecce nella posizione iniziale.':'Puzzle risolto. La scacchiera mostra la tua mossa.'):attempt?.closed?'La scacchiera mostra la soluzione: questo puzzle non conta come risolto.':attempt?'La scacchiera è tornata alla posizione iniziale: prova un’altra mossa.':'Muovi un pezzo: Stockfish verificherà la tua scelta.')}</p></div>
    {attempt?.closed&&<p>{attempt.scheduled?'Risolto al primo tentativo senza aiuti: tolto dai puzzle da ripassare.':new Date(attempt.dueAt).getTime()>Date.now()?'Il prossimo ripasso di questo puzzle è già programmato.':'Questo puzzle resta nella lista da ripassare.'}</p>}
    {attempt?.closed&&<div className="puzzle-next">{hasNext?<button className="primary" disabled={busy} onClick={onNext}>Prossimo puzzle →</button>:<><p>Non ci sono altri puzzle in questa sessione.</p>{canRestart?<button disabled={busy} onClick={onRestart}>Ricomincia gli esercizi</button>:<p>Hai completato tutti i puzzle da ripassare.</p>}</>}</div>}
  </section>
}
