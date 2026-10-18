import { useEffect, useMemo, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import Board, {type AnalysisArrow} from './Board'
import Drills from './Drills'
import BlunderPrevention from './BlunderPrevention'
import Problems from './Problems'
import TutorPanel from './TutorPanel'
import FinalReview from './FinalReview'
import RatingPanel from './RatingPanel'
import DecisionQuality from './DecisionQuality'
import LearningProgress from './LearningProgress'
import PositionJudgment from './PositionJudgment'
import FailureDiagnosis from './FailureDiagnosis'
import MoveReview from './MoveReview'
import MoveHistory from './MoveHistory'
import PanelTabs from './PanelTabs'
import PuzzleFeedback from './PuzzleFeedback'
import TrainingPlan from './TrainingPlan'
import ImportGames from './ImportGames'
import {usePuzzleComparison} from './usePuzzleComparison'
import MistakeHistory from './MistakeHistory'
import {useTrainingMove} from './useTrainingMove'
import ChessInsights,{ThinkingGuide} from './ChessInsights'
import EvaluationChart from './EvaluationChart'
import PgnExport from './PgnExport'
import LichessAnalysis from './LichessAnalysis'
import ExerciseSource from './ExerciseSource'
import {useMoveTime} from './useMoveTime'
import PlayerBar,{material} from './PlayerBar'
import EvalBar,{MaiaBar,whiteValue,type BarValue} from './EvalBar'
import {usePositionEval} from './usePositionEval'
import {useMaiaScore,type MaiaScore} from './useMaiaScore'
import {useBoardSettings} from './boardSettings'
import {FlipBoardButton,resetBoardFlip,useBoardFlip,useBoardOrientation,useFlipShortcut} from './boardFlip'
import BoardSettingsMenu from './BoardSettingsMenu'
import ReviewSummary from './ReviewSummary'
import GameArchive,{type Saved} from './GameArchive'
import InfoNote from './InfoNote'
import BarList from './BarList'
import Icon from './icons'
import {classifyMove} from './moveClass'
import {evaluationSeries} from './evaluationSeries'
import {useMoveSuggestion,SuggestionBox} from './MoveSuggestion'
import Study from './study/Study'
import {ExamProgress} from './study/MockExam'
import type {StudySection,Refutation} from './study/types'
import { api } from './api'
import { maia, type Prediction } from './engine/maia'
import { chooseMaiaMove } from './engine/play'
import type { Game, Color, Exercise, Attempt, Profile, Analysis, Evaluation, PuzzleSession } from './types'

type Tab = 'schedule' | 'play' | 'review' | 'drill' | 'train' | 'problems' | 'progress' | 'archive' | 'prevention' | 'study'
const initialFen = new Chess().fen()
const navigation:[Tab,string,boolean][]=[['schedule','Allenamento',true],['play','Gioca',true],['review','Rivedi',true],['train','Puzzle',true],['problems','Problemi',false],['study','Studio',false],['drill','Drill',false],['prevention','Blunder prevention',false],['progress','Progressi',false],['archive','Partite',false]]
const levels=[800,1100,1400,1700,2000,2300]
const titles: Record<Tab, string> = {schedule:'Allenamento di oggi',study:'Studio',prevention:'Blunder prevention',play:'Gioca contro Maia',review:'Rivedi la partita',drill:'Drill',train:'Puzzle dalle tue partite',problems:'Problemi da partite reali',progress:'Progressi',archive:'Partite'}
const subtitles: Record<Tab, string> = {schedule:'Ripassi in scadenza e nuove posizioni tratte dalle tue partite.',study:'Flashcard, quiz, esami di prova e quaderno degli errori costruiti dalle tue partite.',prevention:'Trova una mossa sicura nelle posizioni in cui hai commesso un blunder.',play:'Maia gioca come un avversario umano del livello che scegli.',review:'Confronta ogni mossa con Stockfish e con la scelta più probabile di Maia.',drill:'Gioca un’apertura, un finale o una tua posizione critica contro Maia.',train:'Ritrova la mossa giusta nelle posizioni in cui avevi sbagliato.',problems:'Problemi tattici del database Lichess, divisi per fasce di rating.',progress:'Errori, ripassi e temi ricorrenti nelle partite analizzate.',archive:'Apri una partita per riprenderla o rivederla.'}
function position(game: Game, ply: number) {
  const board = new Chess(game.initialFen)
  for (const move of game.moves.slice(0, ply)) board.move({from:move.slice(0,2),to:move.slice(2,4),promotion:move[4]})
  return board
}
function score(evaluation: Evaluation) { return evaluation.mate !== null ? `Matto ${evaluation.mate > 0 ? '+' : ''}${evaluation.mate}` : (evaluation.cp / 100).toFixed(2) }

export default function App({onLogout}:{onLogout?:(()=>void)|null}={}) {
  const [entrySection] = useState<Tab|null>(()=>{
    const section=new URLSearchParams(window.location.search).get('section')
    return section&&['schedule','prevention','archive','drill','progress','study','problems'].includes(section)?section as Tab:null
  })
  const [tab, setTab] = useState<Tab>(entrySection??'play')
  const [reviewTab,setReviewTab] = useState('moves')
  const [arrowSources,setArrowSources]=useState({stockfish:true,maia:true,played:true})
  const [game, setGame] = useState<Game | null>(null)
  const [saved, setSaved] = useState<Saved[]>([])
  const [profile, setProfile] = useState<Profile | null>(null)
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [exercise, setExercise] = useState<Exercise | null>(null)
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [session, setSession] = useState<PuzzleSession | null>(null)
  const [hint, setHint] = useState('')
  // Puzzle session whose solution request opened the self-diagnosis.
  const [diagnosing, setDiagnosing] = useState<string|null>(null)
  const puzzleMotion=useTrainingMove((exercise?.id??'')+':'+(session?.id??''))
  const puzzleMove=puzzleMotion.move
  const puzzleComparison=usePuzzleComparison(exercise,session?.id,tab==='train'&&!!attempt?.success)
  const dueExercises=exercises.filter(ex=>new Date(ex.dueAt).getTime()<=Date.now())
  const [completedPuzzles,setCompletedPuzzles]=useState<string[]>([])
  const [color, setColor] = useState<Color|'random'>('w')
  const [moreOpen,setMoreOpen]=useState(false)
  const [elo, setElo] = useState(1500)
  const [busy, setBusy] = useState(false)
  const [botThinking, setBotThinking] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [maiaStatus, setMaiaStatus] = useState(maia.status)
  const [stockfish, setStockfish] = useState('Connessione…')
  const [cursor, setCursor] = useState(0)
  const [playPosition,setPlayPosition]=useState<{id:string;ply:number}|null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [predictionKey,setPredictionKey] = useState('')
  const [predictionError,setPredictionError] = useState('')
  const [reviewElo,setReviewElo] = useState(1500)
  const [requestedPrevention,setRequestedPrevention]=useState<string|null>(null)
  const [showImport, setShowImport] = useState(()=>new URLSearchParams(window.location.search).get('import')==='pgn')
  const [retry, setRetry] = useState(0)
  const [focusJudgment,setFocusJudgment]=useState(false)
  const [requestedDrill,setRequestedDrill] = useState<string|null>(null)
  // Where a Stockfish refutation game was opened from, to offer the way back.
  const [refutationOrigin,setRefutationOrigin]=useState<{gameId:string;kind:'puzzle'|'prevention'|'study';targetId:string;san:string}|null>(null)
  const [studySection,setStudySection]=useState<StudySection>(()=>{try{return (localStorage.getItem('chess-coach-study-section') as StudySection)||'cards'}catch{return 'cards'}})
  const [studyGame,setStudyGame]=useState<string|null>(null)
  function showStudySection(section:StudySection){setStudySection(section);try{localStorage.setItem('chess-coach-study-section',section)}catch{/* storage unavailable */}}
  const currentGame = useRef<Game | null>(null)
  const watchedJobs=useRef(new Set<string>())
  const botController = useRef<AbortController | null>(null)
  currentGame.current = game
  const moveTime=useMoveTime(game,tab==='play'&&!!game&&!game.result&&!jobId)

  async function refresh() {
    const [games, skills, drills] = await Promise.all([api<Saved[]>('/games'),api<Profile>('/profile'),api<Exercise[]>('/exercises')])
    setSaved(games); setProfile(skills); setExercises(drills)
  }
  function keepGame(next: Game, newTurn=false) { if(newTurn)moveTime.begin(next); setGame(next); localStorage.setItem('chess-coach-game', next.id) }
  function fail(reason: unknown) { setError(reason instanceof Error ? reason.message : 'Operazione non riuscita') }
  useEffect(() => {
    maia.onStatus = setMaiaStatus
    Promise.all([refresh(), api<{stockfish:string}>('/health').then(h => setStockfish(h.stockfish))]).catch(fail)
    const id = localStorage.getItem('chess-coach-game')
    if (id) api<Game>('/games/' + id).then(g => { keepGame(g); setCursor(g.version); if(!entrySection)setTab('review') }).catch(()=>localStorage.removeItem('chess-coach-game'))
    return () => { maia.onStatus = () => {} }
  }, [])

  useEffect(() => {
    if (!game || busy || game.result || (game.source !== 'maia' && game.source !== 'stockfish') || game.turn === game.playerColor || tab !== 'play' || jobId) return
    let cancelled = false
    const controller = new AbortController()
    botController.current = controller
    const snapshot = game
    setBotThinking(true)
    ;(async () => {
      let updated: Game
      if (snapshot.source === 'stockfish') updated = await api<Game>(`/games/${snapshot.id}/engine-move`, {version:snapshot.version, revision:snapshot.revision})
      else {
        const move = await chooseMaiaMove(snapshot.fen, snapshot.elo, controller.signal)
        if (cancelled || controller.signal.aborted || !move) return
        updated = await api<Game>(`/games/${snapshot.id}/moves`, {move, version:snapshot.version, revision:snapshot.revision, actor:'maia',elapsed_seconds:moveTime.elapsed(snapshot)})
      }
      if (!cancelled && !controller.signal.aborted && currentGame.current?.id === snapshot.id) keepGame(updated,true)
    })().catch(e => { if (!cancelled && !controller.signal.aborted) fail(e) }).finally(()=> { if (!cancelled) setBotThinking(false) })
    return () => { cancelled = true; controller.abort(); setBotThinking(false) }
  }, [game?.id, game?.version, game?.revision, tab, retry, jobId, busy])

  useEffect(()=>{
    const id=game?.analysisJobId
    if(id&&!jobId&&!watchedJobs.current.has(id)){
      watchedJobs.current.add(id);setJobId(id);setProgress(0)
      setNotice(game?.result?'Partita conclusa: analisi automatica in corso. Gli esercizi saranno disponibili al termine.':'Analisi della partita in corso. Gli esercizi saranno disponibili al termine.')
    }
  },[game?.analysisJobId,jobId])

  useEffect(() => {
    if (!jobId) return
    watchedJobs.current.add(jobId)
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const job = await api<{status:string; progress:number; gameId:string; result?:Analysis; error?:string}>('/jobs/'+jobId)
        if (stopped) return
        setProgress(job.progress)
        if (job.status === 'complete') {
          const updated = await api<Game>('/games/'+job.gameId)
          if (currentGame.current?.id === updated.id) { keepGame(updated); setCursor(job.result?.moves?.[0]?.ply ?? job.result?.decisions[0]?.ply ?? updated.version) }
          setJobId(null); setNotice('Revisione pronta. Le posizioni adatte sono disponibili in Puzzle e Blunder prevention.'); await refresh()
        } else if (job.status === 'failed') { throw new Error(job.error || 'Analisi non riuscita') }
        else timer = setTimeout(poll, 500)
      } catch (e) { if (!stopped) { fail(e); setJobId(null) } }
    }
    poll()
    return () => { stopped = true; clearTimeout(timer) }
  }, [jobId])

  const playPly=game?playPosition?.id===game.id?Math.min(playPosition.ply,game.moves.length):game.moves.length:0
  const browsingHistory=tab==='play'&&!!game&&playPly<game.moves.length
  function showPlayPosition(ply:number){if(game)setPlayPosition(ply>=game.moves.length?null:{id:game.id,ply:Math.max(0,ply)})}
  const reviewBoard = game ? position(game, cursor) : new Chess()
  const puzzleBoard=exercise?new Chess(exercise.fen):null
  if(puzzleBoard&&puzzleMove&&!puzzleComparison.visible)puzzleBoard.move({from:puzzleMove.slice(0,2),to:puzzleMove.slice(2,4),promotion:puzzleMove[4]})
  const nextPuzzle=dueExercises.find(ex=>ex.id!==exercise?.id&&!completedPuzzles.includes(ex.id))
  const boardFen = tab === 'train' && puzzleBoard ? puzzleBoard.fen() : tab === 'review' ? reviewBoard.fen() : browsingHistory && game ? position(game,playPly).fen() : game?.fen || initialFen
  const orientation: Color = tab === 'train' && exercise ? exercise.turn : game?.playerColor || (color==='b'?'b':'w')
  const legal = tab === 'train' ? exercise?.legalMoves || [] : game?.legalMoves || []
  const canMove = !busy && !jobId && (tab === 'train' ? !!exercise && !!session && !attempt?.closed && diagnosing !== session.id : tab === 'play' && !browsingHistory && !!game && !game.result && (game.source === 'maia' || game.source === 'stockfish') && game.turn === game.playerColor && !botThinking)
  const decision = game?.analysis?.decisions.find(d=>d.ply === cursor)
  const visiblePrediction = predictionKey===boardFen+':'+reviewElo?prediction:null
  const reviewedMove=(game?.analysis?.moves||game?.analysis?.decisions)?.find(d=>d.ply===cursor)
  const moveHint=useMoveSuggestion(tab==='play'&&!browsingHistory?game:null)
  const analysisArrows:AnalysisArrow[]=[]
  if(tab==='play'&&game?.fen===boardFen)analysisArrows.push(...moveHint.arrows)
  if(tab==='train'&&puzzleComparison.visible){
    if(puzzleComparison.data?.played)analysisArrows.push({move:puzzleComparison.data.played,source:'played',rank:1})
    if(puzzleComparison.data?.maia)analysisArrows.push({move:puzzleComparison.data.maia,source:'maia',rank:1})
  }
  if(tab==='review'&&reviewedMove?.fen===boardFen){
    if(arrowSources.stockfish)(reviewedMove.stockfishCandidates||[reviewedMove.best]).slice(0,1).forEach((choice,index)=>{if(choice.pv[0])analysisArrows.push({move:choice.pv[0],source:'stockfish',rank:index+1})})
    if(arrowSources.maia)visiblePrediction?.moves.slice(0,1).forEach((choice,index)=>analysisArrows.push({move:choice.uci,source:'maia',rank:index+1}))
    if(arrowSources.played)analysisArrows.push({move:reviewedMove.played,source:'played',rank:1})
  }

  const series=useMemo(()=>tab==='review'&&game?evaluationSeries(game):null,[tab,game])
  const point=series?.points.find(p=>p.position===cursor)
  const {evalBar:showEval,maiaBar:showMaia}=useBoardSettings()
  const flipped=useBoardFlip(),boardOrientation=useBoardOrientation(orientation)
  useFlipShortcut()
  // Without a saved analysis (live game, unanalysed review) the bar asks Stockfish for a quick evaluation.
  const liveEval=usePositionEval(tab==='play'||tab==='review'?game:null,tab==='review'?cursor:playPly,showEval&&(tab==='play'||tab==='review'&&!point))
  const evalValue:BarValue|null|undefined=!showEval?undefined:tab==='review'?(point?{cp:point.cp,mate:point.mate,mateIn:point.terminal&&point.mate?0:null}:liveEval):tab==='play'&&game?liveEval:tab==='train'&&exercise&&attempt?.closed&&!puzzleComparison.visible?((attempt.success?attempt.actual:attempt.best)?whiteValue((attempt.success?attempt.actual:attempt.best)!,exercise.turn):null):undefined
  // Maia's value head: White's expected score for two humans of the review level, or of the game level while playing.
  const maiaPosition=showMaia&&game&&(tab==='play'||tab==='review')
  const maiaScore=useMaiaScore(maiaPosition?boardFen:null,tab==='review'?reviewElo:game?.elo??1500,!!maiaPosition)
  const maiaValue:MaiaScore|null|undefined=maiaPosition?maiaScore:undefined
  const moveBadge=tab==='review'&&reviewedMove?.fen===boardFen&&arrowSources.played?{square:reviewedMove.played.slice(2,4),kind:classifyMove(reviewedMove)}:undefined
  const shownGame=tab==='play'||tab==='review'?game:null
  const shownPly=tab==='review'?cursor:playPly
  const balance=material(boardFen,shownGame?.initialFen)
  const opponent:Color=orientation==='w'?'b':'w'
  const sideToMove=boardFen.split(' ')[1] as Color
  function thinkingTime(side:Color){
    if(!shownGame?.moveTimes)return null
    const first=shownGame.initialFen.split(' ')[1]
    let total=0,known=false
    shownGame.moveTimes.slice(0,shownPly).forEach((t,i)=>{if(((i%2===0)===(first==='w')?'w':'b')===side&&t!=null){total+=t;known=true}})
    return known?total:null
  }
  const opponentName=tab==='train'?'Posizione di allenamento':shownGame?.source==='pgn'?(opponent==='w'?'Bianco':'Nero'):shownGame?.source==='stockfish'?'Stockfish':'Maia'

  useEffect(()=>{
    if(tab!=='review'||!game)return
    const last=game.version
    const key=(event:KeyboardEvent)=>{
      if(event.defaultPrevented||event.altKey||event.ctrlKey||event.metaKey)return
      if((event.target as HTMLElement).closest?.('input,select,textarea,[role=tablist],[contenteditable=true]'))return
      const step=event.key==='ArrowLeft'?-1:event.key==='ArrowRight'?1:0
      if(!step)return
      event.preventDefault();setCursor(c=>Math.max(0,Math.min(last,c+step)))
    }
    window.addEventListener('keydown',key)
    return()=>window.removeEventListener('keydown',key)
  },[tab,game?.id,game?.version])

  useEffect(()=>{if(game){setReviewElo(game.elo);setReviewTab(cursor<game.version?'moves':'quality')}},[game?.id])

  const needsPrediction=arrowSources.maia||['moves','insights'].includes(reviewTab)
  useEffect(() => {
    setPrediction(null);setPredictionError('')
    // The red Maia arrow needs the prediction on every review tab, not only in Mosse.
    if (tab !== 'review' || !(needsPrediction) || !game || reviewBoard.isGameOver()) return
    let stale = false
    const controller = new AbortController()
    const timer = setTimeout(() => {
      maia.predict(reviewBoard.fen(),reviewElo,reviewElo,controller.signal).then(p => { if (!stale) {setPrediction(p);setPredictionKey(reviewBoard.fen()+':'+reviewElo)} }).catch(e=> { if (!stale) setPredictionError(e.message) })
    }, 150)
    return () => {stale = true; controller.abort(); clearTimeout(timer)}
  }, [tab, boardFen, reviewElo, retry, needsPrediction])

  async function startGame() {
    if ((game?.source === 'maia'||game?.source === 'stockfish') && !game.result && !window.confirm('Vuoi iniziare una nuova partita? La partita attuale resterà salvata e potrai riprenderla dall’archivio.')) return
    setBusy(true); setError(''); setNotice('')
    try { const next = await api<Game>('/games',{color:color==='random'?(Math.random()<.5?'w':'b'):color,elo}); keepGame(next,true); setTab('play'); setCursor(0); await refresh(); maia.load().catch(fail) }
    catch (e) {fail(e)} finally {setBusy(false)}
  }
  /** New game against Maia from a position of the shown game; the user plays the side at the bottom of the board. */
  async function playFrom(source:Game,ply:number){
    if ((game?.source === 'maia'||game?.source === 'stockfish') && !game.result && game.id !== source.id && !window.confirm('Vuoi iniziare una nuova partita? La partita attuale resterà salvata e potrai riprenderla dall’archivio.')) return
    const board=position(source,ply),number=board.moveNumber(),side=board.turn()==='w'?'.':'…'
    setBusy(true); setError(''); setNotice('')
    try {
      const next = await api<Game>('/games',{color:boardOrientation,elo:source.source==='maia'?source.elo:elo,fen:board.fen(),title:`Da ${source.title} · ${number}${side}`.slice(0,160)})
      keepGame(next,true); resetBoardFlip(); setPlayPosition(null); setTab('play'); setCursor(0); await refresh(); maia.load().catch(fail)
    } catch (e) {fail(e)} finally {setBusy(false)}
  }
  /** Defend a rejected training move against full-strength Stockfish, starting right after that move. */
  async function playMistake(kind:'puzzle'|'prevention'|'study',targetId:string,mistake:Refutation){
    if ((game?.source === 'maia'||game?.source === 'stockfish') && !game.result && !window.confirm('Vuoi iniziare una nuova partita? La partita attuale resterà salvata e potrai riprenderla dall’archivio.')) return
    const board=new Chess(mistake.fen),number=board.moveNumber(),side=board.turn()==='w'?'.':'…'
    setBusy(true); setError(''); setNotice('')
    try {
      const next = await api<Game>('/games',{color:board.turn(),elo,fen:mistake.fen,opponent:'stockfish',moves:[mistake.move],title:`Confutazione di ${number}${side} ${mistake.san}`})
      keepGame(next,true); setRefutationOrigin({gameId:next.id,kind,targetId,san:mistake.san}); resetBoardFlip(); setPlayPosition(null); setTab('play'); setCursor(0); await refresh()
    } catch (e) {fail(e)} finally {setBusy(false)}
  }
  async function submitMove(move: string) {
    if (!canMove) return
    if(tab==='train'&&exercise&&session){
      const ticket=puzzleMotion.start(move)
      if(ticket===null)return
      setBusy(true);setError('');setAttempt(null)
      try{
        const result=await api<Attempt>(`/exercises/${exercise.id}/attempts`,{move,session_id:session.id,version:session.version})
        if(!puzzleMotion.current(ticket))return
        setAttempt(result);setSession({...session,version:result.version})
        if(result.closed)setCompletedPuzzles(current=>current.includes(exercise.id)?current:[...current,exercise.id])
        await puzzleMotion.finish(ticket,result.closed)
        if(puzzleMotion.current(ticket))await refresh()
      }catch(e){if(puzzleMotion.current(ticket)){fail(e);await puzzleMotion.finish(ticket,false)}}
      finally{if(puzzleMotion.current(ticket))setBusy(false)}
      return
    }
    setBusy(true); setError('')
    try {
      if (game) { const next = await api<Game>(`/games/${game.id}/moves`,{move,version:game.version,revision:game.revision,actor:'human',elapsed_seconds:moveTime.elapsed(game)}); keepGame(next,true) }
    } catch (e) {fail(e)} finally {setBusy(false)}
  }
  async function undo() {
    if (!game?.canUndo || busy || jobId || browsingHistory) return
    botController.current?.abort()
    setBusy(true); setBotThinking(false); setError(''); setNotice('')
    try {
      const next = await api<Game>(`/games/${game.id}/undo`, {version:game.version,revision:game.revision})
      keepGame(next,true); setPlayPosition(null); setCursor(next.version); setNotice('Ultima mossa annullata. Tocca a te.'); await refresh()
    } catch (e) {
      fail(e)
      try { const latest = await api<Game>('/games/'+game.id); keepGame(latest); setCursor(latest.version) } catch (e) { fail(e) }
    } finally { setBusy(false) }
  }
  async function resign() {
    if(!game||(game.source!=='maia'&&game.source!=='stockfish')||game.result||busy)return
    if(!window.confirm('Vuoi abbandonare la partita? Verrà registrata una sconfitta e, se hai giocato delle mosse, partirà l’analisi automatica.'))return
    botController.current?.abort()
    setBusy(true);setBotThinking(false);setError('')
    try{
      const next=await api<Game>(`/games/${game.id}/resign`,{version:game.version,revision:game.revision})
      keepGame(next);setPlayPosition(null);setCursor(next.version)
      setNotice(next.moves.length?'Hai abbandonato la partita. Avvio dell’analisi automatica.':'Hai abbandonato la partita. Non ci sono mosse da analizzare.')
      await refresh()
    }catch(e){
      fail(e)
      try{keepGame(await api<Game>('/games/'+game.id))}catch(e){fail(e)}
    }finally{setBusy(false)}
  }
  async function analyze() {
    if (!game) return
    setReviewTab(current=>current==='evaluation'?'evaluation':'moves')
    setBusy(true); setError(''); setTab('review'); setCursor(game.version)
    try { const result = await api<{jobId:string}>(`/games/${game.id}/analysis`,{}); setProgress(0); setJobId(result.jobId) }
    catch (e) {fail(e)} finally {setBusy(false)}
  }
  async function openGame(id: string, ply?:number) {
    setBusy(true); setError('')
    try {const next = await api<Game>('/games/'+id); keepGame(next); setCursor(ply??next.version); if(ply!==undefined)setReviewTab('moves'); setTab('review')}
    catch(e){fail(e)} finally {setBusy(false)}
  }
  async function openTraining(kind:'puzzle'|'prevention',id:string){
    if(kind==='prevention'){setRequestedPrevention(id);setTab('prevention');return}
    try{const ex=await api<Exercise>('/exercises/'+encodeURIComponent(id));await pickExercise(ex)}catch(e){fail(e)}
  }
  function recordPuzzleResult(result:Attempt,move?:string){
    setAttempt(result)
    puzzleMotion.show(result.closed?(result.success?move:result.best?.pv[0])??null:null)
    if(result.closed&&exercise)setCompletedPuzzles(current=>current.includes(exercise.id)?current:[...current,exercise.id])
  }
  async function pickExercise(ex: Exercise) {
    setExercise(ex); setAttempt(null); puzzleMotion.show(null); setSession(null); setHint(''); setNotice(''); setTab('train'); setError(''); setBusy(true)
    try {setSession(await api<PuzzleSession>(`/exercises/${ex.id}/sessions`,{}))}catch(e){fail(e)}finally{setBusy(false)}
  }
  async function puzzleHelp(reveal=false) {
    if(!exercise||!session)return
    setBusy(true)
    try {
      if(reveal){const result=await api<Attempt>(`/exercises/${exercise.id}/reveal`,{session_id:session.id});recordPuzzleResult(result);await refresh()}
      else{const result=await api<{hint:string}>(`/exercises/${exercise.id}/hint`,{session_id:session.id});setHint(result.hint)}
    }catch(e){fail(e)}finally{setBusy(false)}
  }
  function navigate(next: Tab) {if(busy)return;setMoreOpen(false);setTab(next); setError(''); setNotice(''); if(next==='review'&&game)setCursor(game.version); if(next==='train'&&!exercise&&dueExercises[0])pickExercise(dueExercises[0]); refresh().catch(fail)}

  const playFromButton=(source:Game,ply:number)=>{
    const ended=position(source,ply).isGameOver()
    return <button className="play-from" disabled={busy||!!jobId||botThinking||ended} title={ended?'La partita è già conclusa in questa posizione':'Nuova partita contro Maia da questa posizione: giochi il colore in basso (usa ⇅ per cambiarlo)'}
      onClick={()=>void playFrom(source,ply)}>Gioca da qui col {boardOrientation==='w'?'Bianco':'Nero'}</button>
  }
  const opponentBar=<PlayerBar key="opponent" lower={flipped} avatar={tab==='train'?'◎':opponent==='w'?'♔':'♚'} name={opponentName} rating={tab!=='train'&&shownGame?.source!=='pgn'&&shownGame?.source!=='stockfish'?String(game?.elo||elo):undefined}
    detail={tab==='train'?exercise?.theme||'Scegli un esercizio':shownGame?.source==='pgn'?'Partita importata':shownGame?.source==='stockfish'?'Piena forza · cerca la confutazione':`Livello ${game?.elo||elo} · gioco umano`}
    captured={tab==='train'?[]:balance.captured(opponent)} advantage={balance.advantage(opponent)} time={thinkingTime(opponent)} active={!!shownGame&&!shownGame.result&&sideToMove===opponent}
    aside={tab==='play'&&botThinking&&<span className="thinking" role="status">{opponentName} sta pensando…</span>}/>
  const playerBar=<PlayerBar key="player" lower={!flipped} avatar={orientation==='w'?'♙':'♟'} name={tab==='train'?(attempt?.closed?(attempt.success?'Puzzle risolto':'Soluzione del puzzle'):exercise?.turn==='b'?'Muove il Nero':'Muove il Bianco'):'Tu'}
    detail={tab==='play'?(browsingHistory?`Stai rivedendo la posizione dopo ${playPly} semimosse`:game?.result?`Partita conclusa · ${game.result}${game.termination==='resign'?' · per abbandono':''}`:canMove?'Tocca a te · trascina un pezzo o usa due clic':game?'Attendi la risposta':'Pronto per iniziare'):tab==='review'?`Posizione dopo ${cursor} semimosse`:attempt?.closed?'Esercizio concluso':'Cerca una buona mossa'}
    captured={tab==='train'?[]:balance.captured(orientation)} advantage={balance.advantage(orientation)} time={thinkingTime(orientation)} active={!!shownGame&&!shownGame.result&&sideToMove===orientation}
    aside={<span className="mode-label">{tab==='play'?'PARTITA LIBERA':tab==='review'?'ANALISI':'ESERCIZIO'}</span>}/>
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={e=>{e.preventDefault();navigate('play')}}><span className="brand-mark">♞</span><span>Sparring<span className="brand-light">Mate</span><small>IL TUO SPAZIO DI ALLENAMENTO</small></span></a>
      <nav aria-label="Navigazione principale" className={moreOpen?'more-open':undefined}>{navigation.map(([key,label,primary]) => <button key={key} disabled={busy} data-primary={primary||undefined} className={tab===key?'nav-item active':'nav-item'} onClick={()=>navigate(key)} aria-current={tab===key?'page':undefined}><Icon name={key}/><span className="nav-label">{label}</span>{key==='train'&&!!profile?.due&&<b className="nav-badge">{profile.due}</b>}</button>)}
        <button className={`nav-item nav-more ${!navigation.find(([key])=>key===tab)?.[2]?'active':''}`} aria-expanded={moreOpen} onClick={()=>setMoreOpen(v=>!v)}><Icon name="more"/><span className="nav-label">Altro</span></button></nav>
      <ol className="sidebar-note" aria-label="Come si usa"><li><b>1</b>Gioca contro Maia</li><li><b>2</b>Rivedi gli errori</li><li><b>3</b>Ripassa le posizioni</li></ol>
      <div className="local-status"><span className="status-dot"/> Spazio personale locale<small>Partite archiviate su questo computer.</small></div>
    </aside>
    <main className={'page-'+tab}>
      <header className="topbar"><div className="topbar-title"><span className="crumb">SparringMate <span aria-hidden="true">/</span></span><h1>{titles[tab]}</h1></div><div className="topbar-actions"><button className="quiet" onClick={()=>setShowImport(!showImport)}>↑ <span className="label-long">Importa </span>PGN</button>{onLogout&&<button className="quiet" aria-label="Esci" title="Esci" onClick={onLogout}>⏻<span className="label-long"> Esci</span></button>}{['play','review','train','drill','prevention','study','problems'].includes(tab)&&<FlipBoardButton/>}<BoardSettingsMenu/><span className="pill engine-pill">Maia + Stockfish <span className="status-dot"/></span></div></header>
      {!['play','review','train','prevention','problems'].includes(tab)&&<p className="page-subtitle">{subtitles[tab]}</p>}
      {error&&<div className="alert" role="alert">{error}<button onClick={()=>{setError('');setRetry(x=>x+1)}}>Riprova</button></div>}
      {notice&&<div className="notice" role="status">{notice}</div>}
      {showImport&&<ImportGames onImported={()=>void refresh().catch(fail)} onOpen={id=>void openGame(id)}/>}


      {tab==='schedule'?<TrainingPlan focusJudgment={focusJudgment} onFocused={()=>setFocusJudgment(false)} onOpen={(kind,id)=>void openTraining(kind,id)} onImport={()=>setShowImport(true)} judgment={<PositionJudgment onReview={(id,ply)=>void openGame(id,ply)}/>}/>:tab==='problems'?<Problems/>:tab==='prevention'?<BlunderPrevention startPositionId={requestedPrevention} onStarted={()=>setRequestedPrevention(null)} onArchive={()=>navigate('archive')} onReview={(id,ply)=>void openGame(id,ply)} onPlayMistake={(id,m)=>void playMistake('prevention',id,m)}/>:tab==='drill'?<Drills startTemplateId={requestedDrill} onStarted={()=>setRequestedDrill(null)} onReview={g=>{keepGame(g);setCursor(g.version);setTab('review');refresh().catch(fail)}}/>:tab==='progress'?<div className="progress-layout"><LearningProgress onPractice={()=>{setFocusJudgment(true);navigate('schedule')}}/>
        <section className="panel"><span className="eyebrow">SESSIONE CONSIGLIATA</span><h2>Piano di 25 minuti</h2>{profile?.plan.map((item,i)=><div className="plan-row" key={item.title}><span className="step-number">0{i+1}</span><div><h3>{item.title}</h3><p>{item.description}</p></div><span className="duration">{item.minutes} min</span></div>)}<button className="primary" onClick={()=>navigate(exercises.length?'train':'play')}>Inizia la sessione →</button></section>
        <section className="panel"><span className="eyebrow">DATI RACCOLTI</span><h2>{profile?.confidence||'Nessun dato'}</h2><div className="stat-tiles"><div><strong>{profile?.games||0}</strong><span>partite salvate</span></div><div><strong>{profile?.attempts||0}</strong><span>tentativi</span></div><div><strong>{profile?.unaidedSuccesses||0}</strong><span>primi tentativi riusciti</span></div></div>{profile?.themes.length?<><h3>Posizioni per tema</h3><BarList items={profile.themes.map(t=>({key:t.theme,label:t.theme,value:t.examples}))}/></>:<p className="empty-text">Analizza una partita per iniziare a raccogliere le tue posizioni di allenamento.</p>}<InfoNote>I successi contano solo il primo tentativo senza aiuti, su esercizi nuovi o in scadenza. Le ripetizioni immediate restano pratica. Non sono ancora una misura di padronanza: servono anche verifiche su posizioni nuove.</InfoNote></section>
        <section className="panel"><h2>Tattica e posizione nelle tue decisioni</h2><ThinkingGuide/>{profile?.domains?.length?<BarList items={profile.domains.map(d=>({key:d.kind,label:d.label,value:d.examples}))}/>:null}<InfoNote summary="Come leggere i conteggi">Conteggi di decisioni con peggioramento: le posizioni ripetute sono contate una volta. Indicano cosa rivedere, non una diagnosi di carenze. La categoria posizionale segnala indizi, non una causa dimostrata.</InfoNote></section>
        <ExamProgress/>
      </div>:tab==='study'?<Study games={saved} section={studySection} onSection={showStudySection} gameId={studyGame} onGame={setStudyGame}
        actions={{onPuzzle:id=>void openTraining('puzzle',id),onPrevention:id=>void openTraining('prevention',id),onDrill:id=>{setRequestedDrill(id);setTab('drill')},onPlayMistake:m=>void playMistake('study',studyGame??'',m),onReview:(id,ply)=>void openGame(id,ply)}}/>
      :tab==='archive'?null:<div className={'training-layout layout-'+tab}>
        <section className="board-column">
          {flipped?playerBar:opponentBar}
          {/* Stockfish bar on the left of the board, Maia bar on the right. */}
          <div className={`board-stage ${evalValue!==undefined?'with-eval':''} ${maiaValue!==undefined?'with-maia':''}`}>
            {evalValue!==undefined&&<div className="eval-bars"><EvalBar value={evalValue} orientation={boardOrientation}/></div>}
            <Board badge={moveBadge} analysisArrows={analysisArrows} reverseMove={tab==='train'&&puzzleMotion.reverse} animateMove={tab==='train'||tab==='play'&&!browsingHistory&&!!game&&game.turn===game.playerColor} fen={boardFen} orientation={boardOrientation} interactive={canMove} legalMoves={legal} onMove={submitMove} lastMove={tab==='train'?(puzzleComparison.visible?undefined:puzzleMotion.lastMove):tab==='play'?game?.moves[playPly-1]:tab==='review'&&game&&cursor>0?game.moves[cursor-1]:undefined}/>
            {maiaValue!==undefined&&<div className="eval-bars"><MaiaBar score={maiaValue} orientation={boardOrientation}/></div>}
          </div>
          {flipped?opponentBar:playerBar}
          {tab==='play'&&game&&<div className="board-actions"><button title={`Ritorna alla tua ultima scelta e annulla anche la risposta di ${game.source==='stockfish'?'Stockfish':'Maia'}.`} disabled={!game.canUndo||busy||!!jobId||browsingHistory} onClick={undo}><span aria-hidden="true">↶</span> Annulla ultima mossa</button>{!game.result&&<button disabled={!canMove||!!moveHint.suggestion?.loading} onClick={()=>void moveHint.request()} title="Prima scelta di Stockfish (blu) e di Maia (rosso) nella posizione attuale"><span aria-hidden="true">💡</span> Suggerisci mossa</button>}{(game.source==='maia'||game.source==='stockfish')&&!game.result&&<button className="danger" disabled={busy||!!jobId} onClick={resign}><span aria-hidden="true">⚑</span> Abbandona partita</button>}</div>}
          {tab==='play'&&game&&<SuggestionBox suggestion={moveHint.suggestion} elo={game.elo}/>}
          {browsingHistory&&<div className="play-history-notice"><span>Posizione precedente · {playPly} / {game!.moves.length}</span><span className="play-history-actions">{playFromButton(game!,playPly)}<button className="primary" onClick={()=>setPlayPosition(null)}>Torna alla posizione corrente</button></span></div>}
          {tab==='review'&&game&&<div className="review-controls board-toolbar"><button aria-label="Posizione iniziale" onClick={()=>setCursor(0)} disabled={cursor===0}>⏮</button><button aria-label="Mossa precedente" onClick={()=>setCursor(c=>Math.max(0,c-1))} disabled={cursor===0}>◀</button><span>{cursor} / {game.version}</span><button aria-label="Mossa successiva" onClick={()=>setCursor(c=>Math.min(game.version,c+1))} disabled={cursor===game.version}>▶</button><button aria-label="Ultima posizione" onClick={()=>setCursor(game.version)} disabled={cursor===game.version}>⏭</button>{playFromButton(game,cursor)}</div>}
          {tab==='review'&&game&&<div className="analysis-arrow-controls" role="group" aria-label="Frecce di analisi">{([['stockfish','Stockfish · blu'],['maia','Maia · rosso'],['played','Giocata · bianco']] as const).map(([source,label])=><label key={source}><input type="checkbox" checked={arrowSources[source]} onChange={e=>setArrowSources(current=>({...current,[source]:e.target.checked}))}/><span className={'arrow-swatch source-'+source}/>{label}</label>)}</div>}
          {tab==='train'&&attempt?.success&&<div className="panel" aria-label="Confronto del puzzle">
            <p>{puzzleComparison.visible?'Confronto dalla posizione iniziale del puzzle.':'La scacchiera mostra la tua soluzione.'}</p>
            <div className="analysis-arrow-controls"><span><i className="arrow-swatch source-played"/> Giocata in partita · bianco</span><span><i className="arrow-swatch source-maia"/> Maia {puzzleComparison.data?.elo??''} · rosso</span></div>
            {puzzleComparison.data?.loading&&<p role="status">Calcolo della prima scelta di Maia…</p>}
            {puzzleComparison.data?.error&&<p role="status">{puzzleComparison.data.error} <button onClick={puzzleComparison.retry}>Riprova confronto</button></p>}
            {puzzleComparison.data?.played&&<button onClick={puzzleComparison.toggle}>{puzzleComparison.visible?'Mostra la tua soluzione':'Mostra confronto con frecce'}</button>}
            <p className="footnote">La freccia rossa indica la mossa più probabile al livello della partita, non necessariamente la migliore.</p>
          </div>}
          {((tab==='play'||tab==='review')&&game||tab==='train'&&exercise)&&<LichessAnalysis key={tab==='train'?exercise!.id:game!.id+':'+tab} fen={boardFen} orientation={orientation} game={tab==='train'?undefined:game} ply={tab==='review'?cursor:playPly}/>}
        </section>
        <aside className="coach-column">
          {tab==='train'&&exercise&&<PuzzleFeedback canRestart={dueExercises.length>0} comparing={puzzleComparison.visible} motionMessage={puzzleMotion.message} attempt={attempt} busy={busy} ready={!!session} hasNext={!!nextPuzzle} onNext={()=>{if(nextPuzzle)void pickExercise(nextPuzzle)}} onRestart={()=>{setCompletedPuzzles([]);if(dueExercises[0])void pickExercise(dueExercises[0])}}/>}
          {tab==='play'&&jobId&&<section className="panel" role="status"><p>Analisi automatica della partita… {progress}%</p><progress value={progress} max={100}/></section>}
          {tab==='review'&&<>
            <div className="review-toolbar"><div className="row"><button className="primary" onClick={analyze} disabled={!game?.version||busy||!!jobId}>{game?.analysis?'Ricalcola analisi':'Analizza partita'}</button>{(game?.source==='maia'||game?.source==='stockfish')&&!game.result&&<button disabled={!!jobId} onClick={()=>setTab('play')}>Continua partita</button>}</div>{jobId&&<div role="status"><p>Stockfish analizza la partita… {progress}%</p><progress value={progress} max={100}/></div>}</div>
            {game&&<ReviewSummary game={game} cursor={cursor} onPosition={setCursor}/>}
            {game&&<PgnExport game={game}/>}
            <PanelTabs id="review" label="Pannelli della revisione" value={reviewTab} onChange={setReviewTab} items={[{id:'quality',label:'Decisioni'},{id:'moves',label:'Mosse'},{id:'evaluation',label:'Andamento'},{id:'final',label:'Commento finale'},{id:'tutor',label:'Tutor'},{id:'insights',label:'Approfondimenti'}]}/>
          </>}
          {tab==='review'&&<div role="tabpanel" id="review-panel-final" aria-labelledby="review-tab-final" hidden={reviewTab!=='final'}>{game?<FinalReview game={game} disabled={!!jobId||busy} onPosition={ply=>{setCursor(ply);setReviewTab('moves')}}/>:<section className="panel"><p>Seleziona una partita per richiedere il commento finale.</p></section>}</div>}
          {tab==='review'&&<div role="tabpanel" id="review-panel-evaluation" aria-labelledby="review-tab-evaluation" hidden={reviewTab!=='evaluation'}>{game?<EvaluationChart game={game} cursor={cursor} onPosition={setCursor} analyzing={!!jobId} onAnalyze={analyze}/>:<section className="panel"><p>Seleziona una partita per visualizzare il grafico.</p></section>}</div>}
          {tab==='review'&&<div role="tabpanel" id="review-panel-moves" aria-labelledby="review-tab-moves" hidden={reviewTab!=='moves'}>{game?<MoveReview game={game} cursor={cursor} onPosition={setCursor} level={reviewElo} onLevel={setReviewElo} prediction={visiblePrediction} error={predictionError} onRetry={()=>setRetry(n=>n+1)} analyzing={busy||!!jobId} onAnalyze={analyze}/>:<section className="panel"><p>Gioca una partita o importa un PGN per iniziare.</p></section>}</div>}
          {game&&(tab==='review'||(tab==='play'&&!!game.result))&&<div role={tab==='review'?'tabpanel':undefined} id="review-panel-quality" aria-labelledby={tab==='review'?'review-tab-quality':undefined} hidden={tab==='review'&&reviewTab!=='quality'}><DecisionQuality game={game} disabled={!!jobId||busy} onAnalyze={analyze} onPosition={ply=>{setTab('review');setCursor(ply);setReviewTab('moves')}}/><button className="full" onClick={()=>{setTab('review');setReviewTab('final')}}>Commento finale · andamento e punti da approfondire →</button>{game.analysis&&game.source!=='stockfish'&&<button className="full" onClick={()=>{setStudyGame(game.id);showStudySection('pack');navigate('study')}}>Studia questa partita · quiz, flashcard, tutor →</button>}<details className="panel maia-secondary"><summary>Somiglianza con Maia · facoltativa</summary><RatingPanel key={'rating:'+game.id+':'+game.version+':'+game.revision} game={game} disabled={!!jobId||busy} onRated={rating=>setGame(current=>current?.id===game.id&&current.version===game.version&&current.revision===game.revision?{...current,rating}:current)}/></details></div>}
          {tab==='review'&&!game&&<div role="tabpanel" id="review-panel-quality" aria-labelledby="review-tab-quality" hidden={reviewTab!=='quality'} className="panel">Seleziona una partita per rivedere la qualità delle decisioni.</div>}
          {tab==='play'&&<>
            {game?.source==='stockfish'&&<section className="panel refutation-panel" aria-label="Confutazione"><span className="eyebrow">IMPARA DAL TENTATIVO</span><h3>Difendi {refutationOrigin?.gameId===game.id?refutationOrigin.san:'la tua mossa'} contro Stockfish</h3><p className="muted">La partita parte dopo la mossa che l’esercizio ha rifiutato. Stockfish gioca a piena forza: la sua prima risposta è di solito ciò che non avevi visto. Annulla e prova altre difese per capire se il problema si può riparare.</p><small className="footnote">Partita di studio: non crea puzzle e non entra nei Progressi.</small>{refutationOrigin?.gameId===game.id&&<button className="full" disabled={busy} onClick={()=>{const origin=refutationOrigin;if(origin.kind==='study')navigate('study');else if(origin.kind==='puzzle'&&exercise?.id===origin.targetId)setTab('train');else void openTraining(origin.kind,origin.targetId)}}>← Torna {refutationOrigin.kind==='puzzle'?'al puzzle':refutationOrigin.kind==='study'?'allo studio':'all’esercizio'}</button>}</section>}
            {game&&<MoveHistory key={game.id} game={game} ply={playPly} onPosition={showPlayPosition} onReview={analyze} reviewDisabled={!game.version||busy||botThinking||!!jobId}/>}
            <section className="panel play-setup"><span className="eyebrow">IL TUO SPARRING PARTNER</span><h2>{game?'Nuova partita':'Gioca contro Maia'}</h2><p className="muted">Mosse e imperfezioni ispirate al gioco umano.</p>
              <div className="field-label">Livello di riferimento <strong>{elo}</strong></div>
              <div className="chip-row" role="group" aria-label="Livelli consigliati">{levels.map(level=><button key={level} className="chip" aria-pressed={elo===level} onClick={()=>setElo(level)}>{level}</button>)}</div>
              <input className="level-range" aria-label="Livello Maia" type="range" min="600" max="2600" step="100" value={elo} onChange={e=>setElo(Number(e.target.value))}/><div className="range-labels"><span>600</span><span>2600</span></div>
              <div className="field-label">Il tuo colore</div>
              <div className="segmented color-choice" role="group" aria-label="Il tuo colore">{([['w','♔','Bianco'],['b','♚','Nero'],['random','⚄','Casuale']] as const).map(([value,icon,label])=><button key={value} aria-pressed={color===value} onClick={()=>setColor(value)}><span aria-hidden="true">{icon}</span>{label}</button>)}</div>
              <button className="primary full big" onClick={startGame} disabled={busy||!!jobId||botThinking}>{game?'Nuova partita':'Inizia partita'} →</button>
              <small className="footnote">Il livello guida il modello; non equivale a un rating agonistico certificato.</small>
              {!game&&<p className="tutor-tip"><strong>Il tutor osserva.</strong> Alla fine rivedremo le decisioni più interessanti e creeremo esercizi dalle tue posizioni.</p>}
              <div className="engine-status"><span className={maiaStatus==='Maia pronto'?'status-dot':'status-dot waiting'}/>{maiaStatus}<small>{stockfish}</small></div>
            </section>
            {game&&<PgnExport game={game}/>}
          </>}
          {tab==='review'&&<><div role="tabpanel" id="review-panel-tutor" aria-labelledby="review-tab-tutor" hidden={reviewTab!=='tutor'}>{game?<TutorPanel key={game.id+':'+game.version+':'+game.analysis?.createdAt} game={game} disabled={!!jobId||!game.analysis} onPosition={setCursor} onPuzzle={id=>{const ex=exercises.find(e=>e.id===id);if(ex)pickExercise(ex);else fail(new Error('Esercizio non disponibile: ricarica la pagina.'))}} onDrill={id=>{setRequestedDrill(id);setTab('drill')}}/>:<section className="panel"><p>Seleziona una partita per consultare il tutor.</p></section>}</div><div role="tabpanel" id="review-panel-insights" aria-labelledby="review-tab-insights" hidden={reviewTab!=='insights'} className="insights-grid">
            <section className="panel"><span className="eyebrow">MOMENTI DA RIVEDERE</span><h2>Le mosse più costose</h2>{jobId?<div role="status"><p>Stockfish analizza la partita… {progress}%</p><progress value={progress} max={100}/></div>:!game?<p className="empty-text">Gioca una partita o importa un PGN per iniziare.</p>:<>{!game.analysis?<p className="muted">Avvia la revisione per individuare le decisioni da allenare.</p>:game.analysis.critical.length?game.analysis.critical.map(d=><button className={`moment ${cursor===d.ply?'chosen':''}`} key={d.ply} onClick={()=>setCursor(d.ply)}><span>{Math.floor(d.ply/2)+1}{d.ply%2?'…':'.'} {d.playedSan}</span><span>{d.label}</span><small>{d.insight?.label||d.theme}</small></button>):<p className="muted">Nessun errore rilevante individuato nel budget di analisi. Non significa gioco perfetto.</p>}</>}{decision&&<div className="decision"><h3>Hai giocato {decision.playedSan}</h3><p>Alternativa: <strong>{decision.best.san[0]||'—'}</strong></p><p className="variation">{decision.best.san.join(' ')}</p><small>Valutazione dal lato che muove: {score(decision.actual)} → {score(decision.best)}. Profondità {decision.best.depth}.</small><ChessInsights insight={decision.insight} compact/></div>}</section>
            <section className="panel"><span className="eyebrow">MAIA</span><h3>Mosse più probabili a questo livello</h3>{visiblePrediction?.moves.slice(0,3).map(m=><div className="policy" key={m.uci}><strong>{m.san}</strong><div><span style={{width:`${m.probability*100}%`}}/></div><span>{Math.round(m.probability*100)}%</span></div>)}{!visiblePrediction&&<p className="muted">{game?'Caricamento delle previsioni…':'Nessuna posizione selezionata.'}</p>}<small className="footnote">Probabilità del modello, non giudizi sulla qualità delle mosse.</small></section>
            </div>
          </>}
          {tab==='train'&&<section className="panel puzzle-panel"><span className="eyebrow">DALLE TUE PARTITE</span><h2>{exercise?exercise.theme:'Il tuo primo esercizio'}</h2>{!exercise?<p className="empty-text">Gli esercizi nasceranno dalla revisione delle tue partite. Gioca o importa un PGN, poi avvia l'analisi.</p>:<><p className="muted">{attempt?.closed?'Confronta la posizione sulla scacchiera con la variante di riferimento.':'Muovi sulla scacchiera. Sono accettate anche alternative che mantengono la qualità della posizione.'}</p>{!attempt?.closed&&session&&<div className="row"><button disabled={busy} onClick={()=>puzzleHelp()}><span aria-hidden="true">💡</span> Chiedi un indizio</button><button disabled={busy||diagnosing===session.id} onClick={()=>setDiagnosing(session.id)}>Mostra soluzione</button></div>}{hint&&<p className="hint">{hint}</p>}{session&&diagnosing===session.id&&<FailureDiagnosis kind="puzzle" targetId={exercise.id} sessionId={session.id} onReveal={()=>void puzzleHelp(true)} onCancel={()=>setDiagnosing(null)}/>}{attempt?.closed&&<div className="puzzle-solution"><h3>Variante di riferimento</h3><p className="variation">{attempt.best?.san.join(' ')}</p><small>{attempt.assisted?'Esercizio con aiuto.':'Esercizio senza aiuti.'} Ripasso: {new Date(attempt.dueAt).toLocaleDateString('it-IT')}.</small></div>}</>}</section>}
          {tab==='train'&&exercise&&<ExerciseSource title={exercise.gameTitle} createdAt={exercise.gameCreatedAt} fen={exercise.fen} disabled={busy} onReview={()=>void openGame(exercise.gameId,exercise.ply)}/>}
          {tab==='train'&&dueExercises.length>0&&<section className="panel"><div className="section-head"><h3>Da ripassare</h3><span className="count-chip">{profile?.due??dueExercises.length}</span></div><div className="exercise-list">{dueExercises.map(ex=><button key={ex.id} className={exercise?.id===ex.id?'exercise-link chosen':'exercise-link'} disabled={busy} onClick={()=>pickExercise(ex)}><span>{ex.theme}</span><small>Mossa {Math.floor(ex.ply/2)+1} · {new Date(ex.dueAt).getTime()<=Date.now()?'da ripassare':'programmato'}</small></button>)}</div><InfoNote summary="Quando un puzzle esce dalla lista">Escono dalla lista solo i puzzle risolti al primo tentativo senza aiuti; torneranno alla scadenza del ripasso.</InfoNote></section>}
          {tab==='train'&&exercise&&<MistakeHistory key={exercise.id} kind="puzzle" targetId={exercise.id} revision={session?.version??0} onPlay={m=>void playMistake('puzzle',exercise.id,m)}/>}
          {tab==='train'&&<section className="panel"><ThinkingGuide/>{attempt?.closed&&<ChessInsights insight={attempt.insight} compact/>}</section>}
        </aside>
      </div>}
      {tab==='archive'&&<GameArchive games={saved} disabled={!!jobId||busy} onOpen={id=>void openGame(id)}/>}
      <footer>SparringMate · Prototipo locale <span>Maia per il gioco umano. Stockfish per la verifica.</span></footer>
    </main>
  </div>
}
