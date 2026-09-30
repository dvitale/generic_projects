import {Chess} from 'chess.js'
import type {Color,Evaluation,Game} from './types'

export interface EvaluationPoint {position:number;label:string;cp:number|null;mate:Color|null;terminal:boolean;depth:number;initial:boolean}

/** Actual move evaluations are in the mover's perspective, not White's. */
export function evaluationSeries(game:Game){
  const rows=game.analysis?.moves?.length?game.analysis.moves:game.analysis?.decisions??[]
  const indexed=new Map(rows.filter(d=>d.ply>=0&&d.ply<game.moves.length&&game.moves[d.ply]===d.played).map(d=>[d.ply,d]))
  const start=indexed.size?Math.min(...indexed.keys()):0
  const points:EvaluationPoint[]=[]
  const board=new Chess(game.initialFen)
  function add(position:number,label:string,value:Evaluation,fallback:Color,initial=false){
    const perspective=value.perspective??fallback
    const sign=perspective==='w'?1:-1
    let cp=Number.isFinite(value.cp)?value.cp*sign:null
    let mate:Color|null=value.mate!==null&&Number.isFinite(value.mate)?(value.mate>0?sign:-sign)>0?'w':'b':null
    const terminal=board.isGameOver()
    if(board.isCheckmate()){mate=board.turn()==='w'?'b':'w';cp=null}
    else if(board.isDraw()){cp=0;mate=null}
    else if(mate)cp=null
    if(cp===null&&!mate)return
    points.push({position,label,cp,mate,terminal,depth:value.depth,initial})
  }
  for(let ply=0;ply<game.moves.length;ply++){
    const row=indexed.get(ply)
    const side=board.turn(),number=board.moveNumber()
    if(ply===start&&row)add(ply,ply===0?'Posizione iniziale':'Inizio della parte analizzata',row.best,side,true)
    const uci=game.moves[ply]
    const move=board.move({from:uci.slice(0,2),to:uci.slice(2,4),promotion:uci[4]})
    if(row)add(ply+1,`${number}${side==='w'?'.':'…'} ${move.san}`,row.actual,side)
  }
  return {points,start,complete:points.length===game.moves.length-start+1&&points.length>1}
}

export function evaluationText(point:EvaluationPoint){
  if(point.mate)return `${point.terminal?'Scacco matto':'Matto previsto'} · ${point.mate==='w'?'Bianco':'Nero'}`
  if(point.terminal)return 'Patta · 0,00'
  const value=(point.cp??0)/100
  return `${value>0?'+':''}${value.toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})}`
}
