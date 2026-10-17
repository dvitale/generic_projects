import {useEffect,useState} from 'react'
import {api} from '../api'
import InfoNote from '../InfoNote'
import StudyBoard from './StudyBoard'
import type {AnalysisArrow} from '../Board'
import type {CardsOverview,Rating} from './types'

const ratings:[Rating,string][]=[['again','Di nuovo'],['hard','Difficile'],['good','Bene'],['easy','Facile']]
export function interval(days:number){
  if(days===0)return '10 min'
  if(days<1.5)return '1 giorno'
  if(days<60)return `${Math.round(days)} giorni`
  return `${Math.round(days/30)} mesi`
}

export default function Flashcards({onReview}:{onReview:(gameId:string,ply:number)=>void}){
  const [data,setData]=useState<CardsOverview|null>(null)
  const [revealed,setRevealed]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [session,setSession]=useState(0)
  async function load(){try{setData(await api<CardsOverview>('/study/cards'));setError('')}catch(e){setError(e instanceof Error?e.message:'Schede non disponibili')}}
  useEffect(()=>{void load()},[])
  const card=data?.due[0]
  async function act(path:string,body:object){
    if(!card||busy)return
    setBusy(true)
    try{await api(`/study/cards/${card.id}/${path}`,body);setRevealed(false);setSession(n=>n+1);await load()}
    catch(e){setError(e instanceof Error?e.message:'Operazione non riuscita')}
    finally{setBusy(false)}
  }
  useEffect(()=>{
    const key=(event:KeyboardEvent)=>{
      if(!card||event.altKey||event.ctrlKey||event.metaKey||(event.target as HTMLElement).closest?.('input,select,textarea,button'))return
      if(!revealed&&event.key===' '){event.preventDefault();setRevealed(true)}
      const index=Number(event.key)-1
      if(revealed&&index>=0&&index<4){event.preventDefault();void act('review',{rating:ratings[index][0]})}
    }
    window.addEventListener('keydown',key)
    return()=>window.removeEventListener('keydown',key)
  },[card?.id,revealed,busy])
  const arrows:AnalysisArrow[]=[]
  if(card&&revealed){
    if(card.bestMove)arrows.push({move:card.bestMove,source:'stockfish',rank:1})
    if(card.move)arrows.push({move:card.move,source:'played',rank:1})
  }
  return <>
    {error&&<div className="alert" role="alert">{error}<button onClick={()=>void load()}>Riprova</button></div>}
    <div className="prevention-summary"><span><strong>{data?.due.length??'—'}</strong> schede da ripassare</span><span><strong>{data?.total??0}</strong> schede attive</span><span>{session} ripassate in questa sessione</span></div>
    {!card?<section className="panel study-empty"><span className="eyebrow">FLASHCARD DELLE LEZIONI</span><h2>{data?.total?'Nessuna scheda da ripassare ora':'Ancora nessuna scheda'}</h2>
      <p>{data?.nextDue?`La prossima scheda torna il ${new Date(data.nextDue).toLocaleString('it-IT',{dateStyle:'medium',timeStyle:'short'})}.`:'Le schede nascono dalle tue lezioni.'}</p>
      <ul className="study-list"><li>Ogni <strong>Spiega motivo</strong> nei puzzle e in Blunder prevention diventa una scheda con la sua lezione.</li><li>In <strong>Impara da una partita</strong> e in <strong>Chiedi al tutor</strong> puoi scrivere la tua lezione e salvarla.</li></ul>
    </section>:<div className="training-layout layout-study">
      <StudyBoard fen={card.fen} side={card.turn} arrows={arrows} caption={revealed?'Freccia bianca: la tua mossa di allora. Freccia blu: la scelta di Stockfish.':'Osserva la posizione prima di girare la scheda.'}/>
      <aside className="coach-column">
        <section className="panel flashcard" aria-label="Scheda">
          <span className="eyebrow">{card.theme} · {card.kind==='explanation'?'dalla spiegazione di un tentativo':'la tua lezione'}</span>
          <h2>{card.question}</h2>
          {!revealed?<button className="primary full" onClick={()=>setRevealed(true)}>Mostra risposta <kbd>Spazio</kbd></button>:<>
            <p className="hint flashcard-lesson">{card.lesson}</p>
            {(card.san||card.bestSan)&&<p>{card.san&&<>Avevi giocato <strong>{card.san}</strong>. </>}{card.bestSan&&<>Stockfish preferisce <strong>{card.bestSan}</strong>.</>}</p>}
            <p className="muted">Quanto ti è venuto facile ricordarla?</p>
            <div className="rating-row" role="group" aria-label="Valuta il ricordo">{ratings.map(([rating,label],i)=><button key={rating} className={'rating-'+rating} disabled={busy} onClick={()=>void act('review',{rating})}><strong>{label}</strong><small>{interval(card.preview[rating])} · {i+1}</small></button>)}</div>
          </>}
          <div className="row">{card.gameId&&card.ply!==null&&<button className="quiet" onClick={()=>onReview(card.gameId!,card.ply!)}>Rivedi nella partita</button>}<button className="quiet" disabled={busy} onClick={()=>{if(window.confirm('Archiviare la scheda? Non tornerà più nei ripassi.'))void act('archive',{})}}>Archivia scheda</button></div>
        </section>
        <InfoNote summary="Come funzionano gli intervalli">Rispondi a mente, poi gira la scheda e valuta con sincerità: <em>Di nuovo</em> la ripropone tra 10 minuti, le altre risposte allungano l’intervallo (1, 3 giorni e poi in crescita). Le schede allenano il principio, non la mossa: i puzzle restano il posto dove trovare la mossa giusta.</InfoNote>
      </aside>
    </div>}
  </>
}
