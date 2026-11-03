import type {Color,Evaluation} from '../types'

export type Rating='again'|'hard'|'good'|'easy'
export interface Card {id:number;kind:'explanation'|'note';fen:string;turn:Color;move:string|null;san:string|null;bestMove:string|null;bestSan:string|null;question:string;lesson:string;theme:string;gameId:string|null;ply:number|null;dueAt:string;reps:number;lapses:number;intervalDays:number;legalMoves:string[];preview:Record<Rating,number>}
export interface CardTry {move:string;san:string;cp:number;mate:number|null;loss:number;label:string;accepted:boolean;sameAsPlayed:boolean;sameAsBest:boolean;
  best:{move:string|null;san:string|null;cp:number;mate:number|null};played:{san:string;cp:number;mate:number|null;loss:number}|null}
export interface CardsOverview {due:Card[];total:number;nextDue:string|null;reviewedToday:number}

export interface QuizQuestion {index:number;kind:'best'|'refutation'|'evaluation';prompt:string;fen:string;turn:Color;ply:number;options:{uci:string|null;label:string}[];result?:{choice:number;correct:boolean;answer:number;explanation:string;line:string[]}}
export interface Quiz {id:string;gameId:string;questions:QuizQuestion[];answered:number;score:number}

export interface ExamItem {index:number;fen:string;turn:Color;legalMoves:string[];answered:boolean;exerciseId?:string;gameId?:string;ply?:number;theme?:string;success?:boolean;move?:string|null;san?:string|null;lossCp?:number|null;best?:Evaluation|null}
export interface Exam {id:string;createdAt:string;deadline:string;finishedAt:string|null;size:number;answered:number;items:ExamItem[];score?:number;themes?:{theme:string;total:number;solved:number}[]}
export interface ExamHistory {history:{id:string;createdAt:string;size:number;score:number}[];active:Exam|null;nextRecommended:string|null;cadenceDays:number}

export interface Moment {ply:number;fen:string;turn:Color;moveNumber:number;played:string;playedSan:string;best:string[];bestSan:string[];line:string[];refutation?:string[];loss:number;lossCp?:number|null;label:string;theme?:string;insight?:string|null;exerciseId?:string|null;preventionId?:string|null;cards?:number}
export interface Pack {gameId:string;title:string;createdAt:string;playerColor:Color;quality:{decisions:number;sound:number;inaccuracies:number;errors:number;missedMates?:number};moments:Moment[];quiz:{answered:number;score:number;total:number}|null}

export interface Answer {answer:string;lesson:string;provider:string;notice?:string;best:{cp:number;mate:number|null;pv:string[];san:string[]};moves:{san:string;uci:string;cp:number;mate:number|null;lossCp:number|null;line:string[]}[];perspective:Color}

export type NotebookExample=Moment&{gameId:string;gameTitle:string;createdAt:string;lessons:string[]}
export interface NotebookTheme {theme:string;count:number;errors:number;lessons:string[];examples:NotebookExample[]}

/** A position handed from one study panel to another, e.g. from the game pack to the tutor. */
export interface StudyPosition {fen:string;title:string;gameId?:string;ply?:number;move?:string}
export type StudySection='cards'|'quiz'|'exam'|'pack'|'ask'|'notebook'
export interface Refutation {fen:string;move:string;san:string}

export const pawns=(cp:number)=>(cp/100).toFixed(2).replace('.',',')
// Engine scores come from the side to move; they are shown on the objective scale, like everywhere in the app.
export {objectiveScore as scoreText} from '../evalText'
