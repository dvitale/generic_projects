import {test,expect,type Page} from '@playwright/test'
import {mkdtempSync,readFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join,resolve} from 'node:path'
import {createHash} from 'node:crypto'
import {build} from 'vite'
const reference=JSON.parse(readFileSync(new URL('./fixtures/maia-browser-reference.json',import.meta.url),'utf8'))
let bundle:string
test.beforeAll(async()=>{
  const root=resolve('.')
  expect(createHash('sha256').update(readFileSync(join(root,'public/maia3/maia3_simplified.onnx'))).digest('hex')).toBe(reference.modelSha256)
  bundle=mkdtempSync(join(tmpdir(),'sparringmate-maia-check-'))
  await build({configFile:false,root,build:{lib:{entry:join(root,'src/engine/maia.ts'),name:'MaiaCheck',formats:['iife'],fileName:()=> 'engine.js'},outDir:bundle,emptyOutDir:false}})
})
async function load(page:Page){await page.goto('/');await page.addScriptTag({path:join(bundle,'engine.js')})}

// Synthetic positions cross-checked against CSSLab preprocessing and postprocessing.
// Keep the reference revision and model hash explicit when updating the fixtures.
test('Maia tokenization and legal mask match reference positions for both colors and special moves',async({page})=>{
  await load(page)
  for(const item of reference.cases){
    const result=await page.evaluate(fen=>{
      const encoded=(window as any).MaiaCheck.encode(fen)
      return {tokens:Array.from(encoded.tokens as Float32Array).flatMap((v,i)=>v===1?[i]:[]),legal:encoded.legal.map((m:any)=>m.index).sort((a:number,b:number)=>a-b)}
    },item.fen)
    expect(result.tokens).toEqual(item.occupiedTokenIndices)
    expect(result.legal).toEqual(item.legalIndices)
  }
})

test('Full-policy sampling can select a low-probability move and does not mean top-1 selection',async({page})=>{
  await load(page)
  const policy={whiteExpectedScore:.5,moves:[
    {uci:'e2e4',san:'e4',probability:.8},
    {uci:'d2d4',san:'d4',probability:.19},
    {uci:'g2g4',san:'g4',probability:.01},
  ]}
  for(const [draw,expected] of [[.4,'e2e4'],[.9,'d2d4'],[.999,'g2g4']] as const){
    expect(await page.evaluate(({policy,draw})=>{
      const original=Math.random
      try{Math.random=()=>draw;return (window as any).MaiaCheck.sample(policy)}finally{Math.random=original}
    },{policy,draw})).toBe(expected)
  }
})

test('Real browser Maia reproduces reference predictions at 600, 1500 and 2600',async({page})=>{
  await page.addInitScript(()=>{
    const NativeWorker=window.Worker
    ;(window as any).maiaInputs=[]
    window.Worker=class extends NativeWorker{
      postMessage(message:any,transfer:any){
        if(message.type==='inference')(window as any).maiaInputs.push({self:new Float32Array(message.eloSelfs)[0],opponent:new Float32Array(message.eloOppos)[0]})
        super.postMessage(message,transfer)
      }
    }
  })
  await load(page)
  for(const item of reference.cases){
    const result=await page.evaluate(async item=>(window as any).MaiaCheck.maia.predict(item.fen,item.level,item.level),item)
    expect(result.moves.slice(0,3).map((m:any)=>m.uci)).toEqual(item.topMoves.map(m=>m.uci))
    for(let i=0;i<item.topMoves.length;i++)expect(result.moves[i].probability).toBeCloseTo(item.topMoves[i].probability,5)
    expect(result.moves.reduce((sum:number,m:any)=>sum+m.probability,0)).toBeCloseTo(1,8)
    expect(Math.abs(result.whiteExpectedScore-item.whiteExpectedScore)).toBeLessThan(.0001)
    expect(await page.evaluate(()=>(window as any).maiaInputs.at(-1))).toEqual({self:item.level,opponent:item.level})
  }
})
