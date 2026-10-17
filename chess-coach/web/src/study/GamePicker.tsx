import type {Saved} from '../GameArchive'

/** Analysed games that can feed the study tools; refutation games against Stockfish are excluded. */
export const studyGames=(games:Saved[])=>games.filter(g=>g.quality&&g.source!=='stockfish')

export default function GamePicker({games,value,onChange}:{games:Saved[];value:string|null;onChange:(id:string)=>void}){
  const options=studyGames(games)
  if(!options.length)return <p className="empty-text">Nessuna partita analizzata: gioca o importa una partita e avvia <strong>Analizza partita</strong>.</p>
  return <label className="game-picker"><span className="field-label">Partita</span>
    <select aria-label="Partita" value={value??''} onChange={e=>onChange(e.target.value)}>
      {!value&&<option value="" disabled>Scegli una partita analizzata</option>}
      {options.map(g=><option key={g.id} value={g.id}>{new Date(g.createdAt).toLocaleDateString('it-IT')} · {g.title}{g.quality?` · ${g.quality.errors} errori`:''}</option>)}
    </select></label>
}
