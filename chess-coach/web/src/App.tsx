import { useEffect, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import Board from './Board'
import Drills from './Drills'
import TutorPanel from './TutorPanel'
import { api } from './api'
import { maia, sample, type Prediction } from './engine/maia'
import type { Game, Color, Exercise, Attempt, Profile, Analysis, Evaluation, PuzzleSession } from './types'

type Tab = 'play' | 'review' | 'drill' | 'train' | 'progress'
type Saved = {id:string; title:string; createdAt:string; plies:number; source:string}
const initialFen = new Chess().fen()
const titles: Record<Tab, string> = {play:'Una mossa alla volta.',review:'Capisci le tue scelte.',drill:'Allena una sequenza.',train:'Trasforma gli errori in pratica.',progress:'Il tuo percorso, nel tempo.'}
function position(game: Game, ply: number) {
  const board = new Chess(game.initialFen)
  for (const move of game.moves.slice(0, ply)) board.move({from:move.slice(0,2),to:move.slice(2,4),promotion:move[4]})
  return board
}
function score(evaluation: Evaluation) { return evaluation.mate !== null ? `Matto ${evaluation.mate > 0 ? '+' : ''}${evaluation.mate}` : (evaluation.cp / 100).toFixed(2) }

export default function App() {
  const [tab, setTab] = useState<Tab>('play')
  const [game, setGame] = useState<Game | null>(null)
  const [saved, setSaved] = useState<Saved[]>([])
  const [profile, setProfile] = useState<Profile | null>(null)
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [exercise, setExercise] = useState<Exercise | null>(null)
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [session, setSession] = useState<PuzzleSession | null>(null)
  const [hint, setHint] = useState('')
  const [color, setColor] = useState<Color>('w')
  const [elo, setElo] = useState(1500)
  const [busy, setBusy] = useState(false)
  const [botThinking, setBotThinking] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [maiaStatus, setMaiaStatus] = useState(maia.status)
  const [stockfish, setStockfish] = useState('Connessione…')
  const [cursor, setCursor] = useState(0)
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [pgn, setPgn] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [retry, setRetry] = useState(0)
  const [requestedDrill,setRequestedDrill] = useState<string|null>(null)
  const currentGame = useRef<Game | null>(null)
  currentGame.current = game

  async function refresh() {
    const [games, skills, drills] = await Promise.all([api<Saved[]>('/games'),api<Profile>('/profile'),api<Exercise[]>('/exercises')])
    setSaved(games); setProfile(skills); setExercises(drills)
  }
  function keepGame(next: Game) { setGame(next); localStorage.setItem('chess-coach-game', next.id) }
  function fail(reason: unknown) { setError(reason instanceof Error ? reason.message : 'Operazione non riuscita') }
  useEffect(() => {
    maia.onStatus = setMaiaStatus
    Promise.all([refresh(), api<{stockfish:string}>('/health').then(h => setStockfish(h.stockfish))]).catch(fail)
    const id = localStorage.getItem('chess-coach-game')
    if (id) api<Game>('/games/' + id).then(g => { keepGame(g); setCursor(g.version); setTab('review') }).catch(()=>localStorage.removeItem('chess-coach-game'))
    return () => { maia.onStatus = () => {} }
  }, [])

  useEffect(() => {
    if (!game || game.result || game.source !== 'maia' || game.turn === game.playerColor || tab !== 'play' || jobId) return
    let cancelled = false
    const snapshot = game
    setBotThinking(true)
    ;(async () => {
      const policy = await maia.predict(snapshot.fen, snapshot.elo, snapshot.elo)
      const move = sample(policy)
      if (cancelled || !move) return
      const updated = await api<Game>(`/games/${snapshot.id}/moves`, {move, version:snapshot.version, actor:'maia'})
      if (!cancelled && currentGame.current?.id === snapshot.id) keepGame(updated)
    })().catch(e => { if (!cancelled) fail(e) }).finally(()=> { if (!cancelled) setBotThinking(false) })
    return () => { cancelled = true; setBotThinking(false) }
  }, [game?.id, game?.version, tab, retry, jobId])

  useEffect(() => {
    if (!jobId) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const job = await api<{status:string; progress:number; gameId:string; result?:Analysis; error?:string}>('/jobs/'+jobId)
        if (stopped) return
        setProgress(job.progress)
        if (job.status === 'complete') {
          const updated = await api<Game>('/games/'+job.gameId)
          if (currentGame.current?.id === updated.id) { keepGame(updated); setCursor(job.result?.critical[0]?.ply ?? updated.version) }
          setJobId(null); setNotice('Revisione pronta. Gli esercizi personali sono nella sezione Puzzle.'); await refresh()
        } else if (job.status === 'failed') { throw new Error(job.error || 'Analisi non riuscita') }
        else timer = setTimeout(poll, 500)
      } catch (e) { if (!stopped) { fail(e); setJobId(null) } }
    }
    poll()
    return () => { stopped = true; clearTimeout(timer) }
  }, [jobId])

  const reviewBoard = game ? position(game, cursor) : new Chess()
  const boardFen = tab === 'train' && exercise ? exercise.fen : tab === 'review' ? reviewBoard.fen() : game?.fen || initialFen
  const orientation: Color = tab === 'train' && exercise ? exercise.turn : game?.playerColor || color
  const legal = tab === 'train' ? exercise?.legalMoves || [] : game?.legalMoves || []
  const canMove = !busy && !jobId && (tab === 'train' ? !!exercise && !!session && !attempt?.closed : tab === 'play' && !!game && !game.result && game.source === 'maia' && game.turn === game.playerColor && !botThinking)
  const decision = game?.analysis?.decisions.find(d=>d.ply === cursor)

  useEffect(() => {
    setPrediction(null)
    if (tab !== 'review' || !game || reviewBoard.isGameOver()) return
    let stale = false
    const timer = setTimeout(() => {
      maia.predict(reviewBoard.fen(),game.elo,game.elo).then(p => { if (!stale) setPrediction(p) }).catch(e=> { if (!stale) fail(e) })
    }, 150)
    return () => {stale = true; clearTimeout(timer)}
  }, [tab, boardFen, game?.elo])

  async function startGame() {
    setBusy(true); setError(''); setNotice('')
    try { const next = await api<Game>('/games',{color,elo}); keepGame(next); setTab('play'); setCursor(0); await refresh(); maia.load().catch(fail) }
    catch (e) {fail(e)} finally {setBusy(false)}
  }
  async function submitMove(move: string) {
    if (!canMove) return
    setBusy(true); setError('')
    try {
      if (tab === 'train' && exercise && session) { const result = await api<Attempt>(`/exercises/${exercise.id}/attempts`,{move,session_id:session.id,version:session.version}); setAttempt(result); setSession({...session,version:result.version}); await refresh() }
      else if (game) { const next = await api<Game>(`/games/${game.id}/moves`,{move,version:game.version,actor:'human'}); keepGame(next) }
    } catch (e) {fail(e)} finally {setBusy(false)}
  }
  async function analyze() {
    if (!game) return
    setBusy(true); setError(''); setTab('review'); setCursor(game.version)
    try { const result = await api<{jobId:string}>(`/games/${game.id}/analysis`,{}); setProgress(0); setJobId(result.jobId) }
    catch (e) {fail(e)} finally {setBusy(false)}
  }
  async function openGame(id: string) {
    setBusy(true); setError('')
    try {const next = await api<Game>('/games/'+id); keepGame(next); setCursor(next.version); setTab('review')}
    catch(e){fail(e)} finally {setBusy(false)}
  }
  async function importPgn() {
    setBusy(true); setError('')
    try {const next=await api<Game>('/import',{pgn,color}); keepGame(next); setCursor(next.version); setTab('review'); setShowImport(false); setPgn(''); await refresh()}
    catch(e){fail(e)} finally {setBusy(false)}
  }
  async function pickExercise(ex: Exercise) {
    setExercise(ex); setAttempt(null); setSession(null); setHint(''); setTab('train'); setError(''); setBusy(true)
    try {setSession(await api<PuzzleSession>(`/exercises/${ex.id}/sessions`,{}))}catch(e){fail(e)}finally{setBusy(false)}
  }
  async function puzzleHelp(reveal=false) {
    if(!exercise||!session)return
    setBusy(true)
    try {
      if(reveal){const result=await api<Attempt>(`/exercises/${exercise.id}/reveal`,{session_id:session.id});setAttempt(result);await refresh()}
      else{const result=await api<{hint:string}>(`/exercises/${exercise.id}/hint`,{session_id:session.id});setHint(result.hint)}
    }catch(e){fail(e)}finally{setBusy(false)}
  }
  function downloadPgn() {
    if (!game) return
    const url=URL.createObjectURL(new Blob([game.pgn],{type:'application/x-chess-pgn'}))
    const link=document.createElement('a'); link.href=url; link.download='chess-coach.pgn'; link.click(); URL.revokeObjectURL(url)
  }
  function navigate(next: Tab) {setTab(next); setError(''); setNotice(''); if(next==='review'&&game)setCursor(game.version); if(next==='train'&&!exercise&&exercises[0])pickExercise(exercises[0]); refresh().catch(fail)}

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={e=>{e.preventDefault();navigate('play')}}><span className="brand-mark">♞</span><span>chess<span className="brand-light">coach</span><small>IL TUO SPAZIO DI ALLENAMENTO</small></span></a>
      <nav aria-label="Navigazione principale">{([['play','♟','Gioca'],['review','◉','Rivedi'],['drill','◇','Drill'],['train','◎','Puzzle'],['progress','↗','Progressi']] as const).map(([key,icon,label]) => <button key={key} className={tab===key?'nav-item active':'nav-item'} onClick={()=>navigate(key)} aria-current={tab===key?'page':undefined}><span aria-hidden="true">{icon}</span>{label}{key==='train'&&!!profile?.due&&<b>{profile.due}</b>}</button>)}</nav>
      <div className="sidebar-note"><span className="eyebrow">IL METODO</span><p>Gioca. Comprendi.<br/>Riprova.</p><small>Un passo concreto, ogni giorno.</small></div>
      <div className="local-status"><span className="status-dot"/> Spazio personale locale<small>Partite archiviate su questo computer.</small></div>
    </aside>
    <main>
      <header className="topbar"><span>Il tuo allenamento</span><span className="pill">Maia + Stockfish <span className="status-dot"/></span></header>
      <section className="page-intro"><div><span className="eyebrow">CHESS COACH / {tab==='play'?'SPARRING':tab==='review'?'REVISIONE':tab==='train'?'PUZZLE':tab==='drill'?'DRILL':'PERCORSO'}</span><h1>{titles[tab]}</h1><p>{tab==='play'?'Un avversario dal gioco umano. Uno spazio per migliorare.':tab==='review'?'Confronta mosse plausibili e conseguenze sulla scacchiera.':tab==='train'?'Riparti dalle decisioni delle tue partite, senza suggerimenti anticipati.':tab==='drill'?'Metti in pratica un piano contro Maia, poi rivedi le tue decisioni.':'Osservazioni reali, piccoli obiettivi e ripassi mirati.'}</p></div><button className="quiet" onClick={()=>setShowImport(!showImport)}>↑ Importa PGN</button></section>
      {error&&<div className="alert" role="alert">{error}<button onClick={()=>{setError('');setRetry(x=>x+1)}}>Riprova</button></div>}
      {notice&&<div className="notice" role="status">{notice}</div>}
      {showImport&&<section className="panel import-panel"><h2>Importa una partita</h2><p className="muted">Incolla una singola partita PGN e seleziona il colore che vuoi analizzare.</p><textarea aria-label="Partita PGN" value={pgn} onChange={e=>setPgn(e.target.value)} rows={5} placeholder={'[White "Giocatore"]\n[Black "Avversario"]\n\n1. e4 e5 2. Nf3 Nc6 *'}/><div className="row"><label>Il tuo colore <select value={color} onChange={e=>setColor(e.target.value as Color)}><option value="w">Bianco</option><option value="b">Nero</option></select></label><button className="primary" disabled={busy||!pgn.trim()} onClick={importPgn}>Importa partita</button><button onClick={()=>setShowImport(false)}>Chiudi</button></div></section>}

      {tab==='drill'?<Drills startTemplateId={requestedDrill} onStarted={()=>setRequestedDrill(null)} onReview={g=>{keepGame(g);setCursor(g.version);setTab('review');refresh().catch(fail)}}/>:tab==='progress'?<div className="progress-layout">
        <section className="panel"><span className="eyebrow">IL TUO PIANO</span><h2>25 minuti per allenarti</h2>{profile?.plan.map((item,i)=><div className="plan-row" key={item.title}><span className="step-number">0{i+1}</span><div><h3>{item.title}</h3><p>{item.description}</p></div><span className="duration">{item.minutes} min</span></div>)}<button className="primary" onClick={()=>navigate(exercises.length?'train':'play')}>Inizia la sessione →</button></section>
        <section className="panel"><span className="eyebrow">LE TUE OSSERVAZIONI</span><h2>{profile?.confidence||'Nessun dato'}</h2><div className="stats"><div><strong>{profile?.games||0}</strong><span>partite salvate</span></div><div><strong>{profile?.attempts||0}</strong><span>tentativi</span></div><div><strong>{profile?.unaidedSuccesses||0}</strong><span>primi tentativi riusciti</span></div></div>{profile?.themes.length?profile.themes.map(t=><div className="theme-row" key={t.theme}><span>{t.theme}</span><span>{t.examples} posizioni</span></div>):<p className="empty-text">Analizza una partita per iniziare a raccogliere le tue posizioni di allenamento.</p>}<p className="footnote">I successi contano solo il primo tentativo senza aiuti, su esercizi nuovi o in scadenza. Le ripetizioni immediate restano pratica. Non sono ancora una misura di padronanza: servono anche verifiche su posizioni nuove.</p></section>
      </div>:<div className="training-layout">
        <section className="board-column">
          <div className="player-row"><span className="avatar">{tab==='train'?'◎':'♞'}</span><div><strong>{tab==='train'?'Posizione di allenamento':orientation==='w'?'Maia':'Tu'}</strong><small>{tab==='train'?exercise?.theme||'Scegli un esercizio':orientation==='w'?`Livello ${game?.elo||elo} · gioco umano`:'Il tuo colore: Nero'}</small></div>{tab==='play'&&botThinking&&<span className="thinking" role="status">Maia sta pensando…</span>}</div>
          <Board fen={boardFen} orientation={orientation} interactive={canMove} legalMoves={legal} onMove={submitMove} lastMove={tab==='play'?game?.moves.at(-1):tab==='review'&&game&&cursor>0?game.moves[cursor-1]:undefined}/>
          <div className="player-row lower"><span className="avatar light">{orientation==='w'?'♙':'♞'}</span><div><strong>{tab==='train'?(exercise?.turn==='b'?'Muove il Nero':'Muove il Bianco'):orientation==='w'?'Tu':'Maia'}</strong><small>{tab==='play'?(game?.result?`Partita conclusa · ${game.result}`:canMove?'Tocca a te · scegli un pezzo e la destinazione':game?'Attendi la risposta':'Pronto per iniziare'):tab==='review'?`Posizione dopo ${cursor} semimosse`:'Cerca una buona mossa'}</small></div><span className="mode-label">{tab==='play'?'PARTITA LIBERA':tab==='review'?'ANALISI':'ESERCIZIO'}</span></div>
          {tab==='review'&&game&&<div className="review-controls"><button aria-label="Posizione iniziale" onClick={()=>setCursor(0)} disabled={cursor===0}>⏮</button><button aria-label="Mossa precedente" onClick={()=>setCursor(c=>Math.max(0,c-1))} disabled={cursor===0}>←</button><span>{cursor} / {game.version}</span><button aria-label="Mossa successiva" onClick={()=>setCursor(c=>Math.min(game.version,c+1))} disabled={cursor===game.version}>→</button><button aria-label="Ultima posizione" onClick={()=>setCursor(game.version)} disabled={cursor===game.version}>⏭</button></div>}
        </section>
        <aside className="coach-column">
          {tab==='play'&&<>
            <section className="panel"><span className="eyebrow">IL TUO SPARRING PARTNER</span><h2>Allenati con Maia</h2><p className="muted">Mosse e imperfezioni ispirate al gioco umano.</p><label className="field-label">Livello di riferimento <strong>{elo}</strong><input aria-label="Livello Maia" type="range" min="600" max="2600" step="100" value={elo} onChange={e=>setElo(Number(e.target.value))}/></label><div className="range-labels"><span>600</span><span>2600</span></div><label className="field-label">Il tuo colore<select value={color} onChange={e=>setColor(e.target.value as Color)}><option value="w">Bianco</option><option value="b">Nero</option></select></label><button className="primary full" onClick={startGame} disabled={busy||!!jobId||botThinking}>{game?'Nuova partita':'Inizia partita'} →</button><small className="footnote">Il livello guida il modello; non equivale a un rating agonistico certificato.</small></section>
            <section className="panel tutor-card"><span className="eyebrow">IL TUTOR OSSERVA</span><h3>Concentrati sulla partita.</h3><p>Alla fine rivedremo le decisioni più interessanti e creeremo esercizi dalle tue posizioni.</p><button className="full" disabled={!game?.version||busy||botThinking||!!jobId} onClick={analyze}>Rivedi questa partita</button></section>
            <div className="engine-status"><span className={maiaStatus==='Maia pronto'?'status-dot':'status-dot waiting'}/>{maiaStatus}<small>{stockfish}</small></div>
          </>}
          {tab==='review'&&<>{game&&<TutorPanel key={game.id+':'+game.version+':'+game.analysis?.createdAt} game={game} disabled={!!jobId||!game.analysis} onPosition={setCursor} onPuzzle={id=>{const ex=exercises.find(e=>e.id===id);if(ex)pickExercise(ex);else fail(new Error('Esercizio non disponibile: ricarica la pagina.'))}} onDrill={id=>{setRequestedDrill(id);setTab('drill')}}/>}
            <section className="panel"><span className="eyebrow">MOMENTI DA RIVEDERE</span><h2>Trova un'alternativa</h2>{jobId?<div role="status"><p>Stockfish analizza la partita… {progress}%</p><progress value={progress} max={100}/></div>:!game?<p className="empty-text">Gioca una partita o importa un PGN per iniziare.</p>:<>{!game.analysis?<p className="muted">Avvia la revisione per individuare le decisioni da allenare.</p>:game.analysis.critical.length?game.analysis.critical.map(d=><button className={`moment ${cursor===d.ply?'chosen':''}`} key={d.ply} onClick={()=>setCursor(d.ply)}><span>{Math.floor(d.ply/2)+1}{d.ply%2?'…':'.'} {d.playedSan}</span><span>{d.label}</span><small>{d.theme}</small></button>):<p className="muted">Nessun errore rilevante individuato nel budget di analisi. Non significa gioco perfetto.</p>}<button className="full" onClick={analyze} disabled={busy||!game.version}>{game.analysis?'Ricalcola analisi':'Analizza partita'}</button></>}{decision&&<div className="decision"><h3>Hai giocato {decision.playedSan}</h3><p>Alternativa: <strong>{decision.best.san[0]||'—'}</strong></p><p className="variation">{decision.best.san.join(' ')}</p><small>Valutazione dal lato che muove: {score(decision.actual)} → {score(decision.best)}. Profondità {decision.best.depth}.</small></div>}</section>
            <section className="panel"><span className="eyebrow">LO SGUARDO DI MAIA</span><h3>Mosse umane plausibili</h3>{prediction?.moves.slice(0,3).map(m=><div className="policy" key={m.uci}><strong>{m.san}</strong><div><span style={{width:`${m.probability*100}%`}}/></div><span>{Math.round(m.probability*100)}%</span></div>)}{!prediction&&<p className="muted">{game?'Caricamento delle previsioni…':'Nessuna posizione selezionata.'}</p>}<small className="footnote">Probabilità del modello, non giudizi sulla qualità delle mosse.</small></section>
            {game&&<div className="row"><button onClick={downloadPgn}>↓ Esporta PGN</button>{game.source==='maia'&&!game.result&&<button disabled={!!jobId} onClick={()=>setTab('play')}>Continua partita</button>}</div>}
          </>}
          {tab==='train'&&<section className="panel"><span className="eyebrow">DALLE TUE PARTITE</span><h2>{exercise?exercise.theme:'Il tuo primo esercizio'}</h2>{!exercise?<p className="empty-text">Gli esercizi nasceranno dalla revisione delle tue partite. Gioca o importa un PGN, poi avvia l'analisi.</p>:<><p className="muted">Muovi sulla scacchiera. Sono accettate anche alternative che mantengono la qualità della posizione.</p>{!attempt?.closed&&session&&<div className="row"><button disabled={busy} onClick={()=>puzzleHelp()}>Chiedi un indizio</button><button disabled={busy} onClick={()=>puzzleHelp(true)}>Mostra soluzione</button></div>}{hint&&<p className="hint">{hint}</p>}{busy&&<p role="status">Stockfish verifica la tua mossa…</p>}{attempt&&<div className={attempt.success?'attempt success':'attempt'} role="status"><h3>{attempt.success?'Buona scelta.':'Una posizione da riprovare.'}</h3><p>{attempt.message}</p><p className="variation">{attempt.best?.san.join(' ')}</p><small>{attempt.assisted?'Tentativo con indizio.':'Tentativo senza indizi.'} Ripasso: {new Date(attempt.dueAt).toLocaleDateString('it-IT')}.</small></div>}</>}<div className="exercise-list">{exercises.map(ex=><button key={ex.id} className={exercise?.id===ex.id?'exercise-link chosen':'exercise-link'} disabled={busy} onClick={()=>pickExercise(ex)}><span>{ex.theme}</span><small>Mossa {Math.floor(ex.ply/2)+1} · {new Date(ex.dueAt).getTime()<=Date.now()?'da ripassare':'programmato'}</small></button>)}</div></section>}
        </aside>
      </div>}
      <section className="archive"><div className="section-head"><h2>Le tue partite</h2><span>{saved.length} salvate</span></div>{saved.length?<div className="game-list">{saved.slice(0,6).map(item=><button key={item.id} onClick={()=>openGame(item.id)} disabled={!!jobId||busy}><span className="archive-icon">♟</span><span><strong>{item.title}</strong><small>{new Date(item.createdAt).toLocaleDateString('it-IT')} · {item.plies} semimosse · {item.source==='pgn'?'Importata':'Maia'}</small></span><span className="arrow">↗</span></button>)}</div>:<p className="empty-text">Le partite vengono salvate automaticamente, mossa dopo mossa.</p>}</section>
      <footer>Chess Coach · Prototipo locale <span>Maia per il gioco umano. Stockfish per la verifica.</span></footer>
    </main>
  </div>
}
