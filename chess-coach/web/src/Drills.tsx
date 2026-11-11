import { useEffect, useRef, useState } from 'react'
import Board from './Board'
import {useBoardOrientation} from './boardFlip'
import LichessAnalysis from './LichessAnalysis'
import PanelTabs from './PanelTabs'
import PgnExport from './PgnExport'
import {useMoveTime} from './useMoveTime'
import { api } from './api'
import {ThinkingGuide} from './ChessInsights'
import { paceServerReply } from './engine/play'
import type { Color, Game } from './types'
import MiniBoard from './MiniBoard'
import {useMoveSuggestion,SuggestionBox} from './MoveSuggestion'
import {OpeningFamilies,LineReview,type LineSession,type LineStart} from './OpeningLines'
import DrillReview from './DrillReview'
import OpeningStatus from './OpeningStatus'

interface Template { id:string; name:string; kind:string; theme:string; goal:string; reason:string; color:Color|null; fen?:string; source?:string }
export default function Drills({onReview,startTemplateId,onStarted,startLineId,onLineStarted}:{onReview:(game:Game)=>void;startTemplateId?:string|null;onStarted?:()=>void;startLineId?:string|null;onLineStarted?:()=>void}) {
  const [view,setView]=useState('catalog')
  const [catalog,setCatalog]=useState<Template[]>([])
  const [game,setGame]=useState<Game|null>(null)
  const boardOrientation=useBoardOrientation(game?.playerColor??'w')
  const [elo,setElo]=useState(1500)
  const [color,setColor]=useState<Color>('w')
  const [target,setTarget]=useState(10)
  const [reviewOpen,setReviewOpen]=useState(false)
  const [busy,setBusy]=useState(false)
  const [thinking,setThinking]=useState(false)
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const [line,setLine]=useState<LineSession|null>(null)
  const [lineStart,setLineStart]=useState<LineStart|null>(null)
  const botController=useRef<AbortController|null>(null)
  const hint=useMoveSuggestion(view==='session'?game:null)
  const moveTime=useMoveTime(game,view==='session'&&!!game&&!game.result&&!game.drill?.complete)
  function fail(e:unknown){setError(e instanceof Error?e.message:'Operazione non riuscita')}
  function keep(g:Game,newTurn=false){if(newTurn)moveTime.begin(g);setGame(current=>{if(current?.id!==g.id)setReviewOpen(false);return g});localStorage.setItem('chess-coach-drill',g.id)}
  useEffect(()=>{
    api<Template[]>('/drills').then(setCatalog).catch(fail)
    if(startLineId){const [family,slug,color]=startLineId.split(':');startLine({target:`${family}:${slug}`,color:color==='b'?'b':'w'}).then(()=>onLineStarted?.());return}
    if(startTemplateId){start(startTemplateId).then(()=>onStarted?.());return}
    const lineId=localStorage.getItem('chess-coach-line')
    if(lineId)api<LineSession>('/opening-lines/sessions/'+lineId).then(s=>{if(s.status==='active')setLine(s)}).catch(()=>localStorage.removeItem('chess-coach-line'))
    const id=localStorage.getItem('chess-coach-drill')
    // The page opens on the catalogue; a session in progress is resumed from its banner.
    if(id)api<Game>('/games/'+id).then(g=>keep(g)).catch(()=>localStorage.removeItem('chess-coach-drill'))
  },[])
  useEffect(()=>{
    if(!game||busy||game.drill?.complete||game.result||game.turn===game.playerColor)return
    let cancelled=false
    const controller=new AbortController()
    botController.current=controller
    const snapshot=game
    setThinking(true)
    ;(async()=>{
      const next=await paceServerReply(()=>api<Game>(`/games/${snapshot.id}/maia-move`,{version:snapshot.version,revision:snapshot.revision,elapsed_seconds:moveTime.elapsed(snapshot)}),controller.signal)
      if(!cancelled&&!controller.signal.aborted)keep(next,true)
    })().catch(e=>{if(!cancelled&&!controller.signal.aborted)fail(e)}).finally(()=>{if(!cancelled)setThinking(false)})
    return()=>{cancelled=true;controller.abort();setThinking(false)}
  },[game?.id,game?.version,game?.revision,retry,busy])
  async function undo(){
    if(!game?.canUndo||busy)return
    botController.current?.abort()
    setBusy(true);setThinking(false);setError('')
    try{keep(await api<Game>(`/games/${game.id}/undo`,{version:game.version,revision:game.revision}),true)}
    catch(e){fail(e);try{keep(await api<Game>('/games/'+game.id))}catch(e){fail(e)}}
    finally{setBusy(false)}
  }
  async function start(id:string,settings?:{color:Color;elo:number;target:number}){
    setBusy(true);setError('')
    try{keep(await api<Game>(`/drills/${encodeURIComponent(id)}/start`,settings??{color,elo,target}),true);setView('session')}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  async function startLine(body:LineStart){
    setBusy(true);setError('')
    try{const s=await api<LineSession>('/opening-lines/sessions',body);setLine(s);setLineStart(body);localStorage.setItem('chess-coach-line',s.id);setView('lines')}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  async function setDrillTarget(next:number,review:boolean){
    if(!game||busy)return
    botController.current?.abort()
    setBusy(true);setError('')
    try{keep(await api<Game>(`/games/${game.id}/drill/target`,{version:game.version,revision:game.revision,target:next}));if(review)setReviewOpen(true)}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  async function move(move:string){
    if(!game||busy)return
    setBusy(true);setError('')
    try{keep(await api<Game>(`/games/${game.id}/moves`,{move,version:game.version,revision:game.revision,actor:'human',elapsed_seconds:moveTime.elapsed(game)}),true)}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  return <div>
    {error&&<div className="alert" role="alert">{error}<button onClick={()=>{setError('');setRetry(n=>n+1)}}>Riprova</button></div>}
    <PanelTabs id="drills" label="Pannelli dei drill" value={view} onChange={setView} items={[{id:'catalog',label:'Scegli un drill'},{id:'session',label:'Sessione'},{id:'lines',label:'Ripasso linea'}]}/>
    <div role="tabpanel" id="drills-panel-session" aria-labelledby="drills-tab-session" hidden={view!=='session'}>
    {!game&&<section className="panel"><p>Scegli un drill per iniziare una sessione.</p><button onClick={()=>setView('catalog')}>Scegli un drill</button></section>}
    {game?.drill&&reviewOpen&&game.drill.complete&&<DrillReview key={game.id} game={game} onGame={g=>setGame(g)} onReview={()=>onReview(game)} onNext={()=>{setReviewOpen(false);setView('catalog')}}
      onAgain={()=>{const again=game.drill?.templateId;if(again)void start(again,{color:game.playerColor,elo:game.elo,target})}}/>}
    {game?.drill&&!(reviewOpen&&game.drill.complete)&&<div className="training-layout">
      <section className="board-column"><div className="player-row"><span className="avatar">♞</span><div className="player-info"><strong>{game.drill.name}</strong><small>Maia {game.elo} · {thinking?'Maia sta pensando…':game.drill.complete?'Sessione completata':game.turn===game.playerColor?'Tocca a te':'Attendi Maia'}</small></div></div>
        <Board analysisArrows={hint.arrows} animateMove={game.turn===game.playerColor} fen={game.fen} orientation={boardOrientation} legalMoves={game.legalMoves} interactive={!busy&&!thinking&&!game.drill.complete&&game.turn===game.playerColor} onMove={move} lastMove={game.moves.at(-1)}/>
        <div className="board-actions"><button disabled={busy||thinking||game.drill.complete||game.turn!==game.playerColor||!!hint.suggestion?.loading} onClick={()=>void hint.request()} title="Prima scelta di Stockfish (blu) e di Maia (rosso) nella posizione attuale"><span aria-hidden="true">💡</span> Suggerisci mossa</button></div>
        <SuggestionBox suggestion={hint.suggestion} elo={game.elo}/>
        <LichessAnalysis key={game.id} fen={game.fen} orientation={game.playerColor} game={game}/>
      </section>
      <aside className="coach-column"><section className="panel"><span className="eyebrow">PRATICA DI UNA SEQUENZA</span><h2>{game.drill.theme}</h2><p>{game.drill.goal}</p><OpeningStatus game={game} ply={game.version} engine={game.engineLabel??'Maia'}/><p className="drill-count">{game.drill.target?`${game.drill.decisions} / ${game.drill.target} decisioni`:`${game.drill.decisions} decisioni · senza limite`}</p>{game.drill.target>0&&<progress value={game.drill.decisions} max={game.drill.target}/>}
      {game.drill.complete?<div className="drill-target" role="status"><p><strong>{game.result?'Partita conclusa.':`Traguardo raggiunto (${game.drill.decisions}/${game.drill.target} mosse).`}</strong> {game.result?'Guarda la valutazione del drill.':'Prolunga il drill o termina con la valutazione.'}</p>
        <button className="primary full" disabled={busy} onClick={()=>setReviewOpen(true)}>Termina e valuta →</button>{!game.result&&<button className="full" disabled={busy} onClick={()=>void setDrillTarget(0,false)}>Prolunga il drill</button>}</div>
      :game.drill.decisions>0&&<button className="full" disabled={busy||thinking||game.turn!==game.playerColor} onClick={()=>void setDrillTarget(game.drill!.decisions,true)} title="Chiude il drill qui e mostra la valutazione">Termina e valuta</button>}<button className="full" disabled={busy||!game.canUndo} onClick={undo}>Annulla ultima mossa</button><p className="muted">La revisione valuta solo le tue decisioni dopo la posizione iniziale del drill.</p><button className="primary full" disabled={busy||thinking||game.version===game.drill.startPly} onClick={()=>onReview(game)}>{game.drill.complete?'Rivedi il drill':'Rivedi fin qui'} →</button></section><PgnExport game={game}/></aside>
    </div>}
    </div><div role="tabpanel" id="drills-panel-lines" aria-labelledby="drills-tab-lines" hidden={view!=='lines'}>
    {!line&&<section className="panel"><p>Scegli un’apertura e premi <strong>Ripassa la linea</strong>: giocherai tu le mosse di teoria dalla posizione iniziale.</p><button onClick={()=>setView('catalog')}>Scegli un’apertura</button></section>}
    {line&&<LineReview key={line.id} session={line} onSession={setLine} onDrill={id=>void start(id)} onRestart={()=>void startLine(lineStart??{family:line.family,color:line.color})}/>}
    </div><div role="tabpanel" id="drills-panel-catalog" aria-labelledby="drills-tab-catalog" hidden={view!=='catalog'}>
    {(game?.drill&&!game.drill.complete&&!game.result||line?.status==='active')&&<section className="panel drill-resume" role="status"><span>{game?.drill&&!game.drill.complete&&!game.result?<>Drill in corso: <strong>{game.drill.name}</strong> · {game.drill.decisions} {game.drill.decisions===1?'decisione':'decisioni'}</>:<>Ripasso in corso: <strong>{line!.familyName}</strong></>}</span>
      <span className="drill-resume-actions">{game?.drill&&!game.drill.complete&&!game.result&&<button className="primary" onClick={()=>setView('session')}>Riprendi il drill →</button>}{line?.status==='active'&&<button onClick={()=>setView('lines')}>Riprendi il ripasso →</button>}</span></section>}
    <section className="panel drill-settings"><span className="eyebrow">IMPOSTAZIONI</span><h2>Avversario e durata</h2><div className="row"><label>Livello Maia <select aria-label="Livello drill" value={elo} onChange={e=>setElo(Number(e.target.value))}>{[800,1000,1200,1500,1800,2100,2400].map(n=><option key={n}>{n}</option>)}</select></label><label>Colore <select value={color} onChange={e=>setColor(e.target.value as Color)}><option value="w">Bianco</option><option value="b">Nero</option></select></label><label>Tue mosse <select aria-label="Durata drill" value={target} onChange={e=>setTarget(Number(e.target.value))}>{[3,5,8,10,12,15,20].map(n=><option key={n} value={n}>{n}</option>)}<option value={0}>Senza limite</option></select></label></div><p className="footnote">Il colore vale per le aperture; nelle tue posizioni critiche e nel finale di torre è fissato dall'obiettivo. Le sessioni restano nell'archivio.</p></section>
    {(()=>{
      const personal=catalog.filter(t=>t.kind==='personal'),endgames=catalog.filter(t=>t.kind==='endgame')
      const card=(t:Template)=><article className="panel drill-card" key={t.id}>{t.fen&&<MiniBoard fen={t.fen} orientation={t.color??'w'}/>}<div className="drill-card-body"><h3>{t.name}</h3><p>{t.goal}</p><p className="footnote">{t.reason}</p></div><button aria-label={`Avvia ${t.name}`} disabled={busy||thinking} onClick={()=>start(t.id)}>Avvia →</button></article>
      return <>
        <h2 className="group-title">Aperture</h2><p className="muted group-intro"><strong>Contro Maia</strong> parte dalla fine della linea scelta, già giocata sulla scacchiera. <strong>Ripassa la linea</strong> ti fa giocare le mosse di teoria dalla posizione iniziale.</p>
        <OpeningFamilies color={color} disabled={busy||thinking} onDrill={id=>void start(id)} onReview={body=>void startLine(body)}/>
        {personal.length>0&&<section className="panel drill-personal"><div className="section-head"><div><span className="eyebrow">DALLE TUE PARTITE</span><h2>Le tue posizioni critiche</h2></div><span className="count-chip">{personal.length}</span></div><p className="muted">Riparti da un momento in cui hai sbagliato: trova una buona mossa e continua il piano contro Maia.</p>
          <div className="position-grid">{personal.map(t=><button key={t.id} className="position-tile" aria-label={`Avvia ${t.name} · ${t.theme}`} disabled={busy||thinking} onClick={()=>start(t.id)}>{t.fen&&<MiniBoard fen={t.fen} orientation={t.color??'w'}/>}<strong>{t.theme}</strong>{t.source&&<small>{t.source}</small>}</button>)}</div></section>}
        {endgames.length>0&&<><h2 className="group-title">Finali</h2><div className="drill-catalog">{endgames.map(card)}</div></>}
      </>
    })()}
    <section className="panel drill-method"><ThinkingGuide/><p className="muted">Scegli prima un obiettivo; dopo ogni risposta di Maia ricontrolla scacchi, catture e minacce. In revisione vedrai separati gli errori di piano e quelli di calcolo.</p></section>
    </div>
  </div>
}
