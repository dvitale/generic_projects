function pause(milliseconds:number,signal:AbortSignal):Promise<void> {
  if(signal.aborted)return Promise.reject(new DOMException('Turn cancelled','AbortError'))
  if(milliseconds<=0)return Promise.resolve()
  return new Promise((resolve,reject)=>{
    const abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(new DOMException('Turn cancelled','AbortError'))}
    const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},milliseconds)
    signal.addEventListener('abort',abort,{once:true})
  })
}

/** A human-like pause before a reply computed on the server; waiting first means a cancelled turn commits nothing. */
export async function paceServerReply<T>(reply:()=>Promise<T>,signal:AbortSignal) {
  await pause(1200+(Math.random()+Math.random())*1000,signal)
  return reply()
}
