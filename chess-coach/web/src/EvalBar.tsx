import type {Color,Evaluation} from './types'
import type {MaiaScore} from './useMaiaScore'

export type BarValue={cp:number|null;mate:Color|null;mateIn?:number|null}

/** Converts a side-to-move evaluation to White's perspective. */
export function whiteValue(e:Evaluation,fallback:Color):BarValue{
  const sign=(e.perspective??fallback)==='w'?1:-1
  if(e.mate!==null&&Number.isFinite(e.mate))return {cp:null,mate:(e.mate>0?sign:-sign)>0?'w':'b',mateIn:Math.abs(e.mate)}
  return {cp:e.cp*sign,mate:null}
}

function share(value:BarValue){
  if(value.mate)return value.mate==='w'?100:0
  // Logistic curve: +4 points fills about 90% of the bar.
  return 100/(1+Math.exp(-(value.cp??0)/180))
}

export default function EvalBar({value,orientation}:{value:BarValue|null;orientation:Color}){
  const white=value?share(value):50
  const text=!value?'—':value.mate?(value.mateIn===0?(value.mate==='w'?'1-0':'0-1'):`M${value.mateIn??''}`):`${Math.abs((value.cp??0)/100).toFixed(1)}`
  const leader=!value?null:value.mate??((value.cp??0)>=0?'w':'b')
  const description=!value?'Valutazione non disponibile':value.mate?`${value.mateIn===0?'Scacco matto':'Matto previsto'} per il ${value.mate==='w'?'Bianco':'Nero'}`:`Valutazione Stockfish ${(value.cp??0)>0?'+':''}${((value.cp??0)/100).toFixed(2)} dal punto di vista del Bianco`
  return <div className={`eval-bar stockfish-bar ${orientation==='b'?'flipped':''} ${value?'':'empty'}`} role="img" aria-label={description} title={description}>
    <span className="eval-white" style={{height:`${white}%`}}/>
    <small className={`eval-text ${leader==='b'?'on-black':'on-white'}`}>{text}</small>
  </div>
}

const percent=(x:number)=>`${Math.round(x*100)}%`

/** Second bar: the expected score Maia assigns to White for human players of the given Elo. */
export function MaiaBar({score,orientation}:{score:MaiaScore|null;orientation:Color}){
  const white=score?score.white*100:50
  const leader=score&&score.white<.5?'b':'w'
  const text=!score?'—':String(Math.round(Math.max(score.white,1-score.white)*100))
  const description=!score?'Punteggio atteso Maia non disponibile':`Maia ${score.elo}: punteggio atteso del Bianco ${percent(score.white)} (vince il Bianco ${percent(score.outcome.win)}, patta ${percent(score.outcome.draw)}, vince il Nero ${percent(score.outcome.loss)})`
  return <div className={`eval-bar maia-bar ${orientation==='b'?'flipped':''} ${score?'':'empty'}`} role="img" aria-label={description} title={description}>
    <span className="eval-white" style={{height:`${white}%`}}/>
    <small className={`eval-text ${leader==='b'?'on-black':'on-white'}`}>{text}</small>
  </div>
}
