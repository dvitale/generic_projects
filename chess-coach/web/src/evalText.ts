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

/** The standard wording for the scale and for losses, the same in every section. */
export const SCORE_NOTE='Punteggio oggettivo: positivo se è avanti il Bianco, negativo se è avanti il Nero. Perdere 1,20 significa, per il Bianco, scendere di 1,20 (da 0,00 a −1,20); per il Nero, salire di 1,20 (da 0,00 a +1,20).'

// Without a position (older saved data) the side defaults to White.
export const moverOf=(fen?:string):Color=>fen?.split(' ')[1]==='b'?'b':'w'
