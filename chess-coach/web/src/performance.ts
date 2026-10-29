import calibration from './data/accuracy-rating.json' with {type:'json'}

export interface Performance {rating:number;low:number;high:number;games:number}

const round50=(v:number)=>Math.round(v/50)*50
const {bands,likelihood,temper}=calibration

function chance(row:number[],accuracy:number){
  const a=Math.max(0,Math.min(100,accuracy)),i=Math.min(99,Math.floor(a))
  return row[i]+(row[i+1]-row[i])*(a-i)
}

/**
 * Lichess rating range that best explains these game accuracies, every level 600–2600 equally likely beforehand.
 * Median and 10th–90th percentiles; mirrors `estimate` in scripts/calibrate_accuracy_rating.py.
 */
export function performanceFromAccuracies(accuracies:number[]):Performance|null{
  if(!accuracies.length)return null
  const logs=likelihood.map(row=>temper*accuracies.reduce((s,a)=>s+Math.log(chance(row,a)),0))
  const top=Math.max(...logs),weights=logs.map(v=>Math.exp(v-top)),total=weights.reduce((a,b)=>a+b,0)
  const quantile=(q:number)=>{
    let cumulative=0
    for(let i=0;i<bands.length;i++){
      const share=weights[i]/total
      if(cumulative+share>=q)return Math.min(bands[bands.length-1],Math.max(bands[0],bands[i]-50+100*(q-cumulative)/share))
      cumulative+=share
    }
    return bands[bands.length-1]
  }
  return {rating:round50(quantile(.5)),low:round50(quantile(.1)),high:round50(quantile(.9)),games:accuracies.length}
}

/** One game: needs the same minimum of moves as the calibration. */
export function performanceFromAccuracy(accuracy:number|null,moves:number){
  return accuracy===null||moves<calibration.minMoves?null:performanceFromAccuracies([accuracy])
}

export const calibrationInfo={source:calibration.source,games:calibration.games,minMoves:calibration.minMoves,validation:calibration.validation}
