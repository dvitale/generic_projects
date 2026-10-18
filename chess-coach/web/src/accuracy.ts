import type {Color,Game} from './types'
import type {EvaluationPoint} from './evaluationSeries'

/** Lichess win percentage for White; mates count as certain results. */
export function winPercent(point:Pick<EvaluationPoint,'cp'|'mate'>){
  if(point.mate)return point.mate==='w'?100:0
  const cp=Math.max(-1000,Math.min(1000,point.cp??0))
  return 50+50*(2/(1+Math.exp(-0.00368208*cp))-1)
}

/** Lichess move accuracy from the mover's win percentage before and after, with its +1 uncertainty bonus. */
export function moveAccuracy(before:number,after:number){
  const raw=103.1668100711649*Math.exp(-0.04354415386753951*Math.max(0,before-after))-3.166924740191411
  return Math.max(0,Math.min(100,raw+1))
}

function deviation(values:number[]){
  const mean=values.reduce((a,b)=>a+b,0)/values.length
  return Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/values.length)
}

/**
 * Lichess game accuracy: mean of the volatility-weighted mean and the harmonic mean of move accuracies.
 * Needs an evaluation after every move from `points[0]`; skipped plies keep their positions in the windows.
 */
export function gameAccuracy(game:Game,points:EvaluationPoint[],skip:Set<number>):Record<Color,number|null>{
  const result:Record<Color,number|null>={w:null,b:null}
  const first=points[0]?.position
  if(first===undefined||points.length<3||points.some((p,i)=>p.position!==first+i))return result
  const wins=points.map(winPercent)
  const size=Math.max(2,Math.min(8,Math.floor(wins.length/10)))
  const windows=[...Array(Math.max(0,size-2)).fill(wins.slice(0,size)),...wins.slice(0,wins.length-size+1).map((_,i)=>wins.slice(i,i+size))]
  const weights=windows.map(w=>Math.max(0.5,Math.min(12,deviation(w))))
  const firstTurn:Color=game.initialFen.split(' ')[1]==='b'?'b':'w'
  const moves:Record<Color,{accuracy:number;weight:number}[]>={w:[],b:[]}
  for(let i=0;i+1<wins.length;i++){
    const ply=first+i
    if(skip.has(ply))continue
    const color:Color=(ply%2===0)===(firstTurn==='w')?'w':'b'
    const before=color==='w'?wins[i]:100-wins[i],after=color==='w'?wins[i+1]:100-wins[i+1]
    moves[color].push({accuracy:moveAccuracy(before,after),weight:weights[i]})
  }
  for(const color of ['w','b'] as Color[]){
    const list=moves[color]
    if(!list.length)continue
    const weighted=list.reduce((a,m)=>a+m.accuracy*m.weight,0)/list.reduce((a,m)=>a+m.weight,0)
    const harmonic=list.length/list.reduce((a,m)=>a+1/Math.max(1,m.accuracy),0)
    result[color]=(weighted+harmonic)/2
  }
  return result
}
