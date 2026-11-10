export interface Points {now:number;end:number;plies:number;cp:number|null;mate:number|null;expected:number;rest:number|null}

// Signed, Italian decimal comma, from the player's side (the side to move).
const signed=(x:number,digits=0)=>`${x>0?'+':x<0?'−':''}${Math.abs(x).toFixed(digits).replace('.',',')}`

/** Where an engine score comes from: material now, material at the end of Stockfish's line, the expected score, and the rest. */
export default function PointsBreakdown({points}:{points?:Points|null}){
  if(!points)return null
  const gained=points.end-points.now
  return <div className="points-breakdown" aria-label="Da dove vengono i punti"><h4>Da dove vengono i punti</h4><ul>
    <li><b>Materiale sulla scacchiera: {signed(points.now)}</b> per te (pedone 1, cavallo e alfiere 3, torre 5, donna 9).</li>
    <li><b>Alla fine della variante di Stockfish{points.plies?` (${points.plies} semimosse)`:''}: {signed(points.end)}.</b> {gained>0?`La linea guadagna ${gained} di materiale: è il colpo da trovare, e Stockfish lo conta già come tuo.`:gained<0?`La linea restituisce ${-gained} di materiale in cambio d’altro: attacco, tempo o un pedone che promuove.`:'Il materiale non cambia.'}</li>
    {points.mate!==null?<li><b>Matto {points.mate>0?'a tuo favore':'contro di te'} in {Math.abs(points.mate)}.</b> Il materiale non conta più: decide il re.</li>:<>
      <li><b>Stockfish: {signed(points.cp!/100,2)} per te, punteggio atteso circa {points.expected}%</b> (vittoria 1, patta mezzo punto). Il numero misura le probabilità di vincere, non i pedoni: con due pedoni puliti in più e nessun compenso è normale vedere +4 o più.</li>
      <li><b>Il resto: {signed(points.rest!,2)}.</b> {Math.abs(points.rest!)<1?'Quasi tutto il punteggio è materiale.':points.rest!>0?'Viene da re più sicuro, pezzi più attivi, pedoni passati o iniziativa; e, con un vantaggio senza compenso, dal fatto che si converte.':'Il materiale in più non basta: re esposto, pezzi passivi o un’iniziativa dell’avversario lo compensano.'}</li></>}
  </ul></div>
}
