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
  expect(createHash('sha256').update(readFileSync(join(root,'../models/maia3/maia3_simplified.onnx'))).digest('hex')).toBe(reference.modelSha256)
  bundle=mkdtempSync(join(tmpdir(),'sparringmate-maia-check-'))
  await build({configFile:false,root,build:{lib:{entry:join(root,'src/engine/maia.ts'),name:'MaiaCheck',formats:['iife'],fileName:()=> 'engine.js'},outDir:bundle,emptyOutDir:false}})
})
async function load(page:Page){await page.goto('/');await page.addScriptTag({path:join(bundle,'engine.js')})}

// Encoding and move table are checked against these references on the server: tests/test_maia.py.
// Move selection (temperature, top-p, opening) is drawn on the server: tests/test_maia.py.

test('Maia on the server reproduces the browser reference predictions at 600, 1500 and 2600, in one request',async({page})=>{
  const requests:{positions:{fen:string;selfElo:number;opponentElo:number}[]}[]=[]
  page.on('request',r=>{if(r.url().endsWith('/api/maia/predict'))requests.push(r.postDataJSON())})
  await load(page)
  const results=await page.evaluate(async cases=>Promise.all(cases.map((item:any)=>(window as any).MaiaCheck.maia.predict(item.fen,item.level,item.level))),reference.cases)
  // Asked in the same tick, every position travels in a single request.
  expect(requests).toHaveLength(1)
  expect(requests[0].positions).toEqual(reference.cases.map((item:any)=>({fen:item.fen,selfElo:item.level,opponentElo:item.level})))
  reference.cases.forEach((item:any,c:number)=>{
    const result=results[c]
    expect(result.moves[0].uci).toBe(item.topMoves[0].uci)
    // Server and browser runtimes differ only by floating-point rounding (docs/maia-server.md): near ties may swap places.
    for(const move of item.topMoves)expect(Math.abs(result.moves.find((m:any)=>m.uci===move.uci).probability-move.probability)).toBeLessThan(.005)
    expect(result.moves.reduce((sum:number,m:any)=>sum+m.probability,0)).toBeCloseTo(1,4)
    expect(Math.abs(result.whiteExpectedScore-item.whiteExpectedScore)).toBeLessThan(.005)
    expect(result.moves.every((m:any)=>typeof m.san==='string'&&m.san.length>0)).toBe(true)
  })
})

test('The interface no longer downloads the Maia model or ONNX Runtime',async({page,request})=>{
  const loaded:string[]=[]
  page.on('request',r=>loaded.push(new URL(r.url()).pathname))
  await page.goto('/')
  await page.getByRole('button',{name:'Gioca',exact:true}).click()
  await expect(page.getByText('Maia pronto',{exact:false})).toBeVisible()
  expect(loaded.filter(path=>/maia3|\.onnx|\/ort\/|maia-worker/.test(path))).toEqual([])
  for(const path of ['/maia3/maia3_simplified.onnx','/maia-worker.js','/ort/ort.wasm.min.js'])expect((await request.get(path)).status()).toBe(404)
})
