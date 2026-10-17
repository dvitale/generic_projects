import {useEffect,useState} from 'react'
import {api} from '../api'
import InfoNote from '../InfoNote'
import StudyBoard,{opposite} from './StudyBoard'
import GamePicker from './GamePicker'
import type {AnalysisArrow} from '../Board'
import type {Saved} from '../GameArchive'
import type {Quiz} from './types'

const kinds={best:'Mossa migliore',refutation:'Risposta avversaria',evaluation:'Valutazione'}

export default function RecallQuiz({games,gameId,onGame,onReview}:{games:Saved[];gameId:string|null;onGame:(id:string)=>void;onReview:(gameId:string,ply:number)=>void}){
  const [quiz,setQuiz]=useState<Quiz|null>(null)
  const [current,setCurrent]=useState(0)
  const [loading,setLoading]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    setQuiz(null);setError('')
    if(!gameId)return
    let stale=false
    setLoading(true)
    api<Quiz>(`/study/games/${gameId}/quiz`).then(q=>{if(stale)return;setQuiz(q);const open=q.questions.findIndex(x=>!x.result);setCurrent(open<0?0:open)})
      .catch(e=>{if(!stale)setError(e instanceof Error?e.message:'Quiz non disponibile')}).finally(()=>{if(!stale)setLoading(false)})
    return()=>{stale=true}
  },[gameId,retry])
  const question=quiz?.questions[current]
  const finished=!!quiz&&quiz.answered===quiz.questions.length
  async function answer(choice:number){
    if(!quiz||!question||question.result||busy)return
    setBusy(true)
    try{setQuiz(await api<Quiz>(`/study/quizzes/${quiz.id}/answers`,{question:question.index,choice}))}
    catch(e){setError(e instanceof Error?e.message:'Risposta non registrata')}
    finally{setBusy(false)}
  }
  const arrows:AnalysisArrow[]=[]
  if(question?.result){
    const correct=question.options[question.result.answer].uci,chosen=question.options[question.result.choice].uci
    if(correct)arrows.push({move:correct,source:'stockfish',rank:1})
    if(chosen&&chosen!==correct)arrows.push({move:chosen,source:'played',rank:1})
  }
  // The player sits at the bottom: after their move it is the opponent's turn.
  const side=question?(question.kind==='best'?question.turn:opposite(question.turn)):'w'
  return <>
    <section className="panel study-toolbar"><GamePicker games={games} value={gameId} onChange={onGame}/>{quiz&&<span className="count-chip" aria-label="Punteggio">{quiz.score} / {quiz.questions.length} corrette</span>}</section>
    {error&&<div className="alert" role="alert">{error}<button onClick={()=>setRetry(n=>n+1)}>Riprova</button></div>}
    {loading&&<section className="panel" role="status"><p>Preparo il quiz: Stockfish verifica che le risposte sbagliate perdano davvero…</p><progress/></section>}
    {!gameId&&!loading&&<section className="panel study-empty"><span className="eyebrow">QUIZ DI RICHIAMO</span><h2>Ricorda prima di rileggere</h2><p>Scegli una partita analizzata: fino a cinque domande sulle tue decisioni più costose. Richiamare da soli la risposta fissa la lezione più che rileggere il commento.</p></section>}
    {quiz&&question&&<div className="training-layout layout-study">
      <StudyBoard fen={question.fen} side={side} arrows={arrows} caption={question.result?'Freccia blu: la risposta corretta. Freccia bianca: la tua scelta.':'Rispondi senza muovere i pezzi.'}/>
      <aside className="coach-column">
        <nav className="quiz-steps" aria-label="Domande">{quiz.questions.map((q,i)=><button key={q.index} aria-current={i===current?'step':undefined} className={q.result?(q.result.correct?'correct':'wrong'):''} onClick={()=>setCurrent(i)}>{i+1}</button>)}</nav>
        <section className="panel quiz-question" aria-label="Domanda del quiz">
          <span className="eyebrow">Domanda {current+1} di {quiz.questions.length} · {kinds[question.kind]}</span>
          <h2>{question.prompt}</h2>
          <div className="quiz-options">{question.options.map((o,i)=>{
            const r=question.result
            const state=r?(i===r.answer?'correct':i===r.choice?'wrong':''):''
            return <button key={i} className={'quiz-option '+state} disabled={busy||!!r} aria-pressed={r?.choice===i} onClick={()=>void answer(i)}>{o.label}{state==='correct'&&<span aria-hidden="true"> ✓</span>}{state==='wrong'&&<span aria-hidden="true"> ✗</span>}</button>})}</div>
          {question.result&&<div role="status" aria-live="polite" className={question.result.correct?'quiz-feedback correct':'quiz-feedback wrong'}>
            <h3>{question.result.correct?'✓ Esatto':'✗ Non proprio'}</h3><p>{question.result.explanation}</p>
            {question.result.line.length>0&&<p className="variation">{question.result.line.join(' ')}</p>}
          </div>}
          <div className="row">
            {question.result&&current<quiz.questions.length-1&&<button className="primary" onClick={()=>setCurrent(current+1)}>Prossima domanda →</button>}
            <button className="quiet" onClick={()=>onReview(quiz.gameId,question.ply)}>Rivedi nella partita</button>
          </div>
        </section>
        {finished&&<section className="panel" role="status"><span className="eyebrow">RISULTATO</span><h2>{quiz.score} risposte corrette su {quiz.questions.length}</h2><p className="muted">{quiz.score===quiz.questions.length?'Ricordi bene le lezioni di questa partita.':'Le domande sbagliate sono le prime da trasformare in flashcard dal pacchetto della partita.'}</p></section>}
        <InfoNote summary="Come sono costruite le domande">Le domande nascono dalle tue tre decisioni più costose. Ogni risposta sbagliata proposta è stata controllata da Stockfish: perde almeno 1,50 punti rispetto a quella corretta (la tua mossa di allora può perdere meno). Conta solo la prima risposta: riprovare dopo aver visto la soluzione non è richiamo.</InfoNote>
      </aside>
    </div>}
  </>
}
