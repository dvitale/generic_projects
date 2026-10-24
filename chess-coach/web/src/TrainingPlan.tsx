import {useEffect,useState,useRef,type ReactNode} from 'react'
import {api} from './api'
import InfoNote from './InfoNote'

type Item={kind:'puzzle'|'prevention'|'alternative';id:string;title:string;theme:string;stage:number;new:boolean;readyAt:string}
type Settings={minutes:number;newLimit:number;weekdays:number[];timezone:string}
type Plan={settings:Settings;today:string;activeDay:boolean;target:number;completed:number;successful:number;practice:number;ready:number;waiting:number;total:number;queue:Item[];calendar:{date:string;planned:boolean;due:number}[];nextDue:string|null}
const days=['Lun','Mar','Mer','Gio','Ven','Sab','Dom']
export default function TrainingPlan({onOpen,onImport,judgment,focusJudgment,onFocused}:{onOpen:(kind:Item['kind'],id:string)=>void;onImport:()=>void;judgment:ReactNode;focusJudgment:boolean;onFocused:()=>void}){
  const [plan,setPlan]=useState<Plan|null>(null),[settings,setSettings]=useState<Settings|null>(null)
  const [error,setError]=useState(''),[saving,setSaving]=useState(false)
  const [guideOpened,setGuideOpened]=useState(false)
  const [judgmentOpen,setJudgmentOpen]=useState(false)
  const judgmentRef=useRef<HTMLDetailsElement>(null)
  useEffect(()=>{if(focusJudgment){setJudgmentOpen(true);judgmentRef.current?.scrollIntoView({block:'start'});onFocused()}},[focusJudgment])
  function openGuide(){
    window.open('/api/training-guide/html','_blank','popup=yes,width=1120,height=820,resizable=yes,scrollbars=yes,noopener,noreferrer')
    setGuideOpened(true)
  }
  useEffect(()=>{let stale=false;const refresh=()=>api<Plan>('/training-plan').then(p=>{if(!stale){setPlan(p);setSettings(s=>s??p.settings)}}).catch(e=>{if(!stale)setError(e.message)});void refresh();const timer=setInterval(refresh,30000);return()=>{stale=true;clearInterval(timer)}},[])
  async function save(){if(!settings)return;setSaving(true);setError('');try{const p=await api<Plan>('/training-plan/settings',settings);setPlan(p);setSettings(p.settings)}catch(e){setError((e as Error).message)}finally{setSaving(false)}}
  const ring=plan?Math.min(1,plan.completed/Math.max(1,plan.target)):0
  const busiest=Math.max(1,...(plan?.calendar.map(d=>d.due)??[1]))
  return <div className="schedule-layout">
    {error&&<p className="alert" role="alert">{error}</p>}
    <section className="panel plan-hero"><span className="eyebrow">OGGI</span>
      {!plan?<p role="status">Preparazione del piano…</p>:<div className="plan-hero-body">
        <svg className="progress-ring" viewBox="0 0 120 120" role="img" aria-label={`${plan.completed} verifiche su ${plan.target}`}>
          <circle cx="60" cy="60" r="50" className="ring-track"/>
          <circle cx="60" cy="60" r="50" className="ring-value" style={{strokeDasharray:`${ring*314.16} 314.16`}}/>
          <text x="60" y="58" textAnchor="middle" className="ring-number">{plan.completed}/{plan.target}</text>
          <text x="60" y="78" textAnchor="middle" className="ring-label">verifiche</text>
        </svg>
        <div className="plan-hero-text">
          <h2>{!plan.activeDay?'Oggi è un giorno di pausa':plan.completed>=plan.target?'Obiettivo di oggi completato':plan.queue.length?`${plan.queue.length} esercizi da fare`:'Nessun esercizio in programma'}</h2>
          <p>{plan.completed} / {plan.target} verifiche oggi · {plan.successful} riuscite al primo tentativo · {plan.practice} ripetizioni di pratica.</p>
          <progress aria-label="Verifiche di oggi" value={Math.min(plan.completed,plan.target)} max={plan.target}/>
          <p className="muted">{!plan.activeDay?'Puoi comunque aprire Puzzle o Blunder prevention per fare pratica.':plan.queue.length?'Prima i ripassi in scadenza, poi poche posizioni nuove.':plan.completed>=plan.target?'Le altre posizioni restano disponibili come pratica.':!plan.total?'Importa e analizza una partita: le posizioni adatte entreranno nel piano.':'Con queste impostazioni non ci sono altri esercizi per ora.'}</p>
          {plan.queue[0]&&<button className="primary big" onClick={()=>onOpen(plan.queue[0].kind,plan.queue[0].id)}>Inizia il prossimo ripasso →</button>}
          {!plan.total&&<button onClick={onImport}>Importa partite da Maia</button>}
          {plan.nextDue&&<p className="footnote">Prossimo richiamo: {new Date(plan.nextDue).toLocaleString('it-IT',{timeZone:plan.settings.timezone})}.</p>}
        </div>
      </div>}
    </section>
    <section className="panel"><div className="section-head"><h3>In coda</h3>{plan&&<span className="count-chip">{plan.queue.length}</span>}</div>
      {plan&&<><div className="exercise-list">{plan.queue.map(item=><button key={item.kind+item.id} onClick={()=>onOpen(item.kind,item.id)}><strong><span className={`kind-tag kind-${item.kind}`}>{item.kind==='puzzle'?'Puzzle':item.kind==='prevention'?'Blunder prevention':'Trova un’alternativa'}</span> {item.new?'Nuovo':`Ripasso ${item.stage}`}</strong><small>{item.title} · {item.theme}</small></button>)}</div>
        {!plan.queue.length&&<p className="empty-text">Nessun esercizio in coda.</p>}
        <p className="footnote">{plan.ready} esercizi pronti · {plan.waiting} in attesa di una verifica a distanza.</p>
        <InfoNote summary="Perché non vedo lo stesso errore due volte">Il piano evita di proporre due volte la stessa decisione attraverso Puzzle e Blunder prevention.</InfoNote></>}
    </section>
    <section className="panel calendar-panel"><h3>Prossimi sette giorni</h3><ol className="schedule-calendar">{plan?.calendar.map((day,index)=>{const date=new Date(day.date+'T12:00:00');return <li key={day.date} className={`${day.planned?'':'rest-day'} ${index===0?'today':''}`}>
      <small>{date.toLocaleDateString('it-IT',{weekday:'short'})}</small><strong>{date.getDate()}</strong>
      <span className="due-dot" style={{opacity:day.due?.35+.65*day.due/busiest:.12}} aria-hidden="true"/>
      <span className="due-count" aria-label={`${day.due} scadenze`}>{day.due}</span>{!day.planned&&<small className="day-kind">Pausa</small>}</li>})}</ol>
      <InfoNote summary="Come funziona il ripasso"><p>Primo successo senza aiuti: richiamo dopo 4 ore. Poi 1, 3, 7, 14, 30, 90 e 180 giorni, se riesci ancora al primo tentativo.</p><p>Errore o soluzione mostrata: il livello riparte e la verifica successiva attende 4 ore. Puoi esercitarti subito, ma la ripetizione anticipata non fa avanzare il calendario. Un puzzle sbagliato resta nella lista da ripassare.</p><p>Le scadenze cambiano dopo ogni verifica; gli arretrati compaiono oggi. Il calendario misura il ricordo di queste posizioni, non dimostra che riconosci lo stesso pericolo in una partita nuova. Sistema ispirato alla ripetizione dilazionata, indipendente da MoveTrainer.</p></InfoNote>
    </section>
    <details className="panel settings-panel"><summary>Organizza la settimana{settings&&<small>{settings.minutes} min · {settings.weekdays.length} giorni · max {settings.newLimit} nuove</small>}</summary>{settings&&<div className="settings-body">
      <label className="field-label">Minuti per sessione <input aria-label="Minuti per sessione" type="number" min={5} max={60} value={settings.minutes} onChange={e=>setSettings({...settings,minutes:Number(e.target.value)})}/></label>
      <label className="field-label">Massimo di posizioni nuove al giorno <input aria-label="Posizioni nuove al giorno" type="number" min={0} max={10} value={settings.newLimit} onChange={e=>setSettings({...settings,newLimit:Number(e.target.value)})}/></label>
      <div className="schedule-days chip-row" role="group" aria-label="Giorni di allenamento">{days.map((d,i)=><label key={d} className="chip"><input type="checkbox" checked={settings.weekdays.includes(i)} onChange={e=>setSettings({...settings,weekdays:e.target.checked?[...settings.weekdays,i]:settings.weekdays.filter(x=>x!==i)})}/>{d}</label>)}</div>
      <button className="primary" disabled={saving||!settings.weekdays.length} onClick={save}>{saving?'Salvataggio…':'Salva piano'}</button>
      <p className="footnote">Circa due minuti per esercizio, senza conto alla rovescia. Orari in {settings.timezone}. I giorni di pausa non cancellano i ripassi arretrati.</p>
    </div>}</details>
    <section className="panel guide-card" aria-label="Guida di allenamento">
      <div><h3>Guida di allenamento</h3><p className="muted">Come importare da Maia, organizzare i ripassi e usare Aimchess, MoveTrainer e Noctie.</p></div>
      <div className="row"><button onClick={openGuide}>Apri la guida ↗</button><a className="button-link" href="/api/training-guide/html?download=true" download>Scarica HTML</a></div>
      {guideOpened&&<p className="footnote">Se la finestra non si apre, <a href="/api/training-guide/html" target="_blank" rel="noopener noreferrer">apri la guida in una nuova scheda</a>.</p>}
    </section>
    <details ref={judgmentRef} open={judgmentOpen} className="judgment-entry panel" onToggle={e=>setJudgmentOpen(e.currentTarget.open)}><summary>Valuta la posizione · allena il giudizio prima del motore</summary>{judgmentOpen&&judgment}</details>
  </div>
}
