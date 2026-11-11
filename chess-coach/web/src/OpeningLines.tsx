import {useEffect,useMemo,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import MiniBoard from './MiniBoard'
import InfoNote from './InfoNote'
import {api} from './api'
import {useBoardOrientation} from './boardFlip'
import type {Color} from './types'

export interface LineInfo {id:string;name:string;sans:string[];fen:string;met:number;terminal:boolean;review:{streak:number;reviews:number;failures:number;dueAt:string;due:boolean}|null}
export interface Family {id:string;name:string;description:string;fen:string;games:number;lines:LineInfo[]}
export interface LineSession {id:string;family:string;familyName:string;color:Color;status:'active'|'complete';version:number;fen:string;moves:string[];sans:string[];turn:Color;legalMoves:string[];
  errors:{ply:number;played:string[];expected:string[]}[];hints:number;expected:string[]|null;wrong:{san:string;expected:string[]}|null;reply:string|null;target:string|null;
  line:{id:string;name:string}|null;review:{streak:number;dueAt:string}|null;independent:boolean|null}
export interface LineStart {family?:string;color:Color;lines?:string[];target?:string}

const storeKey=(family:string,color:Color)=>`chess-coach-lines:${family}:${color}`
function storedLines(family:string,color:Color):string[]|null{try{const v=localStorage.getItem(storeKey(family,color));return v?JSON.parse(v):null}catch{return null}}
function storeLines(family:string,color:Color,lines:string[]){try{localStorage.setItem(storeKey(family,color),JSON.stringify(lines))}catch{/* per-viewer convenience only */}}
const when=(iso:string)=>new Date(iso).toLocaleString('it-IT',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})
export function numbered(sans:string[]){return sans.map((s,i)=>i%2===0?`${i/2+1}. ${s}`:s).join(' ')}

/** Opening families of the Drill catalogue: a line to play against Maia from its end, or the review of its book moves. */
export function OpeningFamilies({color,disabled,onDrill,onReview}:{color:Color;disabled:boolean;onDrill:(id:string)=>void;onReview:(start:LineStart)=>void}){
  const [families,setFamilies]=useState<Family[]>([])
  const [error,setError]=useState('')
  const [chosen,setChosen]=useState<Record<string,string>>({})
  const [included,setIncluded]=useState<Record<string,string[]>>({})
  useEffect(()=>{let stale=false;api<Family[]>('/opening-lines?color='+color).then(f=>{if(stale)return;setFamilies(f)
    setIncluded(Object.fromEntries(f.map(x=>{const ends=x.lines.filter(l=>l.terminal).map(l=>l.id);const kept=(storedLines(x.id,color)??ends).filter(id=>ends.includes(id));return[x.id,kept.length?kept:ends]})))}).catch(e=>{if(!stale)setError((e as Error).message)});return()=>{stale=true}},[color])
  function toggle(family:Family,id:string){
    const ends=family.lines.filter(l=>l.terminal).map(l=>l.id),current=included[family.id]??ends
    const next=current.includes(id)?current.filter(x=>x!==id):[...current,id]
    if(!next.length)return
    setIncluded(v=>({...v,[family.id]:next}));storeLines(family.id,color,next)
  }
  if(error)return <p className="alert" role="alert">{error}</p>
  return <div className="drill-catalog opening-families">{families.map(f=>{
    const best=[...f.lines].sort((a,b)=>b.met-a.met)[0]
    const selected=chosen[f.id]??(best?.met?best.id:f.lines[0]?.id)
    const ends=f.lines.filter(l=>l.terminal),mine=included[f.id]??ends.map(l=>l.id)
    const due=ends.filter(l=>l.review?.due).length
    return <article className="panel drill-card opening-family" key={f.id}>
      <MiniBoard fen={f.fen} orientation={color}/>
      <div className="drill-card-body"><h3>{f.name}</h3><p>{f.description}</p>
        <p className="footnote">{f.games?`Nelle tue partite col ${color==='w'?'Bianco':'Nero'}: ${f.games}.`:`Nessuna tua partita col ${color==='w'?'Bianco':'Nero'}.`}{due>0&&<> <strong>{due} {due===1?'linea da ripassare':'linee da ripassare'}.</strong></>}</p></div>
      <label className="opening-line-pick">Linea <select aria-label={`Linea di ${f.name}`} value={selected} onChange={e=>setChosen(v=>({...v,[f.id]:e.target.value}))}>{f.lines.map(l=><option key={l.id} value={l.id}>{l.name}{l.met?` · ${l.met} tue partite`:''}</option>)}</select></label>
      <div className="opening-family-actions">
        <button aria-label={`Avvia ${f.name} contro Maia`} disabled={disabled||!selected} onClick={()=>onDrill('line:'+selected)} title="La linea è già sulla scacchiera: continui tu contro Maia">Contro Maia</button>
        <button className="primary" aria-label={`Ripassa ${f.name}`} disabled={disabled} onClick={()=>onReview({family:f.id,color,lines:mine})} title="Giochi tu le mosse di teoria dalla posizione iniziale">Ripassa la linea</button>
      </div>
      <details className="opening-family-lines"><summary>Linee del ripasso ({mine.length}/{ends.length})</summary>
        <ul>{ends.map(l=><li key={l.id}><label><input type="checkbox" checked={mine.includes(l.id)} onChange={()=>toggle(f,l.id)}/> <span>{l.name}</span></label>
          <small className="muted">{numbered(l.sans)}{l.met?` · ${l.met} tue partite`:''}{l.review?(l.review.due?' · da ripassare':` · ripasso ${l.review.streak} · ${when(l.review.dueAt)}`):''}</small></li>)}</ul>
        <p className="footnote">L’avversario sceglie fra le linee selezionate, preferendo quelle delle tue partite e quelle da ripassare. Una linea esclusa resta disponibile contro Maia.</p>
      </details>
    </article>})}</div>
}

/** Line review: the player plays the book moves of one side; a move out of book is not played and the book move is shown. */
export function LineReview({session,onSession,onDrill,onRestart}:{session:LineSession;onSession:(s:LineSession)=>void;onDrill:(id:string)=>void;onRestart:()=>void}){
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [pending,setPending]=useState(false)
  const orientation=useBoardOrientation(session.color)
  // The opponent's book reply is shown after the player's move, not at once.
  const before=useMemo(()=>{if(!session.reply)return null;const c=new Chess();for(const m of session.moves.slice(0,-1))c.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]});return c.fen()},[session.id,session.version,session.reply])
  useEffect(()=>{if(!session.reply)return;setPending(true);const t=setTimeout(()=>setPending(false),650);return()=>clearTimeout(t)},[session.id,session.version,session.reply])
  const shown=pending&&before?before:session.fen
  const last=pending?session.moves.at(-2):session.moves.at(-1)
  async function call(path:string,body:unknown){setBusy(true);setError('');try{onSession(await api<LineSession>(`/opening-lines/sessions/${session.id}/${path}`,body))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  const mine=session.status==='active'&&session.turn===session.color
  const done=session.status==='complete'
  return <div className="training-layout line-review">
    <section className="board-column"><div className="player-row"><span className="avatar">♞</span><div className="player-info"><strong>{session.familyName}</strong><small>{session.color==='w'?'Giochi col Bianco':'Giochi col Nero'} · {done?'Linea completata':mine?'Tocca a te: gioca la mossa di teoria':'L’avversario risponde dal libro'}</small></div></div>
      <Board fen={shown} orientation={orientation} legalMoves={session.legalMoves} interactive={mine&&!busy&&!pending} onMove={m=>call('move',{move:m,version:session.version})} lastMove={last} animateMove={!pending}/>
    </section>
    <aside className="coach-column"><section className="panel">
      <span className="eyebrow">RIPASSO DELLA LINEA</span><h2>{session.target?`${session.familyName}: ${session.target}`:session.familyName}</h2>
      {error&&<p className="alert" role="alert">{error}</p>}
      <p className="line-moves" aria-label="Mosse giocate">{session.sans.length?numbered(session.sans):'Nessuna mossa ancora.'}</p>
      {session.wrong&&<p className="line-wrong" role="status"><strong>✗ {session.wrong.san} non è la teoria.</strong> Qui si gioca {session.wrong.expected.join(' o ')}: giocala sulla scacchiera.</p>}
      {!session.wrong&&session.expected&&<p className="line-expected" role="status">La teoria qui: <strong>{session.expected.join(' o ')}</strong>.</p>}
      {!done&&<><button className="full" disabled={busy||!mine||!!session.expected} onClick={()=>call('hint',{version:session.version})}>Mostra la mossa di teoria</button>
        <p className="muted">Una mossa fuori dal libro non viene giocata: vedi quella di teoria e riprovi. Errori e mosse mostrate fanno tornare presto la linea in ripasso.</p></>}
      {done&&<div className="line-result">
        <h3>{session.errors.length||session.hints?'Linea completata, con aiuti':'✓ Linea completata senza errori'}{session.line?`: ${session.line.name}`:''}</h3>
        {session.errors.length>0&&<ul className="line-errors">{session.errors.map(e=><li key={e.ply}>{Math.floor(e.ply/2)+1}{e.ply%2?'…':'.'} hai giocato {e.played.join(', ')}; la teoria è {e.expected.join(' o ')}</li>)}</ul>}
        {session.hints>0&&<p>Mosse di teoria mostrate: {session.hints}.</p>}
        <p className="footnote">{session.independent?(session.review?`Prossimo ripasso: ${when(session.review.dueAt)}.`:''):'Ripetizione di pratica: il ripasso era già programmato più avanti e il calendario non cambia.'}</p>
        {session.line&&<button className="primary full" onClick={()=>onDrill('line:'+session.line!.id)}>Continua contro Maia da qui →</button>}
        <button className="full" onClick={onRestart}>Un’altra linea →</button>
      </div>}
      <InfoNote summary="Come funziona">Parti dalla posizione iniziale e giochi le mosse del tuo colore; l’avversario sceglie fra le linee selezionate dell’apertura, preferendo quelle delle tue partite e quelle da ripassare. Una linea senza errori né aiuti torna dopo intervalli crescenti, come i Puzzle (4 ore, 1, 3, 7, 14, 30, 90 e 180 giorni); con un errore torna dopo 4 ore. Le linee e i nomi vengono dal catalogo Lichess delle aperture.</InfoNote>
    </section></aside>
  </div>
}
