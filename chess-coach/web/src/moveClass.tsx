import type {Decision} from './types'

export type MoveClass='best'|'good'|'inaccuracy'|'error'|'blunder'|'missedMate'|'forced'

/** Backend thresholds for inaccuracies and errors (80 and 180 centipawns); 300 or more is a blunder. The loss is on the
 * capped outcome scale (review_loss: beyond ±600 the game is decided); a mate in 1–2 not played is its own class. */
export function classifyMove(d:Pick<Decision,'loss'|'played'|'best'|'forced'|'missedMate'>):MoveClass{
  if(d.forced)return 'forced'
  if(d.missedMate)return 'missedMate'
  if(d.loss>=300)return 'blunder'
  if(d.loss>=180)return 'error'
  if(d.loss>=80)return 'inaccuracy'
  return d.best.pv[0]===d.played?'best':'good'
}

export const moveClassInfo:Record<MoveClass,{symbol:string;label:string}>={
  best:{symbol:'★',label:'Scelta di Stockfish'},
  good:{symbol:'✓',label:'Buona scelta'},
  inaccuracy:{symbol:'?!',label:'Imprecisione'},
  error:{symbol:'?',label:'Errore rilevante'},
  blunder:{symbol:'??',label:'Errore grave'},
  missedMate:{symbol:'#?',label:'Matto mancato'},
  forced:{symbol:'□',label:'Mossa obbligata'},
}

export function MoveClassIcon({kind}:{kind:MoveClass}){
  return <span className={`move-class move-class-${kind}`} title={moveClassInfo[kind].label}>{moveClassInfo[kind].symbol}</span>
}
