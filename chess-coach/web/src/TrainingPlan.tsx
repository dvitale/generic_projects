import {useEffect,useState} from 'react'
import {api} from './api'

type Item={kind:'puzzle'|'prevention';id:string;title:string;theme:string;stage:number;new:boolean;readyAt:string}
type Settings={minutes:number;newLimit:number;weekdays:number[];timezone:string}
type Plan={settings:Settings;today:string;activeDay:boolean;target:number;completed:number;successful:number;practice:number;ready:number;waiting:number;total:number;queue:Item[];calendar:{date:string;planned:boolean;due:number}[];nextDue:string|null}
const days=['Lun','Mar','Mer','Gio','Ven','Sab','Dom']
export default function TrainingPlan({onOpen,onImport}:{onOpen:(kind:Item['kind'],id:string)=>void;onImport:()=>void}){
  const [plan,setPlan]=useState<Plan|null>(null),[settings,setSettings]=useState<Settings|null>(null)
  const [error,setError]=useState(''),[saving,setSaving]=useState(false)
  const [guideOpened,setGuideOpened]=useState(false)
  function openGuide(){
    window.open('/api/training-guide/html','_blank','popup=yes,width=1120,height=820,resizable=yes,scrollbars=yes,noopener,noreferrer')
    setGuideOpened(true)
  }
  useEffect(()=>{let stale=false;const refresh=()=>api<Plan>('/training-plan').then(p=>{if(!stale){setPlan(p);setSettings(s=>s??p.settings)}}).catch(e=>{if(!stale)setError(e.message)});void refresh();const timer=setInterval(refresh,30000);return()=>{stale=true;clearInterval(timer)}},[])
  async function save(){if(!settings)return;setSaving(true);setError('');try{const p=await api<Plan>('/training-plan/settings',settings);setPlan(p);setSettings(p.settings)}catch(e){setError((e as Error).message)}finally{setSaving(false)}}
  return <div className="schedule-layout">
    <section className="panel" style={{gridColumn:'1 / -1'}} aria-label="Guida di allenamento">
      <h2>La tua guida di allenamento</h2>
      <p>Importare da Maia, organizzare i ripassi e usare Aimchess, MoveTrainer e Noctie.</p>
      <div className="actions"><button onClick={openGuide}>Apri la guida ↗</button><a href="/api/training-guide/html?download=true" download>Scarica HTML</a></div>
      {guideOpened&&<p className="footnote">Se la finestra non si apre, <a href="/api/training-guide/html" target="_blank" rel="noopener noreferrer">apri la guida in una nuova scheda</a>.</p>}
    </section>
    {error&&<p className="alert" role="alert">{error}</p>}
    <section className="panel"><span className="eyebrow">IL TUO PIANO</span><h2>Un ripasso alla volta</h2>
      {!plan?<p role="status">Preparazione del piano…</p>:<>
        <p>{plan.completed} / {plan.target} verifiche oggi · {plan.successful} riuscite al primo tentativo · {plan.practice} ripetizioni di pratica.</p>
        <progress aria-label="Verifiche di oggi" value={Math.min(plan.completed,plan.target)} max={plan.target}/>
        <p className="muted">{!plan.activeDay?'Oggi hai previsto una pausa. Puoi comunque aprire Puzzle o Blunder prevention per fare pratica.':plan.queue.length?'Inizia dai ripassi in scadenza, poi affronta poche posizioni nuove.':plan.completed>=plan.target?'Obiettivo di oggi completato. Le altre posizioni restano disponibili come pratica.':!plan.total?'Importa e analizza una partita: le posizioni adatte entreranno nel piano.':'Nessun altro esercizio previsto ora con queste impostazioni.'}</p>
        {plan.queue[0]&&<button className="primary" onClick={()=>onOpen(plan.queue[0].kind,plan.queue[0].id)}>Inizia il prossimo ripasso →</button>}
        {!plan.total&&<button onClick={onImport}>Importa partite da Maia</button>}
        <div className="exercise-list">{plan.queue.map(item=><button key={item.kind+item.id} onClick={()=>onOpen(item.kind,item.id)}><strong>{item.kind==='puzzle'?'Puzzle':'Blunder prevention'} · {item.new?'Nuovo':`Ripasso ${item.stage}`}</strong><small>{item.title} · {item.theme}</small></button>)}</div>
        <p className="footnote">{plan.ready} esercizi pronti · {plan.waiting} in attesa di una verifica a distanza. Il piano evita di proporre due volte la stessa decisione attraverso Puzzle e Blunder prevention.</p>
        {plan.nextDue&&<p>Prossimo richiamo: {new Date(plan.nextDue).toLocaleString('it-IT',{timeZone:plan.settings.timezone})}.</p>}
      </>}
    </section>
    <section className="panel"><h2>Organizza la settimana</h2>{settings&&<>
      <label className="field-label">Minuti per sessione <input aria-label="Minuti per sessione" type="number" min={5} max={60} value={settings.minutes} onChange={e=>setSettings({...settings,minutes:Number(e.target.value)})}/></label>
      <label className="field-label">Massimo di posizioni nuove al giorno <input aria-label="Posizioni nuove al giorno" type="number" min={0} max={10} value={settings.newLimit} onChange={e=>setSettings({...settings,newLimit:Number(e.target.value)})}/></label>
      <div className="schedule-days" role="group" aria-label="Giorni di allenamento">{days.map((d,i)=><label key={d}><input type="checkbox" checked={settings.weekdays.includes(i)} onChange={e=>setSettings({...settings,weekdays:e.target.checked?[...settings.weekdays,i]:settings.weekdays.filter(x=>x!==i)})}/>{d}</label>)}</div>
      <button disabled={saving||!settings.weekdays.length} onClick={save}>{saving?'Salvataggio…':'Salva piano'}</button>
      <p className="footnote">Circa due minuti per esercizio, senza conto alla rovescia. Orari in {settings.timezone}. I giorni di pausa non cancellano i ripassi arretrati.</p>
    </>}</section>
    <section className="panel"><h2>Scadenze dei prossimi sette giorni</h2><div className="schedule-calendar">{plan?.calendar.map(day=><div key={day.date}><strong>{new Date(day.date+'T12:00:00').toLocaleDateString('it-IT',{weekday:'short',day:'numeric',month:'short'})}</strong><span>{day.due} scadenze</span><small>{day.planned?'Allenamento':'Pausa'}</small></div>)}</div><p className="footnote">Scadenze attuali: cambiano dopo ogni verifica. Gli arretrati compaiono oggi; nei giorni di pausa il piano non propone attività.</p></section>
    <section className="panel"><h2>Come funziona il ripasso</h2><p>Primo successo senza aiuti: richiamo dopo 4 ore. Poi 1, 3, 7, 14, 30, 90 e 180 giorni, se riesci ancora al primo tentativo.</p><p>Errore o soluzione mostrata: il livello riparte e la verifica successiva attende 4 ore. Puoi esercitarti subito, ma la ripetizione anticipata non fa avanzare il calendario. Un puzzle sbagliato resta nella lista da ripassare.</p><p className="footnote">Il calendario misura il ricordo di queste posizioni, non dimostra ancora che riconosci lo stesso pericolo in una partita nuova. Sistema ispirato alla ripetizione dilazionata, indipendente da MoveTrainer.</p></section>
  </div>
}
