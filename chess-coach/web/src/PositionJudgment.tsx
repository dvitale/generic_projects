import {useEffect,useState} from 'react'
import Board from './Board'
import LichessAnalysis from './LichessAnalysis'
import {api} from './api'
import type {Color,Evaluation} from './types'
const choices=[['much_worse','Forte svantaggio'],['worse','Svantaggio'],['equal','Circa equilibrio'],['better','Vantaggio'],['much_better','Forte vantaggio']] as const
type Position={id:string;fen:string;ply:number;color:Color;answer?:{assessment:string;confidence:string;threat:string;fearedLost:boolean;familiar:boolean};evidence?:Evaluation;expected?:string;falseAlarm?:boolean;gameId?:string}
export default function PositionJudgment({onReview}:{onReview:(id:string,ply:number)=>void}){
  const [position,setPosition]=useState<Position|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('')
  const [assessment,setAssessment]=useState(''),[confidence,setConfidence]=useState('uncertain'),[threat,setThreat]=useState(''),[fearedLost,setFearedLost]=useState(false),[familiar,setFamiliar]=useState(false)
  async function next(){setLoading(true);setError('');try{const p=await api<Position|null>('/position-judgments/next',{});setPosition(p);setAssessment('');setConfidence('uncertain');setThreat('');setFearedLost(false);setFamiliar(false)}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  useEffect(()=>{void next()},[])
  async function submit(){if(!position||!assessment)return;setLoading(true);setError('');try{setPosition(await api<Position>(`/position-judgments/${position.id}`,{assessment,confidence,threat,fearedLost,familiar}))}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  return <section className="panel" aria-label="Valuta la posizione"><span className="eyebrow">PRIMA LA TUA IMPRESSIONE</span><h2>Valuta la posizione</h2>
    <p>Osserva materiale, sicurezza dei re, attività e minacce concrete. La posizione può essere favorevole, equilibrata o sfavorevole: non devi necessariamente trovare una salvezza.</p>
    {error&&<p role="alert">{error}</p>}{loading&&!position&&<p role="status">Preparazione…</p>}
    {!position&&!loading&&<p>Nessuna nuova posizione disponibile. Analizza altre partite concluse; le posizioni già valutate non vengono riproposte come nuove.</p>}
    {error&&!position&&<button onClick={next}>Riprova</button>}
    {position&&<div className="judgment-layout"><div>
      <p><strong>Valuta dal punto di vista del {position.color==='w'?'Bianco':'Nero'}, che deve muovere.</strong></p>
      <Board fen={position.fen} orientation={position.color} interactive={false} legalMoves={[]} onMove={()=>{}}/>
    </div><div>{!position.answer?<>
      <label className="field-label">La tua valutazione<select aria-label="La tua valutazione" value={assessment} onChange={e=>setAssessment(e.target.value)}><option value="">Scegli prima di vedere il motore</option>{choices.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
      <label className="field-label">Quanto sei sicuro?<select aria-label="Quanto sei sicuro?" value={confidence} onChange={e=>setConfidence(e.target.value)}><option value="uncertain">Poco sicuro</option><option value="moderate">Abbastanza sicuro</option><option value="confident">Molto sicuro</option></select></label>
      <label className="field-label">Quale minaccia temi? Quale risorsa hai?<textarea maxLength={1000} value={threat} onChange={e=>setThreat(e.target.value)} placeholder="Scrivi la risposta concreta che temi e una possibile difesa."/></label>
      <label className="judgment-check"><input type="checkbox" checked={fearedLost} onChange={e=>setFearedLost(e.target.checked)}/>Mi sembra già persa, senza possibilità di difesa.</label>
      <label className="judgment-check"><input type="checkbox" checked={familiar} onChange={e=>setFamiliar(e.target.checked)}/>Ricordo già questa posizione o la sua valutazione.</label>
      <button className="primary full" disabled={loading||!assessment} onClick={submit}>{loading?'Salvataggio…':'Salva e confronta con Stockfish'}</button>
      <p className="footnote">La prima risposta resta salvata. Nessun conto alla rovescia e nessuna valutazione Elo.</p>
    </>:<>
      <h3>Confronto con la tua impressione</h3><p>Hai indicato: <strong>{choices.find(c=>c[0]===position.answer!.assessment)?.[1]}</strong>.</p>
      <p>Stockfish: <strong>{choices.find(c=>c[0]===position.expected)?.[1]}</strong> · {position.evidence?.mate!=null?`Matto ${position.evidence.mate>0?'a favore':'contro'} in ${Math.abs(position.evidence.mate)}`:`${((position.evidence?.cp??0)/100).toFixed(2)} punti dalla tua prospettiva`}.</p>
      {position.falseAlarm&&<p className="notice">Ti sembrava già persa, ma questa analisi non lo conferma. Esamina le risorse prima di rinunciare.</p>}
      <p>{position.answer.assessment===position.expected?'La tua fascia coincide con quella del motore.':'Le due valutazioni differiscono: confronta la minaccia che temevi con la variante, senza attribuire subito la differenza a un difetto del tuo ragionamento.'}</p>
      {position.answer.threat&&<p>La tua riflessione: {position.answer.threat}</p>}
      <p className="variation">Variante di riferimento: {position.evidence?.san.join(' ')||'Non disponibile'}</p>
      <p className="footnote">Analisi salvata a budget limitato, profondità {position.evidence?.depth}. Equilibrio fra −1 e +1; forte vantaggio/svantaggio da ±3. Le fasce sono convenzioni didattiche; uno svantaggio non prova una sconfitta inevitabile.</p>
      <div className="actions"><button disabled={loading} onClick={next}>Prossima posizione</button><button onClick={()=>onReview(position.gameId!,position.ply)}>Rivedi la partita di origine</button></div>
      <LichessAnalysis fen={position.fen} orientation={position.color}/>
    </>}</div></div>}
  </section>
}
