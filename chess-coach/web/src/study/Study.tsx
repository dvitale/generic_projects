import {useState} from 'react'
import PanelTabs from '../PanelTabs'
import Flashcards from './Flashcards'
import RecallQuiz from './RecallQuiz'
import MockExam from './MockExam'
import GamePack,{type PackActions} from './GamePack'
import PositionTutor from './PositionTutor'
import Notebook from './Notebook'
import type {Saved} from '../GameArchive'
import type {StudySection,StudyPosition} from './types'

const sections:{id:StudySection;label:string}[]=[{id:'cards',label:'Flashcard'},{id:'quiz',label:'Quiz'},{id:'exam',label:'Esame di prova'},{id:'pack',label:'Impara da una partita'},{id:'ask',label:'Chiedi al tutor'},{id:'notebook',label:'Quaderno'}]

/** The study tab: tools that turn analysed games into recall practice, kept apart from play and review. */
export default function Study({games,section,onSection,gameId,onGame,actions}:{games:Saved[];section:StudySection;onSection:(s:StudySection)=>void;gameId:string|null;onGame:(id:string)=>void;actions:Omit<PackActions,'onQuiz'|'onAsk'>}){
  const [position,setPosition]=useState<StudyPosition|null>(null)
  const ask=(p:StudyPosition)=>{setPosition(p);onSection('ask')}
  return <div className="study">
    <PanelTabs id="study" label="Strumenti di studio" value={section} onChange={value=>onSection(value as StudySection)} items={sections}/>
    <div role="tabpanel" id={'study-panel-'+section} aria-labelledby={'study-tab-'+section}>
      {section==='cards'&&<Flashcards onReview={actions.onReview}/>}
      {section==='quiz'&&<RecallQuiz games={games} gameId={gameId} onGame={onGame} onReview={actions.onReview}/>}
      {section==='exam'&&<MockExam onPuzzle={actions.onPuzzle} onReview={actions.onReview}/>}
      {section==='pack'&&<GamePack games={games} gameId={gameId} onGame={onGame} actions={{...actions,onQuiz:()=>onSection('quiz'),onAsk:ask}}/>}
      {section==='ask'&&<PositionTutor position={position}/>}
      {section==='notebook'&&<Notebook onPack={id=>{onGame(id);onSection('pack')}} onReview={actions.onReview} onAsk={ask}/>}
    </div>
  </div>
}
