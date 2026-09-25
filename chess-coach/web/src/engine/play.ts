import {maia,sample} from './maia'

function pause(milliseconds:number,signal:AbortSignal):Promise<void> {
  if(signal.aborted)return Promise.reject(new DOMException('Turn cancelled','AbortError'))
  if(milliseconds<=0)return Promise.resolve()
  return new Promise((resolve,reject)=>{
    const abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(new DOMException('Turn cancelled','AbortError'))}
    const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},milliseconds)
    signal.addEventListener('abort',abort,{once:true})
  })
}

/** Presentation pacing only: preserve Maia's move distribution and count inference time. */
export async function chooseMaiaMove(fen:string,elo:number,signal:AbortSignal) {
  const started=performance.now()
  const thinkingTime=1200+(Math.random()+Math.random())*1000
  const policy=await maia.predict(fen,elo,elo,signal)
  await pause(thinkingTime-(performance.now()-started),signal)
  if(signal.aborted)throw new DOMException('Turn cancelled','AbortError')
  return sample(policy)
}
