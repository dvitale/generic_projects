import type {Color} from './types'

type Score={cp:number;mate:number|null}

/** An engine score given from the side to move (`mover`), shown on the one objective scale used everywhere:
 * positive means White is better, negative Black. What one side gains the other loses. */
export function objectiveScore(s:Score,mover:Color){
  const sign=mover==='w'?1:-1
  if(s.mate!==null){const mate=s.mate*sign;return `matto del ${mate>0?'Bianco':'Nero'} in ${Math.abs(mate)}`}
  const cp=s.cp*sign
  return `${cp>=0?'+':'−'}${(Math.abs(cp)/100).toFixed(2).replace('.',',')}`
}


// Without a position (older saved data) the side defaults to White.
export const moverOf=(fen?:string):Color=>fen?.split(' ')[1]==='b'?'b':'w'
