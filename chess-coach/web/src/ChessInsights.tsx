export interface Insight {
  kind:'tactical'|'positional'|'mixed'|'unclear'|'neutral';label:string;
  tacticalFacts:string[];positionalFacts:string[];plans:string[];note:string;
  material?:{before:number;immediate:number;playedLine:number;bestLine:number}
}
export interface Reasoning {tactical?:string;positional?:string;strategicPlan?:string;uncertainty?:string}

export function ThinkingGuide(){
  return <details className="thinking-guide"><summary>Tattica, posizione e strategia: cosa cambia?</summary><dl>
    <dt>Tattica · cosa succede concretamente?</dt><dd>Calcola scacchi, catture, minacce e difese di entrambi i colori, comprese le risposte intermedie.</dd>
    <dt>Posizione · che cosa è migliorato o peggiorato?</dt><dd>Confronta attività dei pezzi, struttura pedonale, centro, colonne e sicurezza del re.</dd>
    <dt>Strategia · quale piano seguire?</dt><dd>Scegli un obiettivo legato alla posizione e controlla che le risposte tattiche avversarie lo permettano.</dd>
  </dl><p>“Blunder” descrive la gravità del peggioramento, non la sua causa. Un calo di 2 punti di valutazione non significa aver perso due pedoni. Una variante breve senza catture non dimostra che l’errore sia strategico.</p></details>
}

export function ReasoningSections({value}:{value:Reasoning}){
  if(!value.tactical&&!value.positional&&!value.strategicPlan)return <p className="footnote">Spiegazione salvata con il formato precedente. Aggiorna il confronto per distinguere tattica, posizione e piano.</p>
  return <div className="reasoning-sections">
    <div><h4>Tattica · conseguenze concrete</h4><p>{value.tactical}</p></div>
    <div><h4>Posizione · che cosa cambia</h4><p>{value.positional}</p></div>
    <div><h4>Strategia · piano da verificare</h4><p>{value.strategicPlan}</p></div>
    {value.uncertainty&&<p className="footnote"><strong>Certezze e limiti. </strong>{value.uncertainty}</p>}
  </div>
}

export default function ChessInsights({insight,compact=false}:{insight?:Insight;compact?:boolean}){
  if(!insight)return null
  return <div className="chess-insight" aria-label="Tattica e strategia"><span className={`insight-badge insight-${insight.kind}`}>{insight.label}</span>
    <details open={compact?undefined:true}><summary>Perché può cambiare la valutazione</summary>
      <h4>Tattica · evidenze nella variante</h4>
      {insight.tacticalFacts.length?<ul>{insight.tacticalFacts.map((fact,i)=><li key={i}>{fact}</li>)}</ul>:<p>Nessuna conseguenza tattica decisiva documentata dalla linea disponibile. Non basta per escludere tattiche più lontane.</p>}
      {insight.material&&<p className="footnote">Saldo materiale convenzionale: prima {insight.material.before}, subito dopo la tua mossa {insight.material.immediate}. È distinto dalla valutazione Stockfish.</p>}
      <h4>Posizione · differenze osservabili</h4>
      {insight.positionalFacts.length?<><p className="footnote">Confronto dopo una mossa in entrambi i casi. Le differenze sono fatti; il loro peso e il nesso con l’errore vanno interpretati.</p><ul>{insight.positionalFacts.map((fact,i)=><li key={i}>{fact}</li>)}</ul></>:<p>Gli indicatori disponibili non spiegano una differenza posizionale chiara. Non è una prova che la posizione sia equivalente.</p>}
      <h4>Strategia · domande per scegliere un piano</h4>
      {insight.plans.length?<ul>{insight.plans.map((plan,i)=><li key={i}>{plan}</li>)}</ul>:<p>Confronta lo scopo delle due scelte e la migliore risposta avversaria. Le evidenze attuali non bastano per attribuire un piano preciso.</p>}
      <p className="footnote">{insight.note}</p>
    </details>
  </div>
}
