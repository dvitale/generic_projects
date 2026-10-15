import type {Decision} from './types'

export type MoveClass='best'|'good'|'inaccuracy'|'error'|'forced'

/** Same thresholds as the backend labels: 80 and 180 centipawns. */
export function classifyMove(d:Pick<Decision,'loss'|'played'|'best'|'forced'>):MoveClass{
  if(d.forced)return 'forced'
  if(d.loss>=180)return 'error'
  if(d.loss>=80)return 'inaccuracy'
  return d.best.pv[0]===d.played?'best':'good'
}

export const moveClassInfo:Record<MoveClass,{symbol:string;label:string}>={
  best:{symbol:'★',label:'Scelta di Stockfish'},
  good:{symbol:'✓',label:'Buona scelta'},
  inaccuracy:{symbol:'?!',label:'Imprecisione'},
  error:{symbol:'?',label:'Errore rilevante'},
  forced:{symbol:'□',label:'Mossa obbligata'},
}

export function MoveClassIcon({kind}:{kind:MoveClass}){
  return <span className={`move-class move-class-${kind}`} title={moveClassInfo[kind].label}>{moveClassInfo[kind].symbol}</span>
}
