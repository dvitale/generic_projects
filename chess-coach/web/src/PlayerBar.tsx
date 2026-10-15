import type {ReactNode} from 'react'
import type {Color} from './types'

const values:Record<string,number>={p:1,n:3,b:3,r:5,q:9}
const order='qrbnp'
const fullSet:Record<string,number>={p:8,n:2,b:2,r:2,q:1}

function counts(fen:string){
  const result:Record<Color,Record<string,number>>={w:{p:0,n:0,b:0,r:0,q:0},b:{p:0,n:0,b:0,r:0,q:0}}
  for(const c of fen.split(' ')[0]){
    const type=c.toLowerCase()
    if(type in values)result[c===type?'b':'w'][type]++
  }
  return result
}

/** Pieces captured by each side, measured against the initial position (custom starts included). */
export function material(fen:string,initialFen?:string){
  const now=counts(fen),start=initialFen?counts(initialFen):{w:fullSet,b:fullSet}
  const captured=(by:Color)=>{
    const victim:Color=by==='w'?'b':'w'
    return order.split('').flatMap(type=>Array.from({length:Math.max(0,start[victim][type]-now[victim][type])},()=>victim+type))
  }
  const score=(side:Color)=>Object.entries(now[side]).reduce((sum,[type,n])=>sum+values[type]*n,0)
  return {captured,advantage:(side:Color)=>score(side)-score(side==='w'?'b':'w')}
}

export function formatClock(seconds:number){
  const total=Math.round(seconds),m=Math.floor(total/60),s=total%60
  return m>=60?`${Math.floor(m/60)}:${String(m%60).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${m}:${String(s).padStart(2,'0')}`
}

export default function PlayerBar({avatar,name,rating,detail,captured=[],advantage=0,time,active=false,aside,lower=false}:{
  avatar:ReactNode;name:string;rating?:string;detail?:ReactNode;captured?:string[];advantage?:number;time?:number|null;active?:boolean;aside?:ReactNode;lower?:boolean
}){
  return <div className={`player-row ${lower?'lower':''} ${active?'to-move':''}`}>
    <span className={`avatar ${lower?'light':''}`}>{avatar}</span>
    <div className="player-info">
      <div className="player-name"><strong>{name}</strong>{rating&&<span className="rating-chip">{rating}</span>}{captured.length>0&&<span className="captured" aria-label={`Pezzi catturati: ${captured.length}`}>{captured.map((code,i)=><img key={i} src={`/pieces/neo/${code}.png`} alt=""/>)}{advantage>0&&<b>+{advantage}</b>}</span>}</div>
      {detail&&<small>{detail}</small>}
    </div>
    {aside}
    {time!=null&&<span className="player-clock" title="Tempo di riflessione registrato">{formatClock(time)}</span>}
  </div>
}
