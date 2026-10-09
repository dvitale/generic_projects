import {useEffect,useState} from 'react'
import {api} from './api'
type Entry={index:number;id?:string;title?:string;origin?:string;duplicate?:boolean;jobId?:string|null;analysisError?:string;error?:string}
type Report={imported:number;duplicates:number;failed:number;results:Entry[]}
export default function ImportGames({onImported,onOpen}:{onImported:()=>void;onOpen:(id:string)=>void}){
  const [pgn,setPgn]=useState(''),[username,setUsername]=useState(()=>localStorage.getItem('pgn-player')||'')
  const [color,setColor]=useState('auto'),[analyze,setAnalyze]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [report,setReport]=useState<Report|null>(null),[jobs,setJobs]=useState<Record<string,string>>({})
  useEffect(()=>{
    if(!report)return
    let stopped=false,polling=false
    const pending=report.results.filter(r=>r.jobId)
    async function poll(){
      if(polling||stopped)return
      polling=true
      try{
      for(const entry of [...pending]){
        try{const j=await api<{status:string;progress:number}>('/jobs/'+entry.jobId);if(stopped)return;setJobs(old=>({...old,[entry.jobId!]:j.status==='complete'?'Esercizi pronti':j.status==='failed'?'Analisi da riprovare':`Analisi ${j.progress}%`}));if(j.status!=='running'){pending.splice(pending.indexOf(entry),1);onImported()}}
        catch{if(!stopped){setJobs(old=>({...old,[entry.jobId!]:'Apri la partita e riprova l’analisi'}));pending.splice(pending.indexOf(entry),1)}}
      }
      }finally{polling=false}
    }
    void poll();const timer=setInterval(()=>{if(pending.length)void poll()},1500)
    return()=>{stopped=true;clearInterval(timer)}
  },[report])
  async function submit(){setBusy(true);setError('');setReport(null);setJobs({});try{localStorage.setItem('pgn-player',username);const r=await api<Report>('/import/batch',{pgn,username,color,analyze});setReport(r);onImported()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function files(list:FileList|null){if(!list)return;setError('');try{const chosen=Array.from(list);if(chosen.reduce((n,f)=>n+f.size,0)>1000000)throw new Error('Usa file per un totale massimo di 1 MB.');setPgn((await Promise.all(chosen.map(f=>f.text()))).join('\n\n'))}catch(e){setError((e as Error).message)}}
  return <section className="panel import-panel" aria-label="Importazione partite"><h2>Porta qui le tue partite di Maia</h2>
    <p>Su Maia apri la partita in Analysis ed esporta o copia il PGN. Qui puoi caricare più file oppure incollare fino a 20 partite insieme. Non serve la password di Maia.</p>
    <p className="footnote">La sincronizzazione automatica dell’account Maia non è disponibile. Il file PGN conserva solo i dati esportati dal sito; i tempi assenti non vengono inventati.</p>
    <label className="field-label">File PGN <input aria-label="File PGN" type="file" accept=".pgn,.txt" multiple disabled={busy} onChange={e=>void files(e.target.files)}/></label>
    <textarea aria-label="Partite PGN" rows={5} value={pgn} disabled={busy} onChange={e=>setPgn(e.target.value)} placeholder={'[Site "https://maiachess.com/"]\n[White "Il tuo nome"]\n[Black "Maia 600"]\n\n1. e4 e5 *'}/>
    <div className="row"><label>Il tuo nome nel PGN (facoltativo) <input aria-label="Nome nel PGN" value={username} disabled={busy} onChange={e=>setUsername(e.target.value)}/></label><label>Colore <select aria-label="Colore da analizzare" value={color} disabled={busy} onChange={e=>setColor(e.target.value)}><option value="auto">Automatico contro Maia</option><option value="w">Bianco in tutte</option><option value="b">Nero in tutte</option></select></label></div>
    <label><input type="checkbox" checked={analyze} disabled={busy} onChange={e=>setAnalyze(e.target.checked)}/> Analizza e prepara gli esercizi dopo l’importazione</label>
    <p><button className="primary" disabled={busy||!pgn.trim()} onClick={submit}>{busy?'Importazione…':'Importa partite'}</button></p>
    {error&&<p role="alert">{error}</p>}
    {report&&<div role="status"><p>{report.imported} importate · {report.duplicates} già presenti · {report.failed} non importate.</p>{report.results.map(r=><p key={r.index}>{r.error?`Partita ${r.index}: ${r.error}`:<><button onClick={()=>onOpen(r.id!)}>{r.title}</button> · {r.origin} · {r.duplicate?'già presente':'salvata'} · {r.analysisError|| (r.jobId?jobs[r.jobId]||'Analisi in coda':'Disponibile per la revisione')}</>}</p>)}</div>}
  </section>
}
