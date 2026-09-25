import type { Decision, Evaluation, Game } from './types'
import type { Prediction } from './engine/maia'

function score(value:Evaluation){return value.mate!==null?`Matto ${value.mate>0?'+':''}${value.mate}`:`${value.cp>0?'+':''}${(value.cp/100).toFixed(2)}`}
function label(d:Decision){const fields=d.fen.split(' ');return `${fields[5]}${fields[1]==='b'?'…':'.'} ${d.playedSan}`}

export default function MoveReview({game,cursor,onPosition,level,onLevel,prediction,error,onRetry,analyzing,onAnalyze}:{
  game:Game;cursor:number;onPosition:(ply:number)=>void;level:number;onLevel:(level:number)=>void;
  prediction:Prediction|null;error:string;onRetry:()=>void;analyzing:boolean;onAnalyze:()=>void
}){
  const moves=game.analysis?.moves||game.analysis?.decisions||[]
  const index=moves.findIndex(d=>d.ply===cursor)
  const current=moves[index]
  const human=prediction?.moves[0]
  const probability=(move:string)=>{
    const value=prediction?.moves.find(m=>m.uci===move)?.probability
    return value===undefined?'…':`${(value*100).toFixed(1)}%`
  }
  const maiaSan=human?.san
  const best=current?.best.pv[0]
  const currentLabel=current?label(current):''
  return <section className="panel move-review" aria-label="Revisione passo passo">
    <span className="eyebrow">UNA MOSSA ALLA VOLTA</span><h2>Revisione passo passo</h2>
    <label className="field-label">Livello Maia per il confronto<select aria-label="Livello Maia per l’analisi" value={level} onChange={e=>onLevel(Number(e.target.value))}>{Array.from({length:21},(_,i)=>600+i*100).map(r=><option key={r} value={r}>{r}</option>)}</select></label>
    {!moves.length?<><p>{analyzing?'Stockfish sta preparando il confronto di tutte le mosse…':'Avvia la revisione per confrontare ogni mossa con Stockfish e Maia.'}</p><button className="primary full" disabled={analyzing||!game.version} onClick={onAnalyze}>Avvia revisione passo passo</button></>:<>
      {!game.analysis?.moves&&<><p className="footnote">Questa analisi contiene solo le tue decisioni.</p><button disabled={analyzing} onClick={onAnalyze}>Aggiorna revisione completa</button></>}
      <div className="review-step-controls"><button aria-label="Decisione precedente" disabled={index===0} onClick={()=>onPosition(moves[index<0?moves.length-1:index-1].ply)}>←</button><label><span className="sr-only">Mossa da confrontare</span><select aria-label="Mossa da confrontare" value={current?.ply??''} onChange={e=>onPosition(Number(e.target.value))}>{!current&&<option value="">Scegli una mossa</option>}{moves.map(d=><option key={d.ply} value={d.ply}>{label(d)} · {d.fen.split(' ')[1]==='w'?'Bianco':'Nero'}</option>)}</select></label><button aria-label="Decisione successiva" disabled={index===moves.length-1} onClick={()=>onPosition(moves[index<0?0:index+1].ply)}>→</button></div>
      {current?<>
        <h3>{currentLabel} · {current.label}</h3><p className="footnote">Scacchiera prima della mossa. Valutazioni dal punto di vista del {current.fen.split(' ')[1]==='w'?'Bianco':'Nero'}, che deve muovere.</p>
        <table aria-label="Confronto delle mosse"><thead><tr><th>Mossa giocata</th><th>Stockfish</th><th>Maia {level}</th></tr></thead><tbody><tr><td><strong>{current.playedSan}</strong><small>{score(current.actual)}</small><small>Prob. Maia {probability(current.played)}</small></td><td><strong>{current.best.san[0]||'—'}</strong><small>{score(current.best)}</small><small>Prob. Maia {best?probability(best):'—'}</small></td><td><strong>{maiaSan||'…'}</strong><small>{human?`${(human.probability*100).toFixed(1)}%`:'Calcolo…'}</small></td></tr></tbody></table>
        <p>{current.forced?'Era l’unica mossa legale.':best===current.played?'La mossa giocata coincide con la scelta di Stockfish.':current.best.mate!==null||current.actual.mate!==null?'La differenza tra le due scelte riguarda una sequenza di matto: confronta le varianti.':`Rispetto alla scelta di Stockfish, la mossa giocata perde ${(current.loss/100).toFixed(2)} pedoni di valutazione.`}</p>
        {human&&<p>{human.uci===current.played?`La mossa giocata è anche la più probabile per Maia ${level}.`:human.uci===best?`Stockfish e Maia ${level} indicano la stessa mossa alternativa.`:`Maia ${level} preferisce ${human.san}: è la scelta umana più probabile secondo il modello, non necessariamente la migliore.`}</p>}
        <details><summary>Varianti verificate da Stockfish</summary><p><strong>Dopo la mossa giocata:</strong> {current.actual.san.join(' ')||current.playedSan}</p><p><strong>Linea preferita:</strong> {current.best.san.join(' ')||'—'}</p></details>
      </>:<p>Seleziona una mossa per vedere le tre scelte nella stessa posizione.</p>}
    </>}
    {error&&<div className="alert" role="alert">{error}<button onClick={onRetry}>Riprova Maia</button></div>}
  </section>
}
