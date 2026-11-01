import MiniBoard from './MiniBoard'
import InfoNote from './InfoNote'
import type {Color} from './types'

export type PathStage='lesson'|'themed'|'mixed'|'waiting'|'review'|'closed'
export interface StudyPathView {id:string;gap:string;source:'puzzle'|'problem';theme:string;family:'method'|'tactic'|'theory';stage:PathStage;round:number;reviewAt:string|null;outcome:string|null;
  lesson:{title:string;recognize:string;question:string};example:{fen:string;turn:Color;solution:string[];label:string}|null;progress:{done:number;size:number;solved:number|null};sizes:{themed:number;mixed:number};fewPuzzles:boolean}
export interface ClosedPath {gap:string;title:string;source:'puzzle'|'problem';outcome:'passed'|'abandoned';reviewAt:string|null;closedAt:string}

export const stageLabels:Record<PathStage,string>={lesson:'Lezione',themed:'Serie a tema',mixed:'Serie mista',waiting:'Ripasso in attesa',review:'Ripasso dei problemi sbagliati',closed:'Concluso'}
const steps:PathStage[]=['lesson','themed','mixed','review']
const day=(iso:string)=>new Date(iso).toLocaleDateString('it-IT',{day:'numeric',month:'long'})

/** One line for the coach column while a path problem is on the board; the mixed series never names its theme. */
export function closedNotice(last:ClosedPath){
  if(last.outcome!=='passed')return `Percorso «${last.title}» abbandonato.`
  return `Percorso «${last.title}» concluso: serie mista superata.${last.source==='puzzle'&&last.reviewAt?` I puzzle che avevi sbagliato tornano nei ripassi dal ${day(last.reviewAt)}.`:' Lacuna superata.'}`
}

export function pathStatus(path:StudyPathView){
  const {done,size}=path.progress
  return `${path.lesson.title} · ${stageLabels[path.stage]}${size?` ${Math.min(done+1,size)} / ${size}`:''}${path.stage==='mixed'?' · il tema non è annunciato':''}`
}

/** The study path in Problemi: the lesson with the player's own failure, then the series and the review. */
export function StudyPathPanel({path,busy,onBegin,onContinue,onLeave,onAbandon}:{path:StudyPathView;busy:boolean;onBegin:()=>void;onContinue:()=>void;onLeave:()=>void;onAbandon:()=>void}){
  const {done,size,solved}=path.progress
  const current=steps.indexOf(path.stage==='waiting'?'review':path.stage)
  return <section className="panel study-path" aria-label="Percorso di studio">
    <span className="eyebrow">PERCORSO DI STUDIO{path.round>1?` · GIRO ${path.round}`:''}</span>
    <h2>{path.lesson.title}</h2>
    <ol className="study-path-steps">{steps.map((step,i)=><li key={step} className={i<current?'done':i===current?'current':''} aria-current={i===current?'step':undefined}>{stageLabels[step]}</li>)}</ol>
    {path.stage==='lesson'?<>
      <h3>Come si riconosce</h3><p>{path.lesson.recognize}</p>
      <h3>La domanda da farti</h3><p>{path.lesson.question}</p>
      {path.example&&<div className="study-path-example"><MiniBoard fen={path.example.fen} orientation={path.example.turn}/><div><strong>{path.example.label}</strong>
        <p>Una delle posizioni che non hai risolto. Muove il {path.example.turn==='w'?'Bianco':'Nero'}; la soluzione era <b>{path.example.solution.join(' ')}</b>.</p></div></div>}
      {path.fewPuzzles&&<p className="footnote">Ci sono pochi problemi Lichess con questo tema: alcuni si ripeteranno. Con make puzzles e un valore di PER_BAND più alto ne importi altri.</p>}
      <p className="muted">Poi {path.sizes.themed} problemi Lichess con questo tema, dal più facile al più difficile, e una serie mista di {path.sizes.mixed} in cui il tema non è annunciato.</p>
      <div className="row"><button className="primary" disabled={busy} onClick={onBegin}>Ho letto: inizia la serie →</button></div>
    </>:path.stage==='waiting'?<p>Serie mista superata. Il ripasso dei problemi che avevi sbagliato è disponibile dal <b>{day(path.reviewAt!)}</b>: a distanza di giorni si vede se lo schema è rimasto.</p>
    :<>
      <p>{stageLabels[path.stage]}: {done} / {size} {solved!==null&&done>0?`· risolti ${solved}`:''}</p>
      {path.stage==='mixed'&&<p className="muted">Qui il tema non viene annunciato: solo metà dei problemi lo contiene. Riconoscerlo da solo è la prova vera.</p>}
      {path.round>1&&path.stage==='themed'&&<p className="muted">La serie mista non è andata come previsto dal rating: si riparte dalla serie a tema.</p>}
      <div className="row"><button className="primary" disabled={busy} onClick={onContinue}>Continua il percorso →</button></div>
    </>}
    <div className="row"><button className="quiet" onClick={onLeave}>Problemi liberi</button><button className="quiet" disabled={busy} onClick={onAbandon}>Abbandona il percorso</button></div>
    <InfoNote summary="Come funziona il percorso"><p>La lacuna nasce dai tuoi risultati: un gruppo di posizioni che risolvi al primo tentativo, senza aiuti, molto meno spesso del previsto. La serie a tema parte un po’ sotto il tuo rating e sale a ogni problema. La serie mista è superata quando i problemi con il tema vanno come previsto dal rating; altrimenti si ripete la serie a tema. I problemi del percorso cambiano il rating come gli altri, ma non entrano nel calcolo delle lacune.</p></InfoNote>
  </section>
}
