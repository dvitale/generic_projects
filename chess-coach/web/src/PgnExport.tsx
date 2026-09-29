import {useState} from 'react'
import type {Game} from './types'

export default function PgnExport({game}:{game:Game}) {
  const [includeTimes,setIncludeTimes]=useState(true)
  return <div className="pgn-export">
    <div className="row"><a className="pgn-download" href={`/api/games/${encodeURIComponent(game.id)}/pgn?include_times=${includeTimes}`} download>↓ Esporta PGN</a>
      <label><input type="checkbox" checked={includeTimes} onChange={e=>setIncludeTimes(e.target.checked)}/> Includi tempi</label></div>
    <small className="footnote">{game.timedMoves?`Tempi disponibili per ${game.timedMoves} di ${game.version} semimosse.`:'Tempi non disponibili per le mosse già archiviate.'} Nelle partite libere viene registrato il tempo di riflessione attivo, senza conto alla rovescia.</small>
  </div>
}
