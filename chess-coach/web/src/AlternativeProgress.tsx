import {useEffect,useState} from 'react'
import {api} from './api'
import BarList from './BarList'
import InfoNote from './InfoNote'

type Outcomes={total:number;independent:number;with_hint:number;understood_after:number;not_understood:number;meanHelp:number|null;helpLevels:number[]}
type Period={found:number;missed:number;partial:number;games:number}
type Results={games:number;win:number;draw:number;loss:number}
type Progress={total:number;completed:number;newPositions:{recent:Outcomes;previous:Outcomes;all:Outcomes};seenPositions:Outcomes;
  difficulties:{label:string;title:string;area:string;count:number}[];classificationSources:Record<string,number>;
  collection:{liveMarks:number;retrospectiveMarks:number;liveAnswers:number;retrospectiveAnswers:number;assistedLive:number;markedOnly:number};
  recurrence:{direction:string;title:string;since:string;before:Period;after:Period}[];maiaOnline:{level:string;timeControl:string;before:Results;after:Results}[];localMaia:{level:number;assisted:Results;autonomous:Results}[]}
const areas:Record<string,string>={search:'ricerca delle mosse',calculation:'calcolo',evaluation:'valutazione',unclear:'da chiarire'}
const share=(part:number,total:number)=>total?`${Math.round(100*part/total)}%`:'—'
function Autonomy({title,data}:{title:string;data:Outcomes}){
  return <div className="alternative-window"><h4>{title}</h4>{data.total?<>
    <p><b>{share(data.independent,data.total)}</b> risolti da solo · aiuto medio <b>{String(data.meanHelp).replace('.',',')}</b> / 5 · <span className="muted">{data.total} episodi</span></p>
    <p className="muted">Con indizio {data.with_hint} · compresi dopo la soluzione {data.understood_after} · non ancora compresi {data.not_understood}</p></>:<p className="muted">Nessun episodio completato.</p>}</div>
}
const results=(r:Results)=>r.games?`${r.win} vinte, ${r.draw} patte, ${r.loss} perse su ${r.games}`:'nessuna partita'

export default function AlternativeProgress(){
  const [data,setData]=useState<Progress|null>(null),[error,setError]=useState('')
  useEffect(()=>{let stale=false;api<Progress>('/alternatives/progress').then(d=>{if(!stale)setData(d)}).catch(e=>{if(!stale)setError(e.message)});return()=>{stale=true}},[])
  return <section className="panel alternative-progress" aria-label="Trova un’alternativa nel tempo"><span className="eyebrow">TROVA UN’ALTERNATIVA</span><h2>Dall’indizio alla mossa trovata da solo</h2>
    {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Caricamento…</p>}
    {data&&(!data.total?<p className="empty-text">Ancora nessun momento segnato. Usa «Qui mi sento bloccato» durante una partita o in Rivedi.</p>:<>
      <div className="alternative-windows"><Autonomy title="Posizioni nuove · ultimi 10" data={data.newPositions.recent}/><Autonomy title="Posizioni nuove · 10 precedenti" data={data.newPositions.previous}/><Autonomy title="Posizioni già viste (ripetizioni)" data={data.seenPositions}/></div>
      <h3>Aiuto necessario sulle posizioni nuove</h3>
      <BarList unit="episodi" items={data.newPositions.all.helpLevels.map((n,level)=>({key:String(level),label:level?`Fino al livello ${level}`:'Nessun aiuto',value:n}))}/>
      {data.difficulties.length>0&&<><h3>Difficoltà più frequenti</h3><BarList unit="episodi" items={data.difficulties.map(d=>({key:d.label,label:`${d.title} · ${areas[d.area]}`,value:d.count}))}/>
        <p className="footnote">Dalle tue risposte dopo la soluzione ({data.classificationSources.declared??0}) e dalle tue correzioni ({data.classificationSources.corrected??0}). Le ipotesi automatiche non entrano nel conteggio.</p></>}
      {data.recurrence.length>0&&<><h3>La stessa idea nelle partite</h3><ul className="alternative-recurrence">{data.recurrence.map(r=><li key={r.direction}><b>{r.title}</b>: dopo il primo episodio trovata {r.after.found} volte e mancata {r.after.missed} ({r.after.games} partite); prima trovata {r.before.found} e mancata {r.before.missed} ({r.before.games} partite).</li>)}</ul>
        <p className="footnote">Decisioni analizzate in cui la mossa migliore era di quel tipo; «mancata» significa almeno 1,80 di perdita. Il tipo di idea è riconosciuto con regole fisse sulla scacchiera.</p></>}
      {data.maiaOnline.length>0&&<><h3>Contro Maia online, a parità di condizioni</h3><ul className="alternative-recurrence">{data.maiaOnline.map(g=><li key={g.level+g.timeControl}><b>Maia {g.level} · cadenza {g.timeControl}</b>: prima {results(g.before)}; dopo {results(g.after)}.</li>)}</ul></>}
      {data.localMaia.length>0&&<><h3>Partite contro Maia in SparringMate</h3><ul className="alternative-recurrence">{data.localMaia.map(g=><li key={g.level}><b>Maia {g.level}</b>: autonome {results(g.autonomous)}; con aiuti {results(g.assisted)}.</li>)}</ul></>}
      <p className="footnote">Raccolta: {data.collection.liveMarks} segnalazioni dal vivo e {data.collection.retrospectiveMarks} in revisione; risposte dal vivo {data.collection.liveAnswers}, ricostruite dopo {data.collection.retrospectiveAnswers}; {data.collection.assistedLive} decisioni di partita rese assistite dal percorso; {data.collection.markedOnly} momenti solo segnati.</p>
      <InfoNote summary="Come leggere questi dati"><p>Il passaggio da «riconosco l’idea dopo un suggerimento» a «la trovo da solo» si misura su posizioni nuove: momenti originali, posizioni analoghe e controesempi. Le ripetizioni sono contate a parte. Poi si guarda se la stessa idea viene trovata nelle partite successive.</p><p>Non esiste un Elo dell’allenamento. I risultati contro Maia dipendono da molti fattori: il confronto prima/dopo non attribuisce al modulo variazioni di risultato, e con pochi episodi o poche partite non dice nulla di stabile.</p></InfoNote>
    </>)}
  </section>
}
