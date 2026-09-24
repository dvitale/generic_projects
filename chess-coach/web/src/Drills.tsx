import { useEffect, useState } from 'react'
import Board from './Board'
import { api } from './api'
import { maia, sample } from './engine/maia'
import type { Color, Game } from './types'

interface Template { id:string; name:string; kind:string; theme:string; goal:string; reason:string; color:Color|null }
export default function Drills({onReview,startTemplateId,onStarted}:{onReview:(game:Game)=>void;startTemplateId?:string|null;onStarted?:()=>void}) {
  const [catalog,setCatalog]=useState<Template[]>([])
  const [game,setGame]=useState<Game|null>(null)
  const [elo,setElo]=useState(1500)
  const [color,setColor]=useState<Color>('w')
  const [target,setTarget]=useState(5)
  const [busy,setBusy]=useState(false)
  const [thinking,setThinking]=useState(false)
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  function fail(e:unknown){setError(e instanceof Error?e.message:'Operazione non riuscita')}
  function keep(g:Game){setGame(g);localStorage.setItem('chess-coach-drill',g.id)}
  useEffect(()=>{
    api<Template[]>('/drills').then(setCatalog).catch(fail)
    if(startTemplateId){start(startTemplateId).then(()=>onStarted?.());return}
    const id=localStorage.getItem('chess-coach-drill')
    if(id)api<Game>('/games/'+id).then(keep).catch(()=>localStorage.removeItem('chess-coach-drill'))
  },[])
  useEffect(()=>{
    if(!game||game.drill?.complete||game.result||game.turn===game.playerColor)return
    let cancelled=false
    const snapshot=game
    setThinking(true)
    ;(async()=>{
      const move=sample(await maia.predict(snapshot.fen,snapshot.elo,snapshot.elo))
      if(cancelled||!move)return
      const next=await api<Game>(`/games/${snapshot.id}/moves`,{move,version:snapshot.version,actor:'maia'})
      if(!cancelled)keep(next)
    })().catch(e=>{if(!cancelled)fail(e)}).finally(()=>{if(!cancelled)setThinking(false)})
    return()=>{cancelled=true;setThinking(false)}
  },[game?.id,game?.version,retry])
  async function start(id:string){
    setBusy(true);setError('')
    try{keep(await api<Game>(`/drills/${encodeURIComponent(id)}/start`,{color,elo,target}))}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  async function move(move:string){
    if(!game||busy)return
    setBusy(true);setError('')
    try{keep(await api<Game>(`/games/${game.id}/moves`,{move,version:game.version,actor:'human'}))}
    catch(e){fail(e)}finally{setBusy(false)}
  }
  return <div>
    {error&&<div className="alert" role="alert">{error}<button onClick={()=>{setError('');setRetry(n=>n+1)}}>Riprova</button></div>}
    {game?.drill&&<div className="training-layout">
      <section className="board-column"><div className="player-row"><span className="avatar">♞</span><div><strong>{game.drill.name}</strong><small>Maia {game.elo} · {thinking?'Maia sta pensando…':game.drill.complete?'Sessione completata':game.turn===game.playerColor?'Tocca a te':'Attendi Maia'}</small></div></div>
        <Board fen={game.fen} orientation={game.playerColor} legalMoves={game.legalMoves} interactive={!busy&&!thinking&&!game.drill.complete&&game.turn===game.playerColor} onMove={move} lastMove={game.moves.at(-1)}/>
      </section>
      <aside className="coach-column"><section className="panel"><span className="eyebrow">PRATICA DI UNA SEQUENZA</span><h2>{game.drill.theme}</h2><p>{game.drill.goal}</p><p className="drill-count">{game.drill.decisions} / {game.drill.target} decisioni</p><progress value={game.drill.decisions} max={game.drill.target}/><p className="muted">La revisione valuta solo le tue decisioni dopo la posizione iniziale del drill.</p><button className="primary full" disabled={busy||thinking||game.version===game.drill.startPly} onClick={()=>onReview(game)}>{game.drill.complete?'Rivedi il drill':'Rivedi fin qui'} →</button>{game.drill.complete&&<p role="status">Drill completato. Verifica le tue scelte prima di ripartire.</p>}</section></aside>
    </div>}
    <section className="panel drill-settings"><span className="eyebrow">PREPARA LA PROSSIMA SESSIONE</span><h2>Aperture, finali e tue posizioni</h2><div className="row"><label>Livello Maia <select aria-label="Livello drill" value={elo} onChange={e=>setElo(Number(e.target.value))}>{[800,1000,1200,1500,1800,2100,2400].map(n=><option key={n}>{n}</option>)}</select></label><label>Colore <select value={color} onChange={e=>setColor(e.target.value as Color)}><option value="w">Bianco</option><option value="b">Nero</option></select></label><label>Tue decisioni <select aria-label="Durata drill" value={target} onChange={e=>setTarget(Number(e.target.value))}>{[3,5,8,12].map(n=><option key={n}>{n}</option>)}</select></label></div><p className="footnote">Nelle tue posizioni critiche e nel finale di torre il colore è fissato dall'obiettivo. Le sessioni restano nell'archivio.</p></section>
    <div className="drill-catalog">{catalog.map(t=><section className="panel" key={t.id}><span className="eyebrow">{t.kind==='personal'?'DALLE TUE PARTITE':t.kind==='endgame'?'FINALE':'APERTURA'}</span><h3>{t.name}</h3><p>{t.goal}</p><p className="footnote">{t.reason}</p><button disabled={busy||thinking} onClick={()=>start(t.id)}>Avvia {t.name} →</button></section>)}</div>
  </div>
}
