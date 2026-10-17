import {useEffect,useState} from 'react'
import {Chess} from 'chess.js'
import {api} from '../api'
import InfoNote from '../InfoNote'
import StudyBoard from './StudyBoard'
import type {AnalysisArrow} from '../Board'
import type {Color} from '../types'
import type {Answer,StudyPosition} from './types'
import {pawns,scoreText} from './types'

interface Exchange {question:string;reply:Answer}

function legalMoves(fen:string){
  try{return new Chess(fen).moves({verbose:true}).map(m=>m.from+m.to+(m.promotion??''))}catch{return null}
}

export default function PositionTutor({position}:{position:StudyPosition|null}){
  const [fen,setFen]=useState(position?.fen??'')
  const [draft,setDraft]=useState(position?.fen??'')
  const [question,setQuestion]=useState('')
  const [explored,setExplored]=useState<string|null>(null)
  const [exchanges,setExchanges]=useState<Exchange[]>([])
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [saved,setSaved]=useState<Record<number,string>>({})
  useEffect(()=>{if(position){setFen(position.fen);setDraft(position.fen);setExchanges([]);setExplored(null);setQuestion(position.move?`Perché ${san(position.fen,position.move)} è un errore?`:'')}},[position?.fen,position?.move])
  const legal=fen?legalMoves(fen):null
  const turn=(fen.split(' ')[1]??'w') as Color
  function san(at:string,uci:string){try{return new Chess(at).move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]}).san}catch{return uci}}
  function explore(uci:string){
    setExplored(uci)
    setQuestion(`Perché non ${san(fen,uci)}?`)
  }
  async function ask(){
    if(!question.trim()||busy||!legal)return
    setBusy(true);setError('')
    try{
      const reply=await api<Answer>('/study/ask',{fen,question,history:exchanges.slice(-4).map(x=>({question:x.question,answer:x.reply.answer}))})
      setExchanges(list=>[...list,{question,reply}]);setQuestion('')
    }catch(e){setError(e instanceof Error?e.message:'Il tutor non ha risposto')}finally{setBusy(false)}
  }
  async function saveLesson(index:number){
    const {reply}=exchanges[index]
    try{
      await api('/study/cards',{fen,lesson:reply.lesson,move:reply.moves[0]?.uci??null,bestMove:reply.best.pv[0]??null,
        question:reply.moves[0]?`Perché ${reply.moves[0].san} non va in questa posizione?`:'Che cosa devi controllare in questa posizione?',
        gameId:position?.fen===fen?position.gameId??null:null,ply:position?.fen===fen?position.ply??null:null})
      setSaved(s=>({...s,[index]:'Scheda creata: la trovi in Flashcard.'}))
    }catch(e){setSaved(s=>({...s,[index]:e instanceof Error?e.message:'Scheda non salvata'}))}
  }
  const last=exchanges.at(-1)?.reply
  const arrows:AnalysisArrow[]=[]
  if(last?.best.pv[0])arrows.push({move:last.best.pv[0],source:'stockfish',rank:1})
  const asked=explored??last?.moves[0]?.uci
  if(asked)arrows.push({move:asked,source:'played',rank:1})
  return <div className="training-layout layout-study">
    {legal?<StudyBoard fen={fen} side={turn} arrows={arrows} legalMoves={legal} onMove={explore} caption="Muovi un pezzo per chiedere di quella mossa: la scacchiera non cambia."/>
      :<section className="board-column panel study-empty"><p>Scegli una posizione dal pacchetto di una partita o dal quaderno, oppure incolla una FEN.</p></section>}
    <aside className="coach-column">
      <section className="panel"><span className="eyebrow">CHIEDI AL TUTOR</span><h2>{position?.fen===fen?position.title:'Posizione libera'}</h2>
        <form className="fen-form" onSubmit={e=>{e.preventDefault();if(legalMoves(draft.trim())){setFen(draft.trim());setExchanges([]);setExplored(null);setError('')}else setError('FEN non valida')}}>
          <label htmlFor="tutor-fen" className="field-label">FEN</label><div className="row"><input id="tutor-fen" type="text" value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Incolla una posizione in notazione FEN"/><button>Usa</button></div>
        </form>
        {legal&&<form onSubmit={e=>{e.preventDefault();void ask()}}>
          <label htmlFor="tutor-question" className="field-label">La tua domanda</label>
          <textarea id="tutor-question" rows={2} maxLength={600} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Per esempio: perché non Cxe5? Scrivi le mosse in notazione o muovi sulla scacchiera."/>
          <button className="primary" disabled={busy||question.trim().length<2}>{busy?'Stockfish verifica…':'Chiedi'}</button>
        </form>}
        {error&&<p role="alert" className="error-text">{error}</p>}
      </section>
      {exchanges.map((x,i)=><section key={i} className="panel tutor-exchange" aria-label={'Risposta '+(i+1)}>
        <p className="tutor-question"><strong>Tu:</strong> {x.question}</p>
        {x.reply.notice&&<p className="hint">{x.reply.notice}</p>}
        <p>{x.reply.answer}</p>
        <p className="hint"><strong>Da controllare prima di muovere. </strong>{x.reply.lesson}</p>
        <details open={i===exchanges.length-1}><summary>Varianti verificate da Stockfish</summary>
          <ul className="verified-lines">
            {x.reply.moves.map(m=><li key={m.uci}><strong>{m.san}</strong> {m.lossCp!=null?`· perde ${pawns(m.lossCp)}`:''} · {scoreText(m)}<p className="variation">{m.line.join(' ')}</p></li>)}
            <li><strong>Migliore: {x.reply.best.san[0]??'—'}</strong> · {scoreText(x.reply.best)}<p className="variation">{x.reply.best.san.join(' ')}</p></li>
          </ul></details>
        <div className="row"><button onClick={()=>void saveLesson(i)} disabled={!!saved[i]}>Salva la lezione come flashcard</button>{saved[i]&&<span role="status" className="footnote">{saved[i]}</span>}</div>
        <small className="footnote">{x.reply.provider==='DeepSeek'?'Risposta DeepSeek basata sulle varianti Stockfish: le mosse di pezzo citate sono state controllate.':'Risposta costruita solo dalle varianti di Stockfish (tutor DeepSeek non configurato o risposta scartata).'} Valutazioni dal punto di vista di chi muove.</small>
      </section>)}
      <InfoNote summary="Come vengono verificate le risposte">Le mosse citate nella domanda (anche in notazione italiana: C, A, T, D, R) vengono analizzate da Stockfish. Se il tutor DeepSeek è configurato riceve solo quelle varianti; una risposta che cita mosse di pezzo o catture non presenti nelle varianti viene scartata e sostituita dai fatti di Stockfish.</InfoNote>
    </aside>
  </div>
}
