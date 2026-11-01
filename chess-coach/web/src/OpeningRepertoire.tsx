import {useEffect,useState} from 'react'
import InfoNote from './InfoNote'
import {api} from './api'
import type {Color} from './types'

interface Family {color:Color;family:string;eco:string;games:number;finished:number;score:number|null;analysed:number;decisions:number;sound:number|null;errors:number;firstMistake:number|null;status:'weak'|'watch'|'ok';variations:string[];exit:{gameId:string;number:number|null;title:string;ply:number;fen:string}|null}
interface Repertoire {families:Family[];overallSound:number|null;rules:{afterBook:number;watch:number;weakScore:number;weakDrop:number}}

const pct=(x:number|null)=>x===null?'—':`${Math.round(x*100)}%`
const statusLabel={weak:'Da curare',watch:'Poche partite',ok:''}

/** Progressi: the openings the player reaches, by colour, with results and the decisions right after the book. */
export default function OpeningRepertoire({onReview,onDrill}:{onReview:(id:string,ply:number)=>void;onDrill:(templateId:string)=>void}){
  const [data,setData]=useState<Repertoire|null>(null),[error,setError]=useState(''),[all,setAll]=useState(false)
  useEffect(()=>{let stale=false;api<Repertoire>('/openings/repertoire').then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[])
  const families=data?.families??[],shown=all?families:families.filter(f=>f.status!=='watch').slice(0,8)
  return <section className="panel opening-repertoire" aria-label="Il tuo repertorio"><span className="eyebrow">LE APERTURE CHE GIOCHI</span><h2>Il tuo repertorio</h2>
    {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Caricamento…</p>}
    {data&&!families.length&&<p>Nessuna apertura riconosciuta: compare qui ogni apertura delle tue partite dalla posizione iniziale.</p>}
    {shown.length>0&&<ul className="repertoire-list">{shown.map(f=><li key={f.color+f.family} className={`repertoire-row repertoire-${f.status}`}>
      <div className="repertoire-head"><span><i className={`side-dot side-dot-${f.color}`} aria-label={f.color==='w'?'col Bianco':'col Nero'}/><b>{f.family}</b> <small className="muted">{f.eco}</small>{f.status!=='ok'&&<span className={`repertoire-status status-${f.status}`}>{statusLabel[f.status]}</span>}</span>
        <span className="repertoire-games">{f.games} {f.games===1?'partita':'partite'}</span></div>
      <dl className="repertoire-stats">
        <div><dt>Punteggio</dt><dd>{pct(f.score)}{f.finished<f.games&&<small> su {f.finished}</small>}</dd></div>
        <div><dt>Dopo la teoria</dt><dd>{f.decisions?<>{pct(f.sound)} <small>senza perdite</small></>:<small>da analizzare</small>}</dd></div>
        <div><dt>Primo errore</dt><dd>{f.firstMistake===null?'—':<>{Math.round(f.firstMistake)}ª mossa <small>dopo la teoria</small></>}</dd></div>
      </dl>
      {f.exit&&<p className="repertoire-actions"><button className="quiet" onClick={()=>onReview(f.exit!.gameId,f.exit!.ply)} title={`Rivedi la fine della teoria in ${f.exit.number!=null?`#${f.exit.number} · `:''}${f.exit.title}`}>Rivedi dove finisce la teoria</button><button className="quiet" onClick={()=>onDrill('opening:'+f.exit!.gameId)} title="Drill contro Maia dalla stessa posizione, l’ultima di teoria della tua partita più recente con questa apertura">Allena da lì</button></p>}
    </li>)}</ul>}
    {families.length>shown.length&&<button className="quiet" onClick={()=>setAll(true)}>Mostra tutte ({families.length})</button>}
    {data&&<InfoNote summary="Come si legge"><p>Le aperture sono le famiglie del catalogo Lichess (la parte del nome prima dei due punti), per colore, nelle tue partite dalla posizione iniziale: drill, partite contro Stockfish e copie di revisione sono escluse. Il <b>punteggio</b> conta le partite finite (vittoria 1, patta ½). <b>Dopo la teoria</b> è la quota delle tue decisioni senza perdite rilevanti (meno di 80 centesimi) nelle {data.rules.afterBook} semimosse dopo l’ultima posizione di teoria, solo nelle partite analizzate; la tua media su tutte le aperture è {pct(data.overallSound)}. <b>Primo errore</b>: in media, quante tue mosse dopo la teoria arriva la prima imprecisione, nelle partite che ne hanno una.</p>
      <p>Un’apertura è <b>da curare</b> da {data.rules.watch} partite in su, con un punteggio sotto il {pct(data.rules.weakScore)} o una quota dopo la teoria di almeno {Math.round(data.rules.weakDrop*100)} punti sotto la tua media. Con meno partite resta fra quelle con <b>poche partite</b>, visibili con «Mostra tutte». Vedi docs/aperture.md.</p></InfoNote>}
  </section>
}
