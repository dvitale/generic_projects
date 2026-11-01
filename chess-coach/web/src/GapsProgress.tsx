import {useEffect,useState} from 'react'
import InfoNote from './InfoNote'
import {api} from './api'
import {solutionLabels} from './FailureDiagnosis'
import {themeLabel} from './Problems'
import {stageLabels,type StudyPathView} from './StudyPath'

interface Gap {key:string;source:'puzzle'|'problem';family:'method'|'tactic'|'theory';status:'confirmed'|'watch';total:number;solved:number;rate:number;expected:number;missing:number;theme:string|null}
interface Overview {gaps:Gap[];path:StudyPathView|null;passed:{gap:string;closed_at:string}[];problemsAvailable:boolean;unclassified:number;rules:{watch:number;confirm:number;failures:number;drop:number;window:number}}

const families:Record<Gap['family'],{label:string;note:string}>={
  method:{label:'Metodo di ricerca',note:'Non è un motivo da imparare: è un tipo di mossa che non cerchi.'},
  tactic:{label:'Motivo tattico',note:'Uno schema che non riconosci ancora.'},
  theory:{label:'Teoria · ipotesi',note:'Lettura basata su fase e materiale: può essere anche tattica dentro un finale.'},
}
const sources={puzzle:'Puzzle',problem:'Problemi'}
const pct=(x:number)=>`${Math.round(x*100)}%`

export function gapLabel(key:string){
  const [kind,name]=key.split(':')
  if(kind==='kind')return solutionLabels[name as keyof typeof solutionLabels]?.title??name
  if(kind==='phase')return 'Finali con poco materiale'
  return themeLabel(name)
}

/** Progressi: the groups of positions solved clearly less often than expected, and the study path for one of them. */
export default function GapsProgress({onStudy}:{onStudy:()=>void}){
  const [data,setData]=useState<Overview|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  useEffect(()=>{let stale=false;api<Overview>('/gaps').then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[])
  async function begin(gap:string){
    setBusy(true);setError('')
    try{await api('/study-paths',{gap});onStudy()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  const confirmed=data?.gaps.filter(g=>g.status==='confirmed')??[],watch=data?.gaps.filter(g=>g.status==='watch')??[]
  const row=(g:Gap)=><li key={g.key} className="gap-row">
    <div className="bar-label"><span><b>{gapLabel(g.key)}</b> <small className="muted">{families[g.family].label} · {sources[g.source]}</small></span>
      <b>{g.solved} / {g.total} <small>atteso {pct(g.expected)}</small></b></div>
    <div className="bar-track" aria-hidden="true"><span style={{width:`${Math.max(2,g.rate*100)}%`}}/></div>
    {g.status==='confirmed'?<p className="footnote">{families[g.family].note}{' '}
      {!g.theme?'Per questo tipo di mossa non ci sono problemi Lichess adatti: allenalo in Trova un’alternativa.'
      :data!.path?null:!data!.problemsAvailable?'Il percorso usa i problemi Lichess: installali con make puzzles.'
      :<button disabled={busy} onClick={()=>void begin(g.key)}>Inizia il percorso di studio</button>}</p>
    :<p className="footnote">Da osservare: servono ancora {g.missing} {g.missing===1?'caso':'casi'} per confermarla.</p>}
  </li>
  return <section className="panel gaps-progress" aria-label="Lacune ricorrenti"><span className="eyebrow">DOVE TI BLOCCHI PIÙ SPESSO</span><h2>Lacune ricorrenti</h2>
    {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Caricamento…</p>}
    {data?.path&&<p className="notice">Percorso in corso: <b>{data.path.lesson.title}</b> · {stageLabels[data.path.stage]}. <button onClick={onStudy}>Continua in Problemi</button></p>}
    {data&&!data.gaps.length&&<p>Nessuna lacuna evidente. Compare qui un gruppo di posizioni (tipo di mossa, tema o finali) che risolvi al primo tentativo molto meno spesso del previsto, da {data.rules.watch} casi in su.</p>}
    {confirmed.length>0&&<><h3>Confermate</h3><ul className="bar-list">{confirmed.map(row)}</ul></>}
    {watch.length>0&&<><h3>Da osservare</h3><ul className="bar-list">{watch.map(row)}</ul></>}
    {!!data?.unclassified&&<p className="footnote">{data.unclassified} {data.unclassified===1?'puzzle è':'puzzle sono'} ancora da classificare con Stockfish: lo faccio ora in background, ricarica la pagina fra qualche minuto.</p>}
    {!!data?.passed.length&&<p className="footnote">Superate: {data.passed.map(p=>gapLabel(p.gap)).join(', ')}.</p>}
    {data&&<InfoNote summary="Come si riconosce una lacuna"><p>Conta solo il primo tentativo senza indizi né soluzione, sulle ultime {data.rules.window} sessioni di Puzzle e di Problemi. Nei Puzzle il tipo di soluzione lo classifica Stockfish (forzante, tranquilla con minaccia, profilassi, miglioramento) e l’atteso è la tua media; nei Problemi il gruppo è un tema Lichess e l’atteso viene dal rating tuo e del problema.</p><p>Una lacuna è confermata con almeno {data.rules.confirm} casi, {data.rules.failures} non risolti e un risultato almeno {Math.round(data.rules.drop*100)} punti sotto l’atteso; da {data.rules.watch} casi è solo da osservare. I problemi giocati dentro un percorso non contano, e una lacuna superata riparte da zero.</p></InfoNote>}
  </section>
}
