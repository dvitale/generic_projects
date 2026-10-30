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

interface Template { id:string; name:string; kind:string; theme:string; goal:string; reason:string; color:Color|null; fen?:string; source?:string }
export default function Drills({onReview,startTemplateId,onStarted}:{onReview:(game:Game)=>void;startTemplateId?:string|null;onStarted?:()=>void}) {
  const [view,setView]=useState('catalog')
  const [catalog,setCatalog]=useState<Template[]>([])
  const [game,setGame]=useState<Game|null>(null)
  const boardOrientation=useBoardOrientation(game?.playerColor??'w')
  const [elo,setElo]=useState(1500)
  const [color,setColor]=useState<Color>('w')
  const [target,setTarget]=useState(5)
  const [busy,setBusy]=useState(false)
  const [thinking,setThinking]=useState(false)
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  const botController=useRef<AbortController|null>(null)
  const hint=useMoveSuggestion(view==='session'?game:null)
  const moveTime=useMoveTime(game,view==='session'&&!!game&&!game.result&&!game.drill?.complete)
  function fail(e:unknown){setError(e instanceof Error?e.message:'Operazione non riuscita')}
  function keep(g:Game,newTurn=false){if(newTurn)moveTime.begin(g);setGame(g);localStorage.setItem('chess-coach-drill',g.id)}
  useEffect(()=>{
    api<Template[]>('/drills').then(setCatalog).catch(fail)
    if(startTemplateId){start(startTemplateId).then(()=>onStarted?.());return}
    const id=localStorage.getItem('chess-coach-drill')
    if(id)api<Game>('/games/'+id).then(g=>{keep(g);setView('session')}).catch(()=>localStorage.removeItem('chess-coach-drill'))
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
  async function start(id:string){
    setBusy(true);setError('')
    try{keep(await api<Game>(`/drills/${encodeURIComponent(id)}/start`,{color,elo,target}),true);setView('session')}
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
    <PanelTabs id="drills" label="Pannelli dei drill" value={view} onChange={setView} items={[{id:'catalog',label:'Scegli un drill'},{id:'session',label:'Sessione'}]}/>
    <div role="tabpanel" id="drills-panel-session" aria-labelledby="drills-tab-session" hidden={view!=='session'}>
    {!game&&<section className="panel"><p>Scegli un drill per iniziare una sessione.</p><button onClick={()=>setView('catalog')}>Scegli un drill</button></section>}
    {game?.drill&&<div className="training-layout">
      <section className="board-column"><div className="player-row"><span className="avatar">♞</span><div className="player-info"><strong>{game.drill.name}</strong><small>Maia {game.elo} · {thinking?'Maia sta pensando…':game.drill.complete?'Sessione completata':game.turn===game.playerColor?'Tocca a te':'Attendi Maia'}</small></div></div>
        <Board analysisArrows={hint.arrows} animateMove={game.turn===game.playerColor} fen={game.fen} orientation={boardOrientation} legalMoves={game.legalMoves} interactive={!busy&&!thinking&&!game.drill.complete&&game.turn===game.playerColor} onMove={move} lastMove={game.moves.at(-1)}/>
        <div className="board-actions"><button disabled={busy||thinking||game.drill.complete||game.turn!==game.playerColor||!!hint.suggestion?.loading} onClick={()=>void hint.request()} title="Prima scelta di Stockfish (blu) e di Maia (rosso) nella posizione attuale"><span aria-hidden="true">💡</span> Suggerisci mossa</button></div>
        <SuggestionBox suggestion={hint.suggestion} elo={game.elo}/>
        <LichessAnalysis key={game.id} fen={game.fen} orientation={game.playerColor} game={game}/>
      </section>
      <aside className="coach-column"><section className="panel"><span className="eyebrow">PRATICA DI UNA SEQUENZA</span><h2>{game.drill.theme}</h2><p>{game.drill.goal}</p><p className="drill-count">{game.drill.decisions} / {game.drill.target} decisioni</p><progress value={game.drill.decisions} max={game.drill.target}/><button className="full" disabled={busy||!game.canUndo} onClick={undo}>Annulla ultima mossa</button><p className="muted">La revisione valuta solo le tue decisioni dopo la posizione iniziale del drill.</p><button className="primary full" disabled={busy||thinking||game.version===game.drill.startPly} onClick={()=>onReview(game)}>{game.drill.complete?'Rivedi il drill':'Rivedi fin qui'} →</button>{game.drill.complete&&<p role="status">Drill completato. Verifica le tue scelte prima di ripartire.</p>}</section><PgnExport game={game}/></aside>
    </div>}
    </div><div role="tabpanel" id="drills-panel-catalog" aria-labelledby="drills-tab-catalog" hidden={view!=='catalog'}>
    <section className="panel drill-settings"><span className="eyebrow">IMPOSTAZIONI</span><h2>Avversario e durata</h2><div className="row"><label>Livello Maia <select aria-label="Livello drill" value={elo} onChange={e=>setElo(Number(e.target.value))}>{[800,1000,1200,1500,1800,2100,2400].map(n=><option key={n}>{n}</option>)}</select></label><label>Colore <select value={color} onChange={e=>setColor(e.target.value as Color)}><option value="w">Bianco</option><option value="b">Nero</option></select></label><label>Tue decisioni <select aria-label="Durata drill" value={target} onChange={e=>setTarget(Number(e.target.value))}>{[3,5,8,12].map(n=><option key={n}>{n}</option>)}</select></label></div><p className="footnote">Nelle tue posizioni critiche e nel finale di torre il colore è fissato dall'obiettivo. Le sessioni restano nell'archivio.</p></section>
    {(()=>{
      const personal=catalog.filter(t=>t.kind==='personal'),openings=catalog.filter(t=>t.kind!=='personal'&&t.kind!=='endgame'),endgames=catalog.filter(t=>t.kind==='endgame')
      const card=(t:Template)=><article className="panel drill-card" key={t.id}>{t.fen&&<MiniBoard fen={t.fen} orientation={t.color??'w'}/>}<div className="drill-card-body"><h3>{t.name}</h3><p>{t.goal}</p><p className="footnote">{t.reason}</p></div><button aria-label={`Avvia ${t.name}`} disabled={busy||thinking} onClick={()=>start(t.id)}>Avvia →</button></article>
      return <>
        {personal.length>0&&<section className="panel drill-personal"><div className="section-head"><div><span className="eyebrow">DALLE TUE PARTITE</span><h2>Le tue posizioni critiche</h2></div><span className="count-chip">{personal.length}</span></div><p className="muted">Riparti da un momento in cui hai sbagliato: trova una buona mossa e continua il piano contro Maia.</p>
          <div className="position-grid">{personal.map(t=><button key={t.id} className="position-tile" aria-label={`Avvia ${t.name} · ${t.theme}`} disabled={busy||thinking} onClick={()=>start(t.id)}>{t.fen&&<MiniBoard fen={t.fen} orientation={t.color??'w'}/>}<strong>{t.theme}</strong>{t.source&&<small>{t.source}</small>}</button>)}</div></section>}
        {openings.length>0&&<><h2 className="group-title">Aperture</h2><div className="drill-catalog">{openings.map(card)}</div></>}
        {endgames.length>0&&<><h2 className="group-title">Finali</h2><div className="drill-catalog">{endgames.map(card)}</div></>}
      </>
    })()}
    <section className="panel drill-method"><ThinkingGuide/><p className="muted">Scegli prima un obiettivo; dopo ogni risposta di Maia ricontrolla scacchi, catture e minacce. In revisione vedrai separati gli errori di piano e quelli di calcolo.</p></section>
    </div>
  </div>
}
