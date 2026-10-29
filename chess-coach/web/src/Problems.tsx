import {useEffect,useRef,useState} from 'react'
import {Chess} from 'chess.js'
import Board from './Board'
import InfoNote from './InfoNote'
import FailureDiagnosis from './FailureDiagnosis'
import {useBoardOrientation} from './boardFlip'
import {maia} from './engine/maia'
import {api} from './api'
import type {Color} from './types'

interface Band {id:number;label:string;min:number;max:number;count:number;attempts:number;solved:number}
interface Overview {available:boolean;source:string;rating:number;attempts:number;solved:number;total:number;adaptiveRange:number;bands:Band[];themes:{id:string;count:number}[];importedAt?:string}
interface Puzzle {id:string;fen:string;opponentMove:string;turn:Color;length:number}
interface Problem {sessionId:string;step:number;repeated:boolean;puzzle:Puzzle;legalMoves:string[]}
interface Result {success:boolean;ratingBefore:number|null;ratingAfter:number|null;rating:number;ratingDeviation:number;plays:number;popularity:number;themes:string[];gameUrl:string;opening:string|null;solution:string[]}
interface MoveResponse {correct:boolean;step:number;reply?:string|null;done?:boolean;legalMoves?:string[];result:Result|Pick<Result,'success'|'ratingBefore'|'ratingAfter'>|null}
type Phase='opponent'|'solving'|'checking'|'wrong'|'done'

// Lichess theme tags, translated; unknown tags are shown as they are.
const themeLabels:Record<string,string>={mate:'Matto',mateIn1:'Matto in 1',mateIn2:'Matto in 2',mateIn3:'Matto in 3',mateIn4:'Matto in 4',mateIn5:'Matto in 5 o più',
  fork:'Forchetta',pin:'Inchiodatura',skewer:'Infilata',discoveredAttack:'Attacco di scoperta',doubleCheck:'Scacco doppio',sacrifice:'Sacrificio',
  deflection:'Deviazione',attraction:'Adescamento',hangingPiece:'Pezzo indifeso',trappedPiece:'Pezzo intrappolato',backRankMate:'Matto sulla traversa',
  smotheredMate:'Matto affogato',promotion:'Promozione',underPromotion:'Sottopromozione',advancedPawn:'Pedone avanzato',endgame:'Finale',
  middlegame:'Mediogioco',opening:'Apertura',short:'Breve',long:'Lungo',veryLong:'Molto lungo',oneMove:'Una mossa',crushing:'Vantaggio decisivo',
  advantage:'Vantaggio',equality:'Salvare la partita',defensiveMove:'Mossa difensiva',quietMove:'Mossa tranquilla',zugzwang:'Zugzwang',
  xRayAttack:'Attacco a raggi X',intermezzo:'Mossa intermedia',clearance:'Sgombero',interference:'Interferenza',capturingDefender:'Eliminare il difensore',
  kingsideAttack:'Attacco sul lato di re',queensideAttack:'Attacco sul lato di donna',exposedKing:'Re esposto',enPassant:'En passant',castling:'Arrocco',
  rookEndgame:'Finale di torri',pawnEndgame:'Finale di pedoni',queenEndgame:'Finale di donne',bishopEndgame:'Finale di alfieri',knightEndgame:'Finale di cavalli',
  queenRookEndgame:'Finale donna e torre',master:'Partita di maestri',masterVsMaster:'Maestro contro maestro',superGM:'Super GM',
  anastasiaMate:'Matto di Anastasia',arabianMate:'Matto arabo',bodenMate:'Matto di Boden',doubleBishopMate:'Matto dei due alfieri',dovetailMate:'Matto a coda di rondine',
  hookMate:'Matto ad uncino',killBoxMate:'Matto a scatola',vukovicMate:'Matto di Vuković',balestraMate:'Matto a balestra',cornerMate:'Matto nell’angolo'}
export const themeLabel=(id:string)=>themeLabels[id]??id
const HIDDEN_THEMES=new Set(['short','long','veryLong','oneMove','advantage','crushing','master','masterVsMaster','superGM'])
const LEVELS=[800,1100,1400,1700,2000,2300]
const pause=(ms:number)=>new Promise<void>(resolve=>window.setTimeout(resolve,ms))
const percent=(x:number)=>x>=.995?'>99%':x<.005?'<1%':`${Math.round(x*100)}%`

function boardAfter(fen:string,line:string[]){
  const board=new Chess(fen)
  for(const m of line)board.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]})
  return board
}

/** Probability, according to Maia, that a human of each level plays the whole solution. */
async function maiaEstimate(fen:string,moves:string[]){
  const out:{level:number;first:number;all:number}[]=[]
  for(const level of LEVELS){
    let all=1,first=0
    for(let i=1;i<moves.length;i+=2){
      const before=boardAfter(fen,moves.slice(0,i)).fen()
      const prediction=await maia.predict(before,level,level)
      const p=prediction.moves.find(m=>m.uci===moves[i])?.probability??0
      if(i===1)first=p
      all*=p
    }
    out.push({level,first,all})
  }
  return out
}

export default function Problems({onPlayFrom}:{onPlayFrom?:(fen:string,color:Color,title:string)=>void}={}){
  const [overview,setOverview]=useState<Overview|null>(null)
  const [band,setBand]=useState<number|null>(null)
  const [theme,setTheme]=useState('')
  const [problem,setProblem]=useState<Problem|null>(null)
  const [line,setLine]=useState<string[]>([])
  const [legal,setLegal]=useState<string[]>([])
  const [phase,setPhase]=useState<Phase>('opponent')
  const [failed,setFailed]=useState(false)
  const [result,setResult]=useState<Result|null>(null)
  const [cursor,setCursor]=useState<number|null>(null)
  const [estimate,setEstimate]=useState<{level:number;first:number;all:number}[]|null>(null)
  const [estimateError,setEstimateError]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  // Session whose solution request opened the self-diagnosis: a new problem closes it.
  const [diagnosing,setDiagnosing]=useState<string|null>(null)
  const token=useRef(0)
  // Free retry once the problem is over: the whole solution is known, so moves are checked here and never rated.
  const [practice,setPractice]=useState<{line:string[];state:'solving'|'wrong'|'solved'}|null>(null)
  const practiceTicket=useRef(0)
  const orientation=useBoardOrientation(problem?.puzzle.turn??'w')

  async function refresh(){const next=await api<Overview>('/problems');setOverview(next);return next}
  useEffect(()=>{refresh().catch(e=>setError(e.message));return()=>{token.current++}},[])

  async function start(){
    const ticket=++token.current
    if(problem&&phase!=='done'&&!failed&&problem.step===1)await api(`/problems/sessions/${problem.sessionId}/skip`,{}).catch(()=>{})
    setBusy(true);setError('');setResult(null);setFailed(false);setCursor(null);setPractice(null);practiceTicket.current++;setEstimate(null);setEstimateError('')
    try{
      const next=await api<Problem>('/problems/next',{band,theme:theme||null})
      if(ticket!==token.current)return
      setProblem(next);setLine([]);setLegal(next.legalMoves);setPhase('opponent')
      // The opponent's move is the mistake to punish: show it, then hand over the board.
      await pause(700)
      if(ticket!==token.current)return
      setLine([next.puzzle.opponentMove]);setPhase('solving')
    }catch(e){if(ticket===token.current){setError(e instanceof Error?e.message:'Problema non disponibile');setProblem(null)}}
    finally{if(ticket===token.current)setBusy(false)}
  }

  function finish(final:Result){
    setResult(final);setPhase('done')
    refresh().catch(()=>{})
    const ticket=token.current
    maiaEstimate(problem!.puzzle.fen,[problem!.puzzle.opponentMove,...final.solution]).then(e=>{if(ticket===token.current)setEstimate(e)}).catch(e=>{if(ticket===token.current)setEstimateError(e.message)})
  }

  async function move(uci:string){
    if(!problem||phase!=='solving')return
    const ticket=token.current
    setLine(l=>[...l,uci]);setPhase('checking')
    try{
      const r=await api<MoveResponse>(`/problems/sessions/${problem.sessionId}/moves`,{move:uci,step:problem.step})
      if(ticket!==token.current)return
      if(!r.correct){
        setFailed(true);setPhase('wrong')
        await pause(900)
        if(ticket!==token.current)return
        setLine(l=>l.slice(0,-1));setPhase('solving');return
      }
      setProblem(p=>p&&{...p,step:r.step})
      if(r.reply){
        await pause(450)
        if(ticket!==token.current)return
        setLine(l=>[...l,r.reply!])
      }
      if(r.done)finish(r.result as Result)
      else{setLegal(r.legalMoves??[]);setPhase('solving')}
    }catch(e){if(ticket===token.current){setError(e instanceof Error?e.message:'Verifica non riuscita');setLine(l=>l.slice(0,-1));setPhase('solving')}}
  }

  async function reveal(){
    if(!problem||phase!=='solving')return
    const ticket=token.current
    setBusy(true)
    try{
      const r=await api<{remaining:string[];result:Result}>(`/problems/sessions/${problem.sessionId}/reveal`,{step:problem.step})
      setFailed(true)
      for(const m of r.remaining){
        if(ticket!==token.current)return
        setLine(l=>[...l,m]);await pause(600)
      }
      if(ticket===token.current)finish(r.result)
    }catch(e){if(ticket===token.current)setError(e instanceof Error?e.message:'Soluzione non disponibile')}
    finally{if(ticket===token.current)setBusy(false)}
  }

  const solution=problem&&result?[problem.puzzle.opponentMove,...result.solution]:[]
  // The solver's starting position: after the opponent's move that sets the problem.
  function playFrom(){
    if(!problem||!onPlayFrom)return
    const b=new Chess(problem.puzzle.fen);const m=problem.puzzle.opponentMove
    b.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]})
    onPlayFrom(b.fen(),problem.puzzle.turn,`Problema ${problem.puzzle.id} · ${b.moveNumber()}${problem.puzzle.turn==='w'?'.':'…'}`)
  }
  function restart(){practiceTicket.current++;setCursor(null);setPractice({line:solution.slice(0,1),state:'solving'})}
  async function practiceMove(uci:string){
    if(!problem||practice?.state!=='solving')return
    const ticket=++practiceTicket.current,played=[...practice.line,uci]
    const after=boardAfter(problem.puzzle.fen,played)
    // As in rated play: the stored move or any mate.
    if(uci!==solution[played.length-1]&&!after.isCheckmate()){
      setPractice({line:played,state:'wrong'})
      await pause(900)
      if(ticket===practiceTicket.current)setPractice({line:practice.line,state:'solving'})
      return
    }
    const reply=after.isCheckmate()?undefined:solution[played.length]
    setPractice({line:played,state:reply?'solving':'solved'})
    if(!reply)return
    await pause(450)
    if(ticket===practiceTicket.current)setPractice({line:[...played,reply],state:'solving'})
  }

  const shown=practice?practice.line:cursor===null?line:line.slice(0,cursor)
  const board=problem?boardAfter(problem.puzzle.fen,shown):null
  const lastMove=shown.at(-1)
  const solverMoves=problem?.puzzle.length??0
  const visibleThemes=result?.themes.filter(t=>!HIDDEN_THEMES.has(t))??[]
  const sanLine=result&&problem?(()=>{const b=new Chess(problem.puzzle.fen);return [problem.puzzle.opponentMove,...result.solution].map(m=>b.move({from:m.slice(0,2),to:m.slice(2,4),promotion:m[4]}).san)})():[]
  const change=result?.ratingAfter!=null&&result.ratingBefore!=null?result.ratingAfter-result.ratingBefore:null

  const filters=overview?.available&&<section className="panel problems-filters">
    <span className="eyebrow">FASCIA DI DIFFICOLTÀ</span>
    <div className="chip-row" role="group" aria-label="Fascia di rating">
      <button className="chip" aria-pressed={band===null} onClick={()=>setBand(null)} title={`Problemi entro ${overview.adaptiveRange} punti dal tuo rating`}>Adattiva · {overview.rating}</button>
      {overview.bands.map(b=><button key={b.id} className="chip" aria-pressed={band===b.id} disabled={!b.count} onClick={()=>setBand(b.id)} title={`${b.count} problemi · ${b.solved}/${b.attempts} risolti al primo tentativo`}>{b.label}{b.attempts>0&&<small className="chip-stat">{b.solved}/{b.attempts}</small>}</button>)}
    </div>
    <label className="problems-theme">Tema <select value={theme} onChange={e=>setTheme(e.target.value)}>
      <option value="">Tutti i temi</option>
      {overview.themes.filter(t=>!HIDDEN_THEMES.has(t.id)).map(t=><option key={t.id} value={t.id}>{themeLabel(t.id)} ({t.count})</option>)}
    </select></label>
  </section>

  return <div className="prevention problems">
    {error&&<div className="alert" role="alert">{error}<button disabled={busy} onClick={()=>{setError('');void refresh()}}>Riprova</button></div>}
    {overview?.available&&<div className="prevention-summary"><span><strong>{overview.rating}</strong> il tuo rating problemi</span><span><strong>{overview.solved} / {overview.attempts}</strong> risolti al primo tentativo</span><span><strong>{overview.total.toLocaleString('it-IT')}</strong> problemi da partite reali</span></div>}
    {!overview?<p role="status">Caricamento…</p>:!overview.available?<section className="panel prevention-intro"><span className="eyebrow">DA INSTALLARE</span><h2>Database dei problemi non presente</h2>
      <p>I problemi provengono dal database pubblico di Lichess (licenza CC0). Per scaricarne una selezione per fasce di rating esegui, nella cartella del progetto:</p>
      <pre className="command">make puzzles</pre>
      <p>Il download scorre il file compresso senza salvarlo e si ferma quando tutte le fasce sono piene: in genere pochi secondi e circa 7 MB su disco. Poi ricarica questa pagina.</p></section>
    :!problem?<>{filters}<section className="panel prevention-intro"><span className="eyebrow">COME FUNZIONA</span><h2>Punisci l’errore dell’avversario</h2>
      <p>Ogni problema nasce da una partita reale giocata su Lichess. La prima mossa, mostrata sulla scacchiera, è quella dell’avversario: di solito un errore. Tocca a te trovare la sequenza che lo sfrutta.</p>
      <p>La difficoltà è il rating del problema, calcolato su Lichess dai tentativi di chi lo ha risolto: non è l’Elo di chi ha giocato la partita. Il tuo rating sale o scende solo al primo tentativo.</p>
      <button className="primary" disabled={busy} onClick={()=>void start()}>Inizia →</button>
      <InfoNote summary="Da dove vengono i problemi"><p>Selezione del <a href={overview.source} target="_blank" rel="noreferrer">database dei puzzle di Lichess</a>: solo problemi con popolarità alta, rating stabile e molti tentativi. Funziona offline. {overview.importedAt&&`Importati il ${new Date(overview.importedAt).toLocaleDateString('it-IT')}.`}</p></InfoNote></section></>
    :<div className="training-layout layout-prevention">
      <section className="board-column">
        <div className="player-row"><span className="avatar">{problem.puzzle.turn==='w'?'♙':'♟'}</span><div className="player-info"><strong>{problem.puzzle.turn==='w'?'Muove il Bianco':'Muove il Nero'}</strong><small>{phase==='done'?`Problema ${problem.puzzle.id}`:`Trova ${solverMoves===1?'la mossa vincente':`la sequenza vincente · ${solverMoves} mosse`}`}</small></div></div>
        <Board fen={board!.fen()} orientation={orientation} legalMoves={practice?board!.moves({verbose:true}).map(m=>m.from+m.to+(m.promotion??'')):legal}
          interactive={practice?practice.state==='solving'&&practice.line.length%2===1:phase==='solving'&&!busy&&cursor===null&&diagnosing!==problem.sessionId}
          onMove={m=>void (practice?practiceMove(m):move(m))} lastMove={lastMove} animateMove/>
        {phase==='done'&&!practice&&<div className="board-toolbar review-controls"><button aria-label="Posizione iniziale" onClick={()=>setCursor(0)} disabled={cursor===0}>⏮</button><button aria-label="Mossa precedente" onClick={()=>setCursor(c=>Math.max(0,(c??line.length)-1))} disabled={cursor===0}>◀</button><span>{cursor??line.length} / {line.length}</span><button aria-label="Mossa successiva" onClick={()=>setCursor(c=>c===null||c+1>=line.length?null:c+1)} disabled={cursor===null}>▶</button><button aria-label="Ultima posizione" onClick={()=>setCursor(null)} disabled={cursor===null}>⏭</button></div>}
      </section>
      <aside className="coach-column">
        <section className={`puzzle-feedback ${practice?(practice.state==='solved'?'solved':practice.state==='wrong'?'retry':''):phase==='done'?(result?.success?'solved':''):phase==='wrong'?'retry':''}`} aria-label="Esito del problema">
          {practice?<div role="status" aria-live="polite">
            <h3>{practice.state==='wrong'?'✗ Non è la mossa giusta':practice.state==='solved'?'✓ Sequenza completata':'↺ Pratica dalla posizione iniziale'}</h3>
            <p>{practice.state==='wrong'?'La scacchiera torna alla posizione precedente.':practice.state==='solved'?'Puoi ricominciare quante volte vuoi.':'Rigioca la soluzione: la pratica non cambia il rating.'}</p>
          </div>:<div role="status" aria-live="polite">
            <h3>{phase==='opponent'?'L’avversario muove…':phase==='checking'?'Verifica…':phase==='wrong'?'✗ Non è la mossa giusta':phase==='done'?(result?.success?'✓ Problema risolto!':'Soluzione completa'):failed?'↻ Riprova':'Tocca a te'}</h3>
            <p>{phase==='wrong'?'La scacchiera torna alla posizione precedente: il primo tentativo è già registrato, ma puoi continuare.':phase==='done'?(change!==null?`Rating ${result!.ratingBefore} → ${result!.ratingAfter} (${change>=0?'+':''}${change}).`:'Questo problema era già stato valutato.'):'Cerca catture, scacchi e minacce: il vantaggio nasce dall’ultima mossa dell’avversario.'}</p>
          </div>}
          <div className="row">
            {phase!=='done'?<><button disabled={busy||phase!=='solving'||diagnosing===problem.sessionId} onClick={()=>setDiagnosing(problem.sessionId)}>Mostra soluzione</button><button disabled={busy} onClick={()=>void start()}>{failed||problem.step>1?'Prossimo problema':'Salta'}</button></>
            :<><button className="primary" disabled={busy} onClick={()=>void start()}>Prossimo problema →</button><button title="Riporta la scacchiera alla posizione iniziale per riprovare: non cambia il rating" onClick={restart}>↺ Riprova da capo</button>{onPlayFrom&&<button className="play-from" title="Nuova partita contro Maia dalla posizione in cui tocca a te" onClick={playFrom}>Gioca da qui col {problem.puzzle.turn==='w'?'Bianco':'Nero'}</button>}</>}
            <button className="quiet" disabled={busy&&phase!=='done'} onClick={()=>{token.current++;setProblem(null);setBusy(false)}}>Cambia fascia</button>
          </div>
          {problem.repeated&&phase!=='done'&&<p className="footnote">Hai già visto tutti i problemi di questa selezione: questo è una ripetizione.</p>}
        </section>
        {diagnosing===problem.sessionId&&<FailureDiagnosis kind="problem" targetId={problem.puzzle.id} sessionId={problem.sessionId} onReveal={()=>void reveal()} onCancel={()=>setDiagnosing(null)}/>}
        {result&&<section className="panel"><span className="eyebrow">IL PROBLEMA</span><h2>Rating {result.rating} <small className="muted">± {result.ratingDeviation}</small></h2>
          <p className="variation">{sanLine.map((san,i)=><span key={i} className={i===0?'muted':undefined}>{san}{' '}</span>)}</p>
          {visibleThemes.length>0&&<div className="chip-row">{visibleThemes.map(t=><span key={t} className="chip">{themeLabel(t)}</span>)}</div>}
          <p className="footnote">{result.plays.toLocaleString('it-IT')} tentativi su Lichess{result.opening?` · ${result.opening}`:''} · <a href={result.gameUrl} target="_blank" rel="noreferrer">partita originale</a> (richiede connessione)</p></section>}
        {result&&<section className="panel maia-estimate"><span className="eyebrow">STIMA MAIA</span><h3>Chi lo risolverebbe d’istinto?</h3>
          {estimate?<ul className="bar-list">{estimate.map(e=><li key={e.level}><div className="bar-label"><span>Livello {e.level}</span><b>{percent(e.all)} <small>{solverMoves>1?`prima mossa ${percent(e.first)}`:''}</small></b></div><div className="bar-track" aria-hidden="true"><span style={{width:`${Math.max(2,e.all*100)}%`}}/></div></li>)}</ul>
          :estimateError?<p>{estimateError}</p>:<p role="status">Calcolo nel browser…</p>}
          <InfoNote summary="Come leggere la stima"><p>Probabilità che Maia, impostata sul livello indicato, giochi tutte le mosse della soluzione al primo colpo. Misura quanto la soluzione è “naturale” per un umano di quel livello, non il tempo di riflessione: chi calcola con calma la trova più spesso. Le varianti alternative di matto accettate non sono contate.</p></InfoNote></section>}
      </aside>
    </div>}
  </div>
}
