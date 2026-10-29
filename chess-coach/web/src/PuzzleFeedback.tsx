import { useEffect, useRef } from 'react'
import type { Attempt, Practice } from './types'

export default function PuzzleFeedback({attempt,busy,ready,hasNext,onNext,onRestart,onPlayFrom,motionMessage,comparing,canRestart=true,practice,onPractice}:{attempt:Attempt|null;busy:boolean;ready:boolean;hasNext:boolean;onNext:()=>void;onRestart:()=>void;onPlayFrom?:{label:string;play:()=>void};motionMessage?:string|null;comparing?:boolean;canRestart?:boolean;practice?:Practice|null;onPractice?:()=>void}){
  const feedback=useRef<HTMLElement>(null)
  // Only scroll when the message is off screen (phones): on desktop the board must not move.
  useEffect(()=>{const r=feedback.current?.getBoundingClientRect();if(attempt&&r&&(r.bottom>innerHeight||r.top<0))feedback.current?.scrollIntoView({block:'nearest',behavior:'smooth'})},[attempt])
  const checking=busy&&!attempt?.closed&&!motionMessage
  // practice: undefined outside free practice, null before its first move.
  if(practice!==undefined&&attempt?.closed)return <section ref={feedback} className={`puzzle-feedback ${practice?.success?'solved':practice?'retry':''}`} aria-label="Esito del puzzle">
    <div role="status" aria-live="polite" aria-atomic="true"><h3>{busy&&!motionMessage?'Verifica della mossa…':practice?.success?`✓ ${practice.san}: mossa corretta`:practice?`↻ ${practice.san}: c’è di meglio`:'↺ Pratica dalla posizione iniziale'}</h3>
      <p>{motionMessage||(practice?.success?'Puoi ricominciare quante volte vuoi.':'Muovi un pezzo: Stockfish verifica la mossa. La pratica non conta per i ripassi.')}</p></div>
    <div className="puzzle-next"><button disabled={busy} onClick={onPractice}>↺ Riprova da capo</button>{hasNext&&<button className="primary" disabled={busy} onClick={onNext}>Prossimo puzzle →</button>}</div>
    {onPlayFrom&&<button className="play-from" disabled={busy} title="Nuova partita contro Maia dalla posizione iniziale del puzzle" onClick={onPlayFrom.play}>{onPlayFrom.label}</button>}
  </section>
  const title=checking?(ready?'Verifica della mossa…':'Preparazione del puzzle…'):attempt?.success?'✓ Mossa corretta!':attempt?.closed?'Soluzione mostrata':attempt?'↻ Mossa da migliorare':'Trova una buona mossa'
  return <section ref={feedback} className={`puzzle-feedback ${attempt?.success?'solved':attempt&&!attempt.closed?'retry':''}`} aria-label="Esito del puzzle">
    <div role="status" aria-live="polite" aria-atomic="true"><h3>{title}</h3><p>{motionMessage||(checking?'Attendi un momento.':attempt?.success?(comparing?'Posizione iniziale: in bianco la mossa giocata in partita, in rosso la scelta di Maia.':'La scacchiera mostra la tua mossa.'):attempt?.closed?'Sulla scacchiera la soluzione; non conta come risolto.':attempt?'La scacchiera è tornata alla posizione iniziale: prova un’altra mossa.':'Muovi un pezzo: Stockfish verificherà la tua scelta.')}</p></div>
    {attempt?.closed&&<small className="feedback-note">{attempt.scheduled?'Primo tentativo senza aiuti: tolto dai puzzle da ripassare.':new Date(attempt.dueAt).getTime()>Date.now()?'Prossimo ripasso già programmato.':'Il puzzle resta nella lista da ripassare: una ripetizione anticipata è pratica.'}</small>}
    {attempt?.closed&&<div className="puzzle-next">{hasNext?<button className="primary" disabled={busy} onClick={onNext}>Prossimo puzzle →</button>:<><p>Non ci sono altri puzzle in questa sessione.</p>{canRestart?<button disabled={busy} onClick={onRestart}>Ricomincia gli esercizi</button>:<p>Hai completato tutti i puzzle da ripassare.</p>}</>}</div>}
    {attempt?.closed&&onPractice&&<button disabled={busy} title="Riporta la scacchiera alla posizione iniziale per riprovare: non conta per i ripassi" onClick={onPractice}>↺ Riprova da capo</button>}
    {attempt?.closed&&onPlayFrom&&<button className="play-from" disabled={busy} title="Nuova partita contro Maia dalla posizione iniziale del puzzle" onClick={onPlayFrom.play}>{onPlayFrom.label}</button>}
  </section>
}
