import {maia,sample,FULL_SELECTION,type Selection} from './maia'

function pause(milliseconds:number,signal:AbortSignal):Promise<void> {
  if(signal.aborted)return Promise.reject(new DOMException('Turn cancelled','AbortError'))
  if(milliseconds<=0)return Promise.resolve()
  return new Promise((resolve,reject)=>{
    const abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(new DOMException('Turn cancelled','AbortError'))}
    const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},milliseconds)
    signal.addEventListener('abort',abort,{once:true})
  })
}

/** Same pacing as Maia for a reply computed on the server; waiting first means a cancelled turn commits nothing. */
export async function paceServerReply<T>(reply:()=>Promise<T>,signal:AbortSignal) {
  await pause(1200+(Math.random()+Math.random())*1000,signal)
  return reply()
}

/** Presentation pacing only: preserve Maia's move distribution and count inference time. */
export async function chooseMaiaMove(fen:string,elo:number,signal:AbortSignal,selection:Selection=FULL_SELECTION) {
  const started=performance.now()
  const thinkingTime=1200+(Math.random()+Math.random())*1000
  const policy=await maia.predict(fen,elo,elo,signal)
  await pause(thinkingTime-(performance.now()-started),signal)
  if(signal.aborted)throw new DOMException('Turn cancelled','AbortError')
  // The FEN's full-move number tells the opening apart; positions set up mid-game use their own number.
  return sample(policy,selection,Number(fen.split(' ')[5])||Infinity)
}
