import {useEffect,useRef,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import MistakeHistory from './MistakeHistory'
import {useTrainingMove} from './useTrainingMove'
import {api} from './api'
import type {Color,Evaluation} from './types'

interface Position {id:string;gameId:string;title:string;ply:number;fen:string;turn:Color;moveNumber:number;legalMoves:string[];dueAt:string;streak:number}
interface Catalog {positions:Position[];stats:{firstAttempts:number;firstSuccesses:number};analyzedGames:number;rule:{description:string}}
interface Session {id:string;version:number;exposure:string;excluded?:boolean;message?:string}
interface Result {success:boolean;assisted:boolean;closed:boolean;version:number;firstTry:boolean;move:string;san:string;actual:Evaluation;example:Evaluation|null;original:{move:string;san:string;evaluation:Evaluation}|null;message:string}
const evaluation=(e:Evaluation)=>e.mate!==null?(e.mate>0?`Matto a tuo favore in ${e.mate}`:`Matto contro di te in ${Math.abs(e.mate)}`):`${e.cp>=0?'+':''}${(e.cp/100).toFixed(2)}`

export default function BlunderPrevention({onArchive,onReview}:{onArchive:()=>void;onReview:(id:string,ply:number)=>void}) {
  const [catalog,setCatalog]=useState<Catalog|null>(null)
  const [position,setPosition]=useState<Position|null>(null)
  const [session,setSession]=useState<Session|null>(null)
  const [result,setResult]=useState<Result|null>(null)
  const [done,setDone]=useState<string[]>([])
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [showOriginal,setShowOriginal]=useState(false)
  const operation=useRef(0)
  const motion=useTrainingMove(position?.id+':'+(session?.id??''))
  async function refresh(){const next=await api<Catalog>('/prevention');setCatalog(next);return next}
  useEffect(()=>{let stale=false;api<Catalog>('/prevention').then(c=>{if(!stale)setCatalog(c)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true;operation.current++}},[])
  const remaining=catalog?.positions.filter(p=>!done.includes(p.id)&&p.id!==position?.id)||[]
  async function open(p:Position){
    const token=++operation.current
    motion.show(null)
    setBusy(true);setError('');setNotice('');setPosition(p);setSession(null);setResult(null);setShowOriginal(false)
    try{
      const s=await api<Session>(`/prevention/${p.id}/sessions`,{})
      if(token!==operation.current)return
      if(s.excluded){setNotice(s.message||'Posizione esclusa.');setDone(d=>[...d,p.id]);setPosition(null);await refresh()}
      else setSession(s)
    }catch(e){if(token===operation.current)setError(e instanceof Error?e.message:'Preparazione non riuscita')}
    finally{if(token===operation.current)setBusy(false)}
  }
  async function submit(move?:string){
    if(!position||!session||busy||result?.closed)return
    const ticket=move?motion.start(move):null
    if(move&&ticket===null)return
    const token=++operation.current
    setBusy(true);setError('');setNotice('')
    try{
      const response=await api<Result>(`/prevention/${position.id}/${move?'attempts':'reveal'}`,{session_id:session.id,version:session.version,...(move?{move}:{})})
      if(token!==operation.current)return
      setResult(response);setSession({...session,version:response.version})
      if(response.closed)setDone(d=>[...d,position.id])
      if(ticket!==null)await motion.finish(ticket,response.closed)
      else motion.show(response.move)
      if(token!==operation.current)return
      await refresh()
    }catch(e){if(token===operation.current){setError(e instanceof Error?e.message:'Verifica non riuscita');if(ticket!==null)await motion.finish(ticket,false)}}
    finally{if(token===operation.current)setBusy(false)}
  }
  function next(){const p=remaining[0];if(p)void open(p)}
  const displayedMove=showOriginal?result?.original?.move:motion.move??undefined
  const board=position?new Chess(position.fen):null
  if(board&&displayedMove)board.move({from:displayedMove.slice(0,2),to:displayedMove.slice(2,4),promotion:displayedMove[4]})
  return <div className="prevention">
    {error&&<div className="alert" role="alert">{error}<button disabled={busy} onClick={()=>position?void open(position):void refresh().catch(e=>setError(e.message))}>Riprova</button></div>}
    {notice&&<div className="notice" role="status">{notice}</div>}
    <div className="prevention-summary"><span><strong>{catalog?.positions.length??'—'}</strong> tue posizioni</span><span><strong>{catalog?.stats.firstSuccesses??0} / {catalog?.stats.firstAttempts??0}</strong> primi tentativi riusciti senza aiuti</span><span>{done.length} completate o escluse in questa sessione</span></div>
    {!position?<section className="panel prevention-intro"><span className="eyebrow">UNA SCELTA SICURA</span><h2>Riconosci il pericolo prima di muovere.</h2><p>Ritrova una posizione in cui hai commesso un blunder. Puoi scegliere qualsiasi mossa che mantenga la partita difendibile: non devi indovinare la prima scelta del motore.</p>
      {!catalog?<p role="status">Caricamento delle tue posizioni…</p>:remaining.length?<button className="primary" disabled={busy} onClick={next}>Inizia Blunder prevention →</button>:<><p>{catalog.positions.length?'Hai completato tutte le posizioni disponibili in questa sessione.':'Nessun blunder evitabile disponibile. Gioca o importa una partita, seleziona il tuo colore e avvia Analizza partita: le posizioni adatte appariranno qui.'}</p>{catalog.positions.length>0&&<button onClick={()=>{setDone([]);void open(catalog.positions[0])}}>Ripeti come pratica</button>}<button onClick={onArchive}>Apri le tue partite</button></>}
      <p className="footnote">{catalog?.rule.description} Le posizioni già perse prima dell’errore vengono escluse. Il primo accesso include una verifica Stockfish approfondita.</p></section>:<div className="training-layout layout-prevention">
      <section className="board-column">
        <section className={`puzzle-feedback ${result?.success?'solved':result&&!result.closed?'retry':''}`} aria-label="Esito Blunder prevention">
          <div role="status" aria-live="polite"><h3>{motion.message?'↻ Mossa da migliorare':busy?session?'Verifica della mossa…':'Verifica della posizione…':result?.success?'✓ Blunder evitato!':result?.closed?'Una mossa sicura':result?'↻ Riprova una mossa diversa':'Evita il blunder'}</h3><p>{motion.message|| (busy?'Stockfish sta controllando la posizione.':result?.message||'Cerca una mossa sicura. Più alternative possono essere corrette.')}</p></div>
          {result?.closed&&<div className="puzzle-next">{remaining.length?<button className="primary" disabled={busy} onClick={next}>Prossima posizione →</button>:<><p>Hai completato tutte le posizioni disponibili.</p><button onClick={()=>{setPosition(null);setSession(null);setResult(null)}}>Riepilogo della sessione</button></>}</div>}
        </section>
        <div className="player-row"><span className="avatar">◇</span><div><strong>{position.turn==='w'?'Muove il Bianco':'Muove il Nero'}</strong><small>Mossa {position.moveNumber} · {position.title}</small></div></div>
        <Board fen={board!.fen()} orientation={position.turn} legalMoves={position.legalMoves} interactive={!busy&&!!session&&!result?.closed} onMove={move=>void submit(move)} lastMove={showOriginal?displayedMove:motion.lastMove} animateMove reverseMove={!showOriginal&&motion.reverse}/>
        <p className="footnote">{showOriginal?'Scacchiera dopo il tuo errore originale.':result?.closed?'Scacchiera dopo la mossa verificata.':'Scacchiera prima del tuo errore: trascina un pezzo o usa due clic.'}</p>
      </section>
      <aside className="coach-column">
        <section className="panel"><span className="eyebrow">PRIMA DI MUOVERE</span><h2>Controlla entrambi i colori.</h2><ol><li>Il re è al sicuro?</li><li>Quali pezzi sono attaccati o indifesi?</li><li>Quali scacchi e catture avrà l’avversario?</li></ol><p className="muted">Una mossa semplice che evita la perdita è sufficiente.</p>
          {!result?.closed&&<div className="row"><button disabled={busy||!session} onClick={()=>void submit()}>Mostra una mossa sicura</button><button disabled={busy||!remaining.length} onClick={()=>{setDone(d=>[...d,position.id]);next()}}>Salta posizione</button></div>}
          <p className="footnote">{catalog?.rule.description} I valori sono dal tuo punto di vista e sono stime del motore.</p>
          {session?.exposure==='practice'&&<p className="footnote">Ripetizione anticipata: utile per esercitarti, non aumenta i successi indipendenti.</p>}
        </section>
        {result&&<section className="panel"><span className="eyebrow">LA TUA SCELTA</span><h2>{result.san} · {evaluation(result.actual)}</h2>{!result.closed?<><p>Dopo aver mostrato la mossa, la scacchiera torna alla posizione iniziale per riprovare.</p><p className="variation">Possibile seguito: {result.actual.san.join(' ')}</p></>:<><p>{result.assisted?'Esempio mostrato con aiuto.':result.firstTry?'Riuscito al primo tentativo senza aiuti.':'Mossa accettata. I tentativi precedenti restano registrati.'}</p><p className="variation">Possibile seguito: {result.actual.san.join(' ')}</p></>}</section>}
        {result?.closed&&result.original&&<section className="panel"><span className="eyebrow">IL CONFRONTO CON LA PARTITA</span><h3>Avevi giocato {result.original.san}</h3><p>Valutazione dopo l’errore: {evaluation(result.original.evaluation)}.</p><p className="variation">{result.original.evaluation.san.join(' ')}</p><div className="row"><button onClick={()=>setShowOriginal(v=>!v)}>{showOriginal?'Mostra la mossa sicura':'Mostra il vecchio errore'}</button><button onClick={()=>onReview(position.gameId,position.ply)}>Rivedi nella partita</button></div></section>}
        <MistakeHistory key={position.id} kind="prevention" targetId={position.id} revision={session?.version??0}/>
      </aside>
    </div>}
  </div>
}
