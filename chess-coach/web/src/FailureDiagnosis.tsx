import {useEffect,useState} from 'react'
import Board from './Board'
import {api} from './api'
import type {Color,Evaluation} from './types'

export type DiagnosisKind='puzzle'|'problem'|'prevention'
type Move={uci:string;san:string}
type Context={existing:Diagnosis|null;fen?:string;color?:Color;playerMoves?:Move[];tried?:Move[];threatFen?:string|null;threatMoves?:Move[]}
type Answer={assessment:string;confidence:string;fearedLost:boolean;threat:string|null;candidate:string|null;candidateReason:string|null;obstacle?:string|null;note:string}
type Solution={kind:'forcing'|'quiet_threat'|'prophylaxis'|'improvement';san:string;line:string[];gain:{ply:number;san:string[]}|null;forcing?:string[];
  threat?:{san:string;evaluation:Evaluation};stopped?:{san:string;before:Evaluation;after:Evaluation};facts?:{piece:string;reach:[number,number];openRooks:string[]|null;center:string[]|null}}
type Evidence={best:Evaluation;engineBand:string;bandGap:number;tried?:string[];
  threat:{real:boolean;evaluation:Evaluation;san:string|null}|null;
  statedThreat?:{san:string;evaluation:Evaluation;concrete:boolean};
  candidate?:{san:string;evaluation:Evaluation;sound:boolean};solution?:Solution|null}
export type Diagnosis={id:string;kind:DiagnosisKind;answer:Answer;evidence:Evidence;search:string;reading:string[];ruleVersion:number}

export const bands=[['much_worse','Forte svantaggio'],['worse','Svantaggio'],['equal','Circa equilibrio'],['better','Vantaggio'],['much_better','Forte vantaggio']] as const
export const diagnosisLabels:Record<string,{title:string;practice:string}>={
  missed_solution:{title:'Soluzione non vista',practice:'Allena la ricerca delle candidate: scacchi, catture e minacce, per entrambi i colori, prima di scegliere.'},
  rejected_solution:{title:'Vista ma scartata',practice:'Errore di calcolo o timore infondato: prima di scartare una mossa, gioca la risposta che temi fino a una posizione tranquilla.'},
  pessimistic:{title:'Valutazione troppo pessimista',practice:'Cerca le tue risorse prima di rinunciare: l’esercizio “Valuta la posizione” allena proprio questo.'},
  optimistic:{title:'Valutazione troppo ottimista',practice:'Controlla le risposte forzanti dell’avversario prima di considerarti al sicuro.'},
  ignored_threat:{title:'Minaccia non vista',practice:'Chiediti a ogni mossa “cosa farebbe l’avversario se potesse muovere ora?”. Blunder prevention allena questo controllo.'},
  phantom_threat:{title:'Minaccia fantasma',practice:'Verifica la minaccia che temi giocandola davvero: spesso c’è una difesa o non porta a niente.'},
  accurate:{title:'Lettura corretta',practice:'Valutazione e minacce erano giuste: il punto debole è il calcolo della sequenza. Allenati con problemi a più mosse.'},
}
const reasons=[['material','Mi sembrava perdere materiale'],['mate','Temevo un matto o un attacco'],['calculation','Non riuscivo a calcolarla fino in fondo'],['inconclusive','Mi sembrava inconcludente'],['other','Altro motivo']] as const
const obstacles=[['inconclusive','Le candidate erano inconcludenti: niente scacchi, catture o minacce utili'],['no_plan','Non sapevo quale piano seguire'],['calculation','Non riuscivo a calcolare le varianti'],['danger','Temevo le risposte dell’avversario']] as const
export const solutionLabels:Record<Solution['kind'],{title:string;practice:string}>={
  forcing:{title:'Soluzione forzante',practice:'Prima di valutare le mosse tranquille elenca tutti gli scacchi, le catture e le promozioni, anche quelli che sembrano perdere materiale, e gioca ciascuno fino alla risposta forzata.'},
  quiet_threat:{title:'Mossa tranquilla con una minaccia',practice:'Quando nessuna mossa forzante funziona, chiediti: quale mossa mi darebbe uno scacco, una cattura o un matto alla mossa successiva? Una minaccia che l’avversario deve parare vale quanto una mossa forzante.'},
  prophylaxis:{title:'Profilassi',practice:'Quando sei in vantaggio e nulla sembra funzionare, chiediti cosa giocherebbe l’avversario se toccasse a lui, e impediscilo: spesso l’unico modo di perdere il vantaggio è il suo controgioco.'},
  improvement:{title:'Miglioramento posizionale',practice:'Senza tattiche immediate, cerca il tuo pezzo peggiore e chiediti dove sarebbe più attivo; confronta le candidate guardando la posizione dopo 3–4 mosse, non dopo la prima.'},
}
const pieceNames:Record<string,string>={K:'il re',Q:'la donna',R:'la torre',B:'l’alfiere',N:'il cavallo',P:'il pedone'}
const bandLabel=(id:string)=>bands.find(b=>b[0]===id)?.[1]??id

export function formatEvaluation(e:Evaluation){
  if(e.mate!=null)return `matto ${e.mate>0?'a tuo favore':'contro di te'} in ${Math.abs(e.mate)}`
  return `${e.cp>0?'+':''}${(e.cp/100).toFixed(2)}`
}

const sanList=(sans:string[])=>sans.length>1?`${sans.slice(0,-1).join(', ')} e ${sans.at(-1)}`:sans[0]

function explain(d:Diagnosis,label:string){
  const e=d.evidence,tried=e.tried??[]
  const played=tried.length?`Hai provato ${sanList(tried)}, che non ${tried.length>1?'risolvono':'risolve'}`:''
  switch(label){
    case 'missed_solution':
      if(e.candidate)return `${played?`${played}; avevi considerato anche`:'Avevi considerato'} ${e.candidate.san} (${formatEvaluation(e.candidate.evaluation)}), che non risolve: scartarla era giusto, ma la mossa buona non era fra le tue candidate.`
      return played?`${played}: la mossa buona non era fra le tue candidate.`:'Non avevi una candidata: la mossa buona non è entrata nella tua ricerca.'
    case 'rejected_solution':return `Avevi visto ${e.candidate!.san}, che funzionava (${formatEvaluation(e.candidate!.evaluation)}), ma l’hai scartata${d.answer.candidateReason?`: «${reasons.find(r=>r[0]===d.answer.candidateReason)?.[1].toLowerCase()}»`:''}${tried.length?`, e hai giocato ${sanList(tried)}`:''}.`
    case 'pessimistic':case 'optimistic':return `Hai indicato «${bandLabel(d.answer.assessment)}»${d.answer.fearedLost?' e la davi per persa':''}; Stockfish: «${bandLabel(e.engineBand)}» (${formatEvaluation(e.best)}).`
    case 'ignored_threat':return `Se l’avversario potesse muovere, ${e.threat?.san} porterebbe la valutazione a ${formatEvaluation(e.threat!.evaluation)}.`
    case 'phantom_threat':return `Dopo ${e.statedThreat?.san} la valutazione resterebbe ${formatEvaluation(e.statedThreat!.evaluation)}: la minaccia non era concreta.`
    default:return `Hai indicato «${bandLabel(d.answer.assessment)}», in linea con Stockfish (${formatEvaluation(e.best)})${e.statedThreat?.concrete?`, e la minaccia ${e.statedThreat.san} era reale`:''}.`
  }
}

function describeSolution(d:Diagnosis,s:Solution){
  const tried=d.evidence.tried??[],gain=s.gain?` Il guadagno concreto arriva alla semimossa ${s.gain.ply}: ${s.gain.san.join(' ')}.`:''
  let text=''
  switch(s.kind){
    case 'forcing':text=`${s.san} è ${s.forcing?.includes('check')?'uno scacco':s.forcing?.includes('capture')?'una cattura':'una promozione'}: una mossa forzante.${gain}`;break
    case 'quiet_threat':text=`${s.san} non dà scacco e non cattura, ma minaccia ${s.threat!.san} (${formatEvaluation(s.threat!.evaluation)} se l’avversario non reagisse): l’avversario deve rispondere a quella minaccia.${gain}`;break
    case 'prophylaxis':text=`${s.san} toglie all’avversario ${s.stopped!.san}: con una mossa libera la valutazione scenderebbe a ${formatEvaluation(s.stopped!.before)}, dopo ${s.san} resta ${formatEvaluation(s.stopped!.after)}.${gain}`;break
    case 'improvement':{const f=s.facts!,more=[f.reach[1]-f.reach[0]>=3?`la portata dei tuoi pezzi passa da ${f.reach[0]} a ${f.reach[1]} case`:'',f.openRooks?.length?`torre su colonna aperta (${f.openRooks.join(', ')})`:'',f.center?.length?`controllo del centro (${f.center.join(', ')})`:''].filter(Boolean)
      text=`${s.san} sposta ${pieceNames[f.piece]??'un pezzo'} senza scacchi, catture o minacce immediate${more.length?`: ${more.join('; ')}`:''}.${gain||` Nella variante di Stockfish (${s.line.slice(0,6).join(' ')}) non c’è guadagno di materiale a breve: il vantaggio è nella posizione.`}`}
  }
  // The player's own account: candidates looked inconclusive, or there was no plan.
  if((d.answer.obstacle==='inconclusive'||d.answer.obstacle==='no_plan')&&d.search==='missed_solution')
    text+=s.kind==='forcing'?` Le tue candidate ti sembravano inconcludenti${tried.length?` (${sanList(tried)})`:''}, ma la soluzione era proprio una mossa forzante che non avevi considerato.`
      :' Non hai trovato la mossa perché, probabilmente, cercavi scacchi, catture e minacce dirette: qui la soluzione è una mossa tranquilla, e va cercata con un’altra domanda.'
  return text
}

function Result({diagnosis}:{diagnosis:Diagnosis}){
  const s=diagnosis.evidence.solution
  // A correct reading leaves the search: the default advice about calculation fits only forcing solutions.
  const practice=(label:string)=>label==='accurate'&&s&&s.kind!=='forcing'?'Valutazione e minacce erano giuste: ti è sfuggito il tipo di mossa, vedi sotto.':diagnosisLabels[label].practice
  return <div className="diagnosis-result">
    <h3>La tua diagnosi</h3>
    <ul className="diagnosis-list">{[diagnosis.search,...diagnosis.reading].map(label=><li key={label} className={`diagnosis-${label}`}>
      <strong>{diagnosisLabels[label].title}</strong><p>{explain(diagnosis,label)}</p><p className="muted">{practice(label)}</p></li>)}
      {s&&<li className={`diagnosis-solution solution-${s.kind}`}><strong>La soluzione: {solutionLabels[s.kind].title.toLowerCase()}</strong><p>{describeSolution(diagnosis,s)}</p><p className="muted">{solutionLabels[s.kind].practice}</p></li>}</ul>
    <p className="footnote">Confronto con Stockfish a budget limitato. La minaccia si misura dando la mossa all’avversario; le fasce sono convenzioni didattiche (equilibrio fra −1 e +1, forte vantaggio da ±3). La diagnosi è salvata e non cambia rating né ripassi.</p>
  </div>
}

export default function FailureDiagnosis({kind,targetId,sessionId,onReveal,onCancel}:{kind:DiagnosisKind;targetId:string;sessionId:string;onReveal:()=>void;onCancel:()=>void}){
  const [context,setContext]=useState<Context|null>(null),[saved,setSaved]=useState<Diagnosis|null>(null)
  const [error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [assessment,setAssessment]=useState(''),[confidence,setConfidence]=useState('uncertain'),[fearedLost,setFearedLost]=useState(false)
  const [threat,setThreat]=useState<Move|null|undefined>(undefined),[candidate,setCandidate]=useState<Move|null>(null)
  const [reason,setReason]=useState(''),[obstacle,setObstacle]=useState(''),[note,setNote]=useState(''),[picking,setPicking]=useState<'threat'|'candidate'|null>(null)
  const ids={kind,target_id:targetId,session_id:sessionId}
  useEffect(()=>{let stale=false
    api<Context>('/diagnoses/context',ids).then(c=>{if(stale)return;setContext(c);if(c.existing)setSaved(c.existing)}).catch(e=>{if(!stale)setError(e.message)})
    return()=>{stale=true}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[kind,targetId,sessionId])

  // In check there is no threat question: the danger is already on the board.
  const ready=Boolean(assessment)&&(threat!==undefined||!context?.threatFen)
  async function submit(){
    if(!ready)return
    setBusy(true);setError('')
    try{
      setSaved(await api<Diagnosis>('/diagnoses',{...ids,assessment,confidence,feared_lost:fearedLost,threat:threat?.uci??null,
        candidate:candidate?.uci??null,candidate_reason:candidate&&reason?reason:null,obstacle:obstacle||null,note}))
      onReveal()
    }catch(e){setError(e instanceof Error?e.message:'Diagnosi non riuscita')}
    finally{setBusy(false)}
  }

  if(saved)return <section className="panel failure-diagnosis" aria-label="Diagnosi dell’errore"><span className="eyebrow">PRIMA DELLA SOLUZIONE</span><Result diagnosis={saved}/></section>
  const opponent=context?.color==='w'?'il Nero':'il Bianco'
  const tried=context?.tried??[]
  // Moves already tried count as candidates on their own: the picker offers only the others.
  const pickMoves=picking==='threat'?context?.threatMoves??[]:(context?.playerMoves??[]).filter(m=>!tried.some(t=>t.uci===m.uci))
  function pick(uci:string){
    const move=pickMoves.find(m=>m.uci===uci)
    if(!move)return
    if(picking==='threat')setThreat(move);else setCandidate(move)
    setPicking(null)
  }
  return <section className="panel failure-diagnosis" aria-label="Diagnosi dell’errore"><span className="eyebrow">PRIMA DELLA SOLUZIONE</span>
    <h2>Cosa vedevi?</h2>
    <p>Poche risposte rapide: Stockfish le confronta con la posizione per capire se il problema è nella valutazione, nelle minacce, nel calcolo o nel tipo di mossa che cercavi.</p>
    {error&&<p role="alert" className="alert">{error}</p>}
    {!context&&!error&&<p role="status">Preparazione…</p>}
    {context&&<>
      <label className="field-label">Come valuti la posizione?<select aria-label="Come valuti la posizione?" value={assessment} onChange={e=>setAssessment(e.target.value)}><option value="">Scegli una fascia</option>{bands.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
      <label className="field-label">Quanto sei sicuro?<select aria-label="Quanto sei sicuro?" value={confidence} onChange={e=>setConfidence(e.target.value)}><option value="uncertain">Poco sicuro</option><option value="moderate">Abbastanza sicuro</option><option value="confident">Molto sicuro</option></select></label>
      <label className="judgment-check"><input type="checkbox" checked={fearedLost} onChange={e=>setFearedLost(e.target.checked)}/>Mi sembra già persa.</label>

      <fieldset className="diagnosis-step"><legend>Quale minaccia temi?</legend>
        {context.threatFen?<>
          <p className="muted">Se {opponent} potesse muovere adesso, cosa giocherebbe?</p>
          <div className="row">{threat?<span className="chip">Minaccia: <b>{threat.san}</b></span>:threat===null?<span className="chip">Nessuna minaccia</span>:null}
            <button aria-pressed={picking==='threat'} onClick={()=>setPicking(picking==='threat'?null:'threat')}>{picking==='threat'?'Annulla':'Indica sulla scacchiera'}</button>
            <button aria-pressed={threat===null} onClick={()=>{setThreat(null);setPicking(null)}}>Non vedo minacce</button></div>
        </>:<p className="muted">Sei sotto scacco: la minaccia è già sulla scacchiera.</p>}
      </fieldset>

      <fieldset className="diagnosis-step"><legend>{tried.length?'Quale altra mossa avevi considerato e scartato?':'Quale mossa avevi considerato e scartato?'}</legend>
        {tried.length>0&&<p className="muted">Le mosse che hai provato contano già fra le tue candidate: <b>{sanList(tried.map(m=>m.san))}</b>.</p>}
        <div className="row">{candidate?<span className="chip">Candidata: <b>{candidate.san}</b></span>:<span className="chip">Nessuna</span>}
          <button aria-pressed={picking==='candidate'} onClick={()=>setPicking(picking==='candidate'?null:'candidate')}>{picking==='candidate'?'Annulla':'Indica sulla scacchiera'}</button>
          {candidate&&<button onClick={()=>{setCandidate(null);setReason('')}}>Nessuna</button>}</div>
        {candidate&&<label className="field-label">Perché l’hai scartata?<select aria-label="Perché l’hai scartata?" value={reason} onChange={e=>setReason(e.target.value)}><option value="">Scegli un motivo</option>{reasons.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>}
      </fieldset>

      <label className="field-label">Cosa ti bloccava? (facoltativa)<select aria-label="Cosa ti bloccava?" value={obstacle} onChange={e=>setObstacle(e.target.value)}><option value="">Scegli, se ti riconosci</option>{obstacles.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>

      {picking&&<div className="diagnosis-board"><p role="status"><b>{picking==='threat'?`Muovi un pezzo di ${opponent}.`:'Muovi la mossa che avevi considerato.'}</b></p>
        <Board fen={picking==='threat'?context.threatFen!:context.fen!} orientation={context.color!} interactive legalMoves={pickMoves.map(m=>m.uci)} onMove={pick}/></div>}

      <label className="field-label">Nota (facoltativa)<textarea maxLength={1000} value={note} onChange={e=>setNote(e.target.value)} placeholder="Cosa avevi in mente?"/></label>
    </>}
    {/* Skipping stays available even when the context cannot be loaded: the solution is never blocked. */}
    <div className="row diagnosis-actions">
      {context&&<button className="primary" disabled={busy||!ready} onClick={()=>void submit()}>{busy?'Confronto con Stockfish…':'Confronta e mostra la soluzione'}</button>}
      <button disabled={busy} onClick={onReveal}>Salta: mostra subito</button>
      <button className="quiet" disabled={busy} onClick={onCancel}>Torna alla posizione</button>
    </div>
    {context&&!ready&&<p className="footnote">Per il confronto servono la valutazione e la risposta sulla minaccia.</p>}
  </section>
}
