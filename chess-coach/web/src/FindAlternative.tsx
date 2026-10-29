import {useEffect,useRef,useState} from 'react'
import {Chess} from 'chess.js'
import Board,{type AnalysisArrow} from './Board'
import MiniBoard from './MiniBoard'
import InfoNote from './InfoNote'
import {api} from './api'
import {useBoardOrientation} from './boardFlip'
import type {Color,Evaluation,Game} from './types'

type Move={uci:string;san:string}
type Hint={level:number;title:string;text?:string;squares?:string[];move?:string;san?:string;feared?:string;threat?:string;detail?:string;continuation?:string;line?:string[];kind?:string;status?:string|null}
type Attempt={id:number;move:string;san:string;verdict:string;label:string;helpLevel:number;message:string;reply:string|null;evaluation?:Evaluation;lossCp?:number|null;scoreDrop?:number}
type Alternative={move:string;san:string;verdict:string;label:string;lossCp:number|null;scoreDrop:number;evaluation:{cp:number;mate:number|null;san:string[]}}
type Classification={declared:string;inferred:string;inferredReason:string;corrected:string|null;final:string;area:string}
export type Episode={id:string;role:string;roleLabel:string;parentId:string|null;origin:string;reasoningOrigin:string|null;exposure:string;status:string;createdAt:string;
  fen:string;color:Color;moveNumber:number;ply:number|null;gameId:string|null;gameNumber?:number|null;gameTitle:string|null;gameSource:string|null;onlineMaia:boolean;legalMoves:string[];
  playedMove:Move|null;reasoning:{threat:string|null;threatSan:string|null;threatNone:boolean;threatText:string;consideredSan:string[];consideredNone:boolean}|null;
  analysisReady:boolean;helpLevel:number;hints:Hint[];hintSource:string|null;attempts:Attempt[];found:{move?:string;san?:string;verdict?:string;level:number;revealed?:boolean;explanation?:Hint&{direction:string}|null}|null;
  prediction:{san:string;matches:boolean;strong:boolean;engineReply:string|null;message:string}|null;reflection:{considered:string;detail:string;note:string}|null;
  classification:Classification|null;outcome:string|null;outcomeLabel:string|null;dueAt:string|null;pendingInGame:boolean;assistedGame:boolean;goal:string;
  links:{id:string;role:string;roleLabel:string;status:string;dueAt:string|null;outcome:string|null}[];threatFen:string|null;threatMoves:Move[];playerMoves:Move[];
  solution:{move:string;san:string;direction:string;evaluation:Evaluation;status:string;alternatives:Alternative[];considered:Alternative[];
    engine:{name:string;nodes:number;candidates:number};tempting?:Move|null;earlierPly:number|null}|null;
  feedback?:{verdict:string;label:string;message:string;reply:string|null;san:string;attemptId:number};followups?:Record<string,{id:string|null;message:string}>}
type Item={id:string;role:string;roleLabel:string;origin:string;status:string;createdAt:string;fen:string;color:Color;title:string|null;moveNumber:number;helpLevel:number;outcomeLabel:string|null;dueAt:string|null;ready:boolean}

const levels=['Ricerca autonoma','Domanda sulla minaccia','Direzione della ricerca','Che cosa osservare','Mossa suggerita','Continuazione e spiegazione']
export const labels:Record<string,string>={not_considered:'Alternativa non considerata',rejected_reply:'Scartata per una risposta avversaria',threat_inevitable:'Minaccia ritenuta inevitabile',evaluation:'Difficoltà a valutare la posizione risultante',unclear:'Motivo non ancora chiaro'}
const areas:Record<string,string>={search:'ricerca delle mosse',calculation:'calcolo delle risposte',evaluation:'valutazione',unclear:'da chiarire'}
const details=[['reply','Ho visto come rispondere alla replica che temevo'],['threat','La minaccia non era inevitabile'],['evaluation','La posizione dopo è migliore di quanto pensassi'],['resource','Ho notato una risorsa di un pezzo'],['unclear','Non mi è ancora chiaro']] as const
const phases:Record<string,string>={marked:'Segnato',reasoning:'Prima della ricerca',searching:'Ricerca in corso',reflecting:'Dopo la soluzione',complete:'Completato'}
export function score(e:{cp:number;mate:number|null}){return e.mate!=null?`matto ${e.mate>0?'a tuo favore':'contro di te'} in ${Math.abs(e.mate)}`:`${e.cp>=0?'+':''}${(e.cp/100).toFixed(2).replace('.',',')}`}
const when=(iso:string)=>new Date(iso).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'})
function play(fen:string,moves:string[]){const board=new Chess(fen);for(const m of moves)board.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]});return board}

export default function FindAlternative({episodeId,onEpisode,embedded=false,onClose,onReview,onPlayFrom,onApplied}:{episodeId:string|null;onEpisode:(id:string|null)=>void;embedded?:boolean;onClose?:()=>void;onReview:(gameId:string,ply:number)=>void;onPlayFrom:(fen:string,color:Color,title:string)=>void;onApplied?:(game:Game)=>void}){
  const [items,setItems]=useState<Item[]|null>(null)
  const [episode,setEpisode]=useState<Episode|null>(null)
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[retry,setRetry]=useState<(()=>void)|null>(null)
  const [picking,setPicking]=useState<'threat'|'considered'|'prediction'|null>(null)
  const [threat,setThreat]=useState<Move|null|undefined>(undefined),[threatText,setThreatText]=useState('')
  const [considered,setConsidered]=useState<Move[]>([]),[noneConsidered,setNoneConsidered]=useState(false)
  const [reflection,setReflection]=useState({considered:'',detail:'',note:''})
  const [step,setStep]=useState(0)
  const operation=useRef(0)
  const orientation=useBoardOrientation(episode?.color??'w')
  async function list(){try{setItems(await api<Item[]>('/alternatives/episodes'))}catch(e){setError((e as Error).message)}}
  useEffect(()=>{if(!embedded)void list()},[embedded,episode?.status])
  useEffect(()=>{
    setPicking(null);setThreat(undefined);setThreatText('');setConsidered([]);setNoneConsidered(false);setReflection({considered:'',detail:'',note:''});setStep(0)
    if(!episodeId){setEpisode(null);return}
    const token=++operation.current
    api<Episode>('/alternatives/episodes/'+episodeId).then(e=>{if(token===operation.current)setEpisode(e)}).catch(e=>{if(token===operation.current)setError(e.message)})
  },[episodeId])
  // Every request keeps the user's work on the server: a failure offers to repeat the same request.
  async function call(path:string,body:unknown={},after?:(e:Episode)=>void){
    if(!episode)return
    const token=++operation.current
    setBusy(true);setError('');setRetry(null)
    try{const next=await api<Episode>(`/alternatives/episodes/${episode.id}${path}`,body);if(token!==operation.current)return;if(next.status==='reflecting'&&episode.status!=='reflecting')setStep(1);setEpisode(next);after?.(next)}
    catch(e){if(token===operation.current){setError((e as Error).message);setRetry(()=>()=>void call(path,body,after));try{setEpisode(await api<Episode>('/alternatives/episodes/'+episode.id))}catch{/* keep the shown state */}}}
    finally{if(token===operation.current)setBusy(false)}
  }
  async function apply(){
    if(!episode)return
    setBusy(true);setError('')
    try{onApplied?.(await api<Game>(`/alternatives/episodes/${episode.id}/apply`,{}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }

  if(!episode)return <div className="alternative-home">
    {error&&<div className="alert" role="alert">{error}</div>}
    <section className="panel"><span className="eyebrow">COME FUNZIONA</span><h2>Trova un’alternativa</h2>
      <p>Quando ti sembra che tutte le mosse perdano, premi <b>Qui mi sento bloccato</b> durante una partita, oppure <b>Qui mi sentivo bloccato</b> in Rivedi, anche su partite importate da Maia online.</p>
      <ol className="alternative-steps"><li>Dici che cosa temi e quali mosse hai considerato.</li><li>Cerchi da solo una mossa che tenga la partita: ne vanno bene più di una.</li><li>Se serve, chiedi aiuti progressivi: prima domande e direzioni, poi un pezzo da osservare, infine la mossa.</li><li>Dopo la soluzione racconti che cosa l’ha resa convincente; la posizione torna in ripasso, con casi simili e controesempi verificati.</li></ol>
      <InfoNote summary="Chi decide che cosa">Stockfish verifica ogni mossa e continuazione. Gli indizi nascono da fatti controllati sulla scacchiera; il tutor, se configurato, li riformula e ogni riferimento viene verificato. Maia non giudica la correttezza.</InfoNote>
    </section>
    {!items?<p role="status">Caricamento…</p>:([['Da esaminare',items.filter(i=>i.status!=='complete'&&!i.dueAt)],['Pronti oggi',items.filter(i=>i.ready)],['In programma',items.filter(i=>i.dueAt&&!i.ready&&i.status!=='complete')],['Completati',items.filter(i=>i.status==='complete').slice(0,12)]] as const).map(([title,group])=>
      <section className="panel" key={title}><div className="section-head"><h3>{title}</h3><span className="count-chip">{group.length}</span></div>
        {group.length?<div className="alternative-list">{group.map(i=><button key={i.id} onClick={()=>onEpisode(i.id)}><MiniBoard fen={i.fen} orientation={i.color}/><span><strong>{i.roleLabel} · {phases[i.status]}</strong><small>{i.title??'Posizione'} · mossa {i.moveNumber} · {i.origin==='live'?'segnato dal vivo':i.origin==='retrospective'?'segnato in revisione':'programmato'}</small>
          <small>{i.outcomeLabel?`${i.outcomeLabel} · aiuto ${i.helpLevel}/5`:i.dueAt?`Da ${when(i.dueAt)}`:when(i.createdAt)}</small></span></button>)}</div>:<p className="empty-text">{title==='Da esaminare'?'Nessun momento segnato: usa il pulsante durante una partita o in Rivedi.':'Nessuna posizione.'}</p>}
      </section>)}
  </div>

  const e=episode, solved=e.status==='reflecting'||e.status==='complete'
  const hint4=e.hints.find(h=>h.level===4), hint3=e.hints.find(h=>h.level===3), final=e.found?.explanation??e.hints.find(h=>h.level===5)
  const solution=e.solution
  const line=solved&&solution?(final?.line??[solution.move]):[]
  const shownLine=line.slice(0,step)
  const board=picking==='threat'&&e.threatFen?new Chess(e.threatFen):picking==='prediction'&&hint4?.move?play(e.fen,[hint4.move]):solved&&shownLine.length?play(e.fen,shownLine):new Chess(e.fen)
  const legal=picking==='threat'?e.threatMoves.map(m=>m.uci):picking==='considered'?e.playerMoves.map(m=>m.uci):picking==='prediction'?board.moves({verbose:true}).map(m=>m.from+m.to+(m.promotion??'')):e.status==='searching'&&e.analysisReady?e.legalMoves:[]
  const interactive=!busy&&legal.length>0
  const arrows:AnalysisArrow[]=e.status==='searching'&&hint4?.move&&!picking?[{move:hint4.move,source:'stockfish',rank:1}]:[]
  function boardMove(uci:string){
    if(picking==='threat'){setThreat(e.threatMoves.find(m=>m.uci===uci)??null);setPicking(null)}
    else if(picking==='considered'){const m=e.playerMoves.find(m=>m.uci===uci);if(m&&!considered.some(c=>c.uci===uci))setConsidered(c=>[...c,m].slice(0,8));setNoneConsidered(false)}
    else if(picking==='prediction'){setPicking(null);void call('/prediction',{move:uci})}
    else void call('/attempts',{move:uci,version:e.attempts.length})
  }
  const latest=e.attempts.at(-1)
  const concession=e.status==='searching'&&latest?.verdict==='concession'?latest:null
  const answered=(threat!==undefined||threatText.trim()||!e.threatFen)&&(considered.length||noneConsidered)
  const side=e.color==='w'?'il Bianco':'il Nero', opponent=e.color==='w'?'il Nero':'il Bianco'
  const source=e.gameId?<>{e.gameNumber!=null&&`#${e.gameNumber} · `}{e.gameTitle??'Partita'}{e.onlineMaia&&' · Maia online'}</>:<>{e.gameTitle??'Posizione verificata'}</>
  const boardNote=picking==='threat'?`Muovi un pezzo di ${opponent}: la mossa che temi.`:picking==='considered'?'Muovi le mosse che avevi considerato, una alla volta.':picking==='prediction'?`Muovi la risposta che ti aspetti da ${opponent}.`:solved?'Soluzione sulla scacchiera dell’esercizio: usa ◀ ▶ per la continuazione.':e.status==='searching'?'Muovi un pezzo per proporre la tua alternativa.':'Scacchiera dell’esercizio.'

  return <div className={`training-layout layout-alternative ${embedded?'alternative-embedded':''}`}>
    <section className="board-column">
      <div className="player-row"><span className="avatar">⟡</span><div><strong>Muove {side} · mossa {e.moveNumber}</strong><small>{source}</small></div></div>
      <Board fen={board.fen()} orientation={orientation} legalMoves={legal} interactive={interactive} onMove={boardMove} analysisArrows={arrows}
        highlights={e.status==='searching'&&!picking?hint3?.squares:undefined} lastMove={solved&&shownLine.length?shownLine.at(-1):undefined} animateMove/>
      <p className="footnote">{boardNote} Le mosse qui non cambiano la partita originale.</p>
      {solved&&line.length>0&&<div className="board-toolbar alternative-steps-bar"><button aria-label="Posizione iniziale" disabled={!step} onClick={()=>setStep(0)}>⏮</button><button aria-label="Mossa precedente" disabled={!step} onClick={()=>setStep(s=>s-1)}>◀</button>
        <span className="review-step">{step?`${step} / ${line.length}`:'Posizione dell’esercizio'}</span><button aria-label="Mossa successiva" disabled={step>=line.length} onClick={()=>setStep(s=>s+1)}>▶</button></div>}
    </section>
    <aside className="coach-column">
      {error&&<div className="alert" role="alert">{error}{retry&&<button disabled={busy} onClick={retry}>Riprova</button>}</div>}
      <section className="panel alternative-header" aria-label="Esercizio">
        <div className="section-head"><span className="eyebrow">TROVA UN’ALTERNATIVA · {e.roleLabel.toUpperCase()}</span><span className="chip">{phases[e.status]}</span></div>
        <h2>{e.goal}</h2>
        <p className="muted">Origine: {source}{e.ply!=null&&` · mossa ${e.moveNumber}`} · {e.origin==='live'?'segnato durante la partita':e.origin==='retrospective'?'segnato rivedendo la partita':'programmato'}{e.reasoningOrigin&&` · risposte ${e.reasoningOrigin==='live'?'raccolte dal vivo':'ricostruite dopo'}`}</p>
        <div className="help-meter" role="img" aria-label={`Aiuto ricevuto: livello ${e.helpLevel} di 5`}>{levels.map((label,i)=><span key={label} className={i<=e.helpLevel&&i>0?'used':''} title={label}/>)}<small>Aiuto ricevuto: {e.helpLevel} / 5{e.helpLevel?` · ${levels[e.helpLevel]}`:''}</small></div>
        <div className="row">
          {embedded&&onClose&&<button className="primary" onClick={onClose}>Torna alla partita</button>}
          {!embedded&&<button onClick={()=>onEpisode(null)}>← Tutti gli episodi</button>}
          {e.gameId&&e.ply!=null&&<button disabled={busy} onClick={()=>onReview(e.gameId!,e.ply!)}>Apri nell’analisi</button>}
          {solved&&<button className="play-from" disabled={busy} onClick={()=>onPlayFrom(e.fen,e.color,`Trova un’alternativa · ${e.gameTitle??'posizione'} · ${e.moveNumber}${e.color==='w'?'.':'…'}`)}>Gioca da qui col {e.color==='w'?'Bianco':'Nero'}</button>}
        </div>
        {e.origin==='live'&&e.pendingInGame&&<p className="footnote">La partita aspetta questa mossa e il tempo di riflessione continua a contare come prima. Aiuti e verifiche rendono assistita questa decisione; la sola segnalazione no.</p>}
      </section>

      {e.status==='marked'&&<section className="panel"><h3>Momento segnato</h3><p>Nessun aiuto mostrato. Quando vuoi, ragiona sulla posizione: le risposte verranno registrate come ricostruite dopo, se la partita è andata avanti.</p>
        <button className="primary" disabled={busy} onClick={()=>void call('/open')}>Aiutami a ragionare</button></section>}

      {e.status==='reasoning'&&<section className="panel alternative-questions" aria-label="Prima della ricerca"><span className="eyebrow">PRIMA DI QUALSIASI CONSIGLIO</span>
        <fieldset><legend>Che cosa temi che possa fare l’avversario?</legend>
          {e.threatFen?<><div className="row">{threat?<span className="chip">Temi <b>{threat.san}</b></span>:threat===null?<span className="chip">Nessuna minaccia</span>:null}
            <button aria-pressed={picking==='threat'} onClick={()=>setPicking(picking==='threat'?null:'threat')}>{picking==='threat'?'Annulla':'Indica sulla scacchiera'}</button>
            <button aria-pressed={threat===null} onClick={()=>{setThreat(null);setPicking(null)}}>Non ne vedo nessuna</button></div>
            <input aria-label="Descrivi la minaccia in breve" maxLength={300} placeholder="Oppure in breve, per esempio: «mi prende la donna»" value={threatText} onChange={ev=>setThreatText(ev.target.value)}/></>
            :<p className="muted">Sei sotto scacco: la minaccia è già sulla scacchiera.</p>}
        </fieldset>
        <fieldset><legend>Quali mosse hai considerato?</legend>
          <div className="row">{considered.map(m=><button key={m.uci} className="chip" aria-label={`Togli ${m.san}`} onClick={()=>setConsidered(c=>c.filter(x=>x.uci!==m.uci))}>{m.san} ×</button>)}
            <button aria-pressed={picking==='considered'} onClick={()=>setPicking(picking==='considered'?null:'considered')}>{picking==='considered'?'Fatto':'Indica sulla scacchiera'}</button>
            <button aria-pressed={noneConsidered} onClick={()=>{setNoneConsidered(true);setConsidered([]);setPicking(null)}}>Non ne vedo nessuna</button></div>
        </fieldset>
        <button className="primary" disabled={busy||!answered} onClick={()=>void call('/reasoning',{threat:threat?.uci??null,threat_none:threat===null,threat_text:threatText,considered:considered.map(m=>m.uci),considered_none:noneConsidered})}>{busy?'Stockfish analizza la posizione…':'Inizia la ricerca'}</button>
        {!answered&&<p className="footnote">Bastano due risposte brevi; «Non ne vedo nessuna» è una risposta valida.</p>}
      </section>}

      {e.status==='searching'&&<section className="panel alternative-search" aria-label="Ricerca">
        {!e.analysisReady?<><p>L’analisi della posizione non è pronta. Le tue risposte sono salvate.</p><button className="primary" disabled={busy} onClick={()=>void call('/analyze')}>Riprova l’analisi</button></>:<>
          <h3>{busy?'Verifica…':e.feedback?`${e.feedback.label}: ${e.feedback.san}`:levels[0]}</h3>
          <p role="status" aria-live="polite">{e.feedback?.message??(latest?`Ultimo tentativo: ${latest.san} · ${latest.label}. ${latest.message}`:'Cerca una mossa che mantenga ragionevoli possibilità. Non serve la prima scelta del motore: più alternative possono andare bene.')}</p>
          {concession&&<button disabled={busy} onClick={()=>void call('/accept',{attempt_id:concession.id})}>Accetto {concession.san} e passo alla spiegazione</button>}
          {e.hints.map(h=><div key={h.level} className={`alternative-hint hint-level-${h.level}`}><strong>Aiuto {h.level} · {h.title}</strong><p>{h.text}</p></div>)}
          {hint4&&!e.prediction&&<button aria-pressed={picking==='prediction'} onClick={()=>setPicking(picking==='prediction'?null:'prediction')}>{picking==='prediction'?'Annulla':`Prevedi la risposta dopo ${hint4.san}`}</button>}
          {e.prediction&&<p className="alternative-prediction">Hai previsto {e.prediction.san}. {e.prediction.message}{!e.prediction.matches&&e.prediction.engineReply?` Risposta principale di Stockfish: ${e.prediction.engineReply}.`:''}</p>}
          <div className="row">{e.helpLevel<5&&<button disabled={busy} onClick={()=>void call('/hint',{level:e.helpLevel+1})}>{e.helpLevel===4?'Mostra continuazione e spiegazione':`Chiedi un aiuto: ${levels[e.helpLevel+1].toLowerCase()}`}</button>}</div>
          {e.attempts.length>0&&<details><summary>Tentativi ({e.attempts.length})</summary><ul className="alternative-attempts">{e.attempts.map(a=><li key={a.id}><b>{a.san}</b> · {a.label}{a.helpLevel?` · dopo l’aiuto ${a.helpLevel}`:''}</li>)}</ul></details>}
          {e.hintSource==='tutor'&&<p className="footnote">Indizi riformulati dal tutor e controllati sulla posizione.</p>}
        </>}
      </section>}

      {solved&&solution&&<section className="panel alternative-solution" aria-label="Soluzione">
        <span className="eyebrow">{e.found?.revealed?'SOLUZIONE MOSTRATA':e.found?.verdict==='concession'?'MOSSA ACCETTATA CON UNA CONCESSIONE':'ALTERNATIVA TROVATA'}</span>
        <h2>{e.found?.san??solution.san} {final?.kind&&<span className={`kind-tag kind-${final.kind}`}>{final.kind==='tactical'?'Tattica':final.kind==='positional'?'Posizionale':'Tattica e posizione'}</span>}</h2>
        {e.found?.san&&e.found.san!==solution.san&&<p className="muted">La spiegazione riguarda la tua mossa. Stockfish preferisce {e.found.verdict==='valid'?'di poco ':''}{solution.san}.</p>}
        {final&&<ol className="alternative-explanation"><li><b>Che cosa temevi.</b> {final.feared}</li><li><b>Che cosa minacciava davvero l’avversario.</b> {final.threat}</li><li><b>Il dettaglio decisivo.</b> {final.detail}</li><li><b>La prova.</b> {final.continuation}</li></ol>}
        {final?.status&&<p className="alternative-lost">{final.status}{solution.earlierPly!=null&&e.gameId&&<button className="quiet" onClick={()=>onReview(e.gameId!,solution.earlierPly!)}>Rivedi la tua mossa precedente</button>}</p>}
        {solution.tempting&&<p>Qui {solution.tempting.san} usa la stessa idea dell’episodio di partenza, ma Stockfish la respinge: è il controesempio da ricordare.</p>}
        {e.playedMove&&<p className="muted">In partita hai giocato {e.playedMove.san}.</p>}
        <details><summary>Alternative verificate e tuoi tentativi</summary>
          <ul className="alternative-attempts">{solution.alternatives.map(a=><li key={a.move}><b>{a.san}</b> · {a.label} · {score(a.evaluation)}</li>)}</ul>
          {e.attempts.length>0&&<ul className="alternative-attempts">{e.attempts.map(a=><li key={a.id}>Tuo tentativo <b>{a.san}</b> · {a.label}{a.evaluation?` · ${score(a.evaluation)}`:''}</li>)}</ul>}
          <p className="footnote">Valori dal tuo punto di vista. {solution.engine.name}, {solution.engine.nodes.toLocaleString('it-IT')} nodi per mossa, {solution.engine.candidates} candidate a confronto: è una stima, non una dimostrazione.</p>
        </details>
        {e.origin==='live'&&e.pendingInGame&&<button className="primary" disabled={busy} onClick={()=>void apply()}>Gioca {e.found?.san??solution.san} nella partita</button>}
      </section>}

      {e.status==='reflecting'&&<section className="panel alternative-questions" aria-label="Dopo la soluzione"><span className="eyebrow">CAPIRE L’ILLUMINAZIONE</span>
        <fieldset><legend>Questa mossa non ti era venuta in mente oppure l’avevi scartata?</legend><div className="row">{([['not_considered','Non mi era venuta in mente'],['rejected','L’avevo vista ma scartata'],['unsure','Non ne sono sicuro']] as const).map(([id,label])=>
          <button key={id} aria-pressed={reflection.considered===id} onClick={()=>setReflection(r=>({...r,considered:id}))}>{label}</button>)}</div></fieldset>
        <fieldset><legend>Quale dettaglio ora la rende convincente?</legend><div className="row">{details.map(([id,label])=><button key={id} aria-pressed={reflection.detail===id} onClick={()=>setReflection(r=>({...r,detail:id}))}>{label}</button>)}</div></fieldset>
        <textarea aria-label="Nota facoltativa" maxLength={500} placeholder="Nota facoltativa" value={reflection.note} onChange={ev=>setReflection(r=>({...r,note:ev.target.value}))}/>
        <button className="primary" disabled={busy||!reflection.considered||!reflection.detail} onClick={()=>void call('/reflection',reflection)}>Salva e programma il ripasso</button>
      </section>}

      {e.status==='complete'&&<section className="panel" aria-label="Esito"><span className="eyebrow">ESITO</span><h2>{e.outcomeLabel}</h2>
        {e.classification&&<><p>Difficoltà: <b>{labels[e.classification.final]}</b> <span className="muted">({areas[e.classification.area]}{e.classification.corrected?', corretta da te':', dalla tua risposta'})</span></p>
          <p className="muted">Ipotesi del sistema, da verificare: {labels[e.classification.inferred]}. {e.classification.inferredReason}</p>
          <label className="field-label">Correggi la classificazione<select aria-label="Correggi la classificazione" value={e.classification.final} disabled={busy} onChange={ev=>void call('/classification',{label:ev.target.value})}>{Object.entries(labels).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label></>}
        {e.links.length>0&&<ul className="alternative-links">{e.links.map(l=><li key={l.id}><button className="quiet" onClick={()=>onEpisode(l.id)}>{l.roleLabel}</button> {l.status==='complete'?'completato':l.dueAt?`da ${when(l.dueAt)}`:''}</li>)}</ul>}
        {!embedded&&<button disabled={busy||['analog','counterexample'].every(r=>e.links.some(l=>l.role===r))} onClick={()=>void call('/followups',{kinds:['analog','counterexample']})}>{busy?'Ricerca e verifica con Stockfish…':'Cerca una posizione analoga e un controesempio'}</button>}
        {e.followups&&Object.entries(e.followups).map(([kind,r])=><p key={kind} className="footnote">{kind==='analog'?'Posizione analoga':'Controesempio'}: {r.message}</p>)}
        <p className="footnote">Il ripasso è più vicino quando hai avuto bisogno di più aiuto. Una ripetizione conta a parte: rivedere una soluzione non equivale a trovarla da solo in una posizione nuova.</p>
      </section>}
    </aside>
  </div>
}
