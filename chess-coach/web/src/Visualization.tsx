import {useEffect,useState} from 'react'
import Board from './Board'
import InfoNote from './InfoNote'
import {api} from './api'
import {useBoardOrientation} from './boardFlip'
import type {Color} from './types'

interface Summary {plies:number;answered:number;recent:number;recentCorrect:number;byDepth:{plies:number;answered:number;correct:number}[];rules:{min:number;max:number;start:number;stepUp:number}}
interface Question {id:string;fen:string;orientation:Color;line:string;plies:number;question:string;options:string[]}
interface Answer {correct:boolean;answer:number;explanation:string;finalFen:string;moves:string[];summary:Summary}

const halfMoves=(n:number)=>n===1?'1 semimossa':`${n} semimosse`

/** Visualizza: a position from your games, a few moves to play only in your head, then one question on where they lead. */
export default function Visualization(){
  const [summary,setSummary]=useState<Summary|null>(null),[asked,setAsked]=useState<Question|null>(null)
  const [answer,setAnswer]=useState<Answer|null>(null),[choice,setChoice]=useState<number|null>(null)
  const [showEnd,setShowEnd]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const orientation=useBoardOrientation(asked?.orientation??'w')
  useEffect(()=>{api<Summary>('/visualization/summary').then(setSummary).catch(e=>setError(e.message))},[])
  async function next(){
    setBusy(true);setError('')
    try{setAsked(await api<Question>('/visualization/next',{}));setAnswer(null);setChoice(null);setShowEnd(true)}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function choose(index:number){
    if(!asked||answer)return
    setBusy(true);setError('');setChoice(index)
    try{const result=await api<Answer>(`/visualization/${asked.id}/answer`,{choice:index});setAnswer(result);setSummary(result.summary)}
    catch(e){setError((e as Error).message);setChoice(null)}finally{setBusy(false)}
  }
  const level=summary?.plies??2
  const stats=summary&&summary.recent>0&&<p className="footnote">Ultime {summary.recent} risposte: {summary.recentCorrect} giuste. {summary.byDepth.map(d=>`${halfMoves(d.plies)}: ${d.correct}/${d.answered}`).join(' · ')}</p>
  if(!asked)return <section className="panel visualization-intro"><span className="eyebrow">CALCOLO A MENTE</span><h2>Allena la visualizzazione</h2>
    <p>Vedi una posizione di una tua partita e le mosse che seguono, scritte ma non giocate sulla scacchiera. Seguile a mente, poi rispondi a una domanda sulla posizione a cui portano: che pezzo c’è in una casa, chi attacca un pezzo, quante catture ci sono, se il re è sotto scacco.</p>
    <p>Lunghezza attuale: <b>{halfMoves(level)}</b>. Cresce di una semimossa dopo {summary?.rules.stepUp??3} risposte giuste di fila, cala dopo un errore.</p>
    {error&&<p role="alert">{error}</p>}
    <button className="primary" disabled={busy} onClick={()=>void next()}>Inizia →</button>{stats}
    <InfoNote summary="Perché serve"><p>Molti errori nascono da una posizione immaginata male: un pezzo che si crede ancora su una casa, una presa che non c’è più. Qui la risposta la calcola il programma con le regole degli scacchi, senza motore: è giusta o sbagliata senza margini. Le mosse vengono dalle tue partite, dopo l’apertura.</p></InfoNote>
  </section>
  const finalShown=!!answer&&showEnd
  return <div className="training-layout layout-prevention visualization">
    <section className="board-column">
      <div className="player-row"><div className="player-info"><strong>{finalShown?'Posizione dopo la linea':'Posizione di partenza'}</strong><small>{finalShown?'Confronta con quella che avevi immaginato':'Le mosse non vengono giocate sulla scacchiera'}</small></div></div>
      <Board fen={finalShown?answer.finalFen:asked.fen} orientation={orientation} interactive={false} legalMoves={[]} onMove={()=>{}}/>
      {answer&&<div className="board-toolbar segmented" role="group" aria-label="Posizione mostrata"><button aria-pressed={!showEnd} onClick={()=>setShowEnd(false)}>Partenza</button><button aria-pressed={showEnd} onClick={()=>setShowEnd(true)}>Dopo la linea</button></div>}
    </section>
    <aside className="coach-column">
      <section className="panel visualization-question" aria-label="Domanda">
        <span className="eyebrow">GIOCA A MENTE · {halfMoves(asked.plies).toUpperCase()}</span>
        <p className="visualization-line">{asked.line}</p>
        <h3>{asked.question}</h3>
        <div className="visualization-options" role="group" aria-label="Risposte">{asked.options.map((option,i)=><button key={option} disabled={busy||!!answer}
          className={answer?(i===answer.answer?'option-right':i===choice?'option-wrong':''):''} onClick={()=>void choose(i)}>{option}</button>)}</div>
        {answer&&<div role="status" className={answer.correct?'notice':'alert'}><b>{answer.correct?'✓ Giusto.':'✗ Non è così.'}</b> {answer.explanation}</div>}
        {error&&<p role="alert">{error}</p>}
        {answer&&<button className="primary" disabled={busy} onClick={()=>void next()}>Prossima domanda →</button>}
        {stats}
      </section>
    </aside>
  </div>
}
