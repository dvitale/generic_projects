import {boardSettings} from './boardSettings'

export type MoveSound='move'|'capture'|'check'
let context:AudioContext|null=null

/** Short synthesized clicks: no audio files, nothing leaves this computer. */
export function playMoveSound(kind:MoveSound){
  if(!boardSettings().sound||typeof AudioContext==='undefined')return
  try{
    context??=new AudioContext()
    if(context.state==='suspended')void context.resume()
    const start=context.currentTime
    const knock=(at:number,frequency:number,volume:number)=>{
      const length=Math.floor(context!.sampleRate*.06)
      const buffer=context!.createBuffer(1,length,context!.sampleRate)
      const data=buffer.getChannelData(0)
      for(let i=0;i<length;i++)data[i]=(Math.random()*2-1)*Math.pow(1-i/length,6)
      const source=context!.createBufferSource(),filter=context!.createBiquadFilter(),gain=context!.createGain()
      source.buffer=buffer;filter.type='bandpass';filter.frequency.value=frequency;filter.Q.value=1.4
      gain.gain.value=volume
      source.connect(filter).connect(gain).connect(context!.destination)
      source.start(start+at)
    }
    if(kind==='capture'){knock(0,900,1.1);knock(.045,650,.9)}
    else knock(0,kind==='check'?1700:1150,.8)
  }catch{/* Sound is optional. */}
}
