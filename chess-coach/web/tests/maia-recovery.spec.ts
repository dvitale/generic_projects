import {test,expect,type Page} from '@playwright/test'

const pgn='1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. Nbd2 Bb7 12. Bc2 h6 *'

async function mockWorker(page:Page,failure:'once-policy'|'once-value'|'always'|'none'){
  await page.addInitScript(failure=>{
    const state={active:0,maxActive:0,workers:0,inferences:0,invalid:0,failure}
    ;(window as any).maiaTest=state
    class TestWorker {
      onmessage:((event:any)=>void)|null=null
      onerror:((event:any)=>void)|null=null
      closed=false
      pending=new Set<ReturnType<typeof setTimeout>>()
      constructor(){state.workers++}
      postMessage(message:any){
        if(message.type==='init'){queueMicrotask(()=>{if(!this.closed)this.onmessage?.({data:{type:'status',status:'ready'}})});return}
        if(message.type!=='inference')return
        state.inferences++;state.active++;state.maxActive=Math.max(state.active,state.maxActive)
        const collision=state.active>1
        const corrupt=state.failure==='always'||(state.inferences===5&&state.failure.startsWith('once-'))
        const timer=setTimeout(()=>{
          this.pending.delete(timer);state.active--
          if(this.closed)return
          const logitsMove=new Float32Array(4352)
          const logitsValue=new Float32Array(3)
          if(collision||corrupt){state.invalid++;if(state.failure==='once-value')logitsValue[0]=NaN;else logitsMove.fill(NaN)}
          this.onmessage?.({data:{type:'inference-result',id:message.id,logitsMove:logitsMove.buffer,logitsValue:logitsValue.buffer}})
        },2)
        this.pending.add(timer)
      }
      terminate(){this.closed=true;for(const timer of this.pending){clearTimeout(timer);state.active--}this.pending.clear()}
    }
    ;(window as any).Worker=TestWorker
  },failure)
}

for(const failure of ['none','once-policy','once-value'] as const){
  test(`Rating and position review serialize inference and recover from ${failure}`,async({page,request})=>{
    const game=await(await request.post('/api/import',{data:{pgn}})).json()
    await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
    await mockWorker(page,failure)
    await page.goto('/')
    const panel=page.getByRole('region',{name:'Valutazione Elo della partita'})
  await page.getByRole('tab',{name:'Elo',exact:true}).click()
    await panel.getByRole('button',{name:/^(Stima Elo della partita|Ricalcola stima Elo)$/}).click()
    for(let i=0;i<6;i++)await page.getByRole('button',{name:'Mossa precedente',exact:true}).click()
    await expect(panel.getByRole('button',{name:'Ricalcola stima Elo'})).toBeVisible({timeout:30000})
    await expect(page.getByRole('alert')).toHaveCount(0)
    const stats=await page.evaluate(()=>(window as any).maiaTest)
    expect(stats.maxActive).toBe(1)
    expect(stats.invalid).toBe(failure==='none'?0:1)
    expect(stats.workers).toBe(failure==='none'?1:2)
    const saved=(await(await request.get('/api/games/'+game.id)).json()).rating
    expect(saved.logScores.every((v:number)=>Number.isFinite(v))).toBe(true)
  })
}

test('Persistent invalid Maia output stops without saving partial scores and allows a later retry',async({page,request})=>{
  const imported=await(await request.post('/api/import',{data:{pgn,color:'b'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),imported.id)
  await mockWorker(page,'always')
  await page.goto('/')
  const panel=page.getByRole('region',{name:'Valutazione Elo della partita'})
  await page.getByRole('tab',{name:'Elo',exact:true}).click()
  await panel.getByRole('button',{name:'Stima Elo della partita'}).click()
  await expect(panel.getByRole('alert')).toContainText('anche dopo il riavvio')
  expect((await(await request.get('/api/games/'+imported.id)).json()).rating).toBeNull()
  await page.evaluate(()=>{(window as any).maiaTest.failure='none'})
  await panel.getByRole('button',{name:'Stima Elo della partita'}).click()
  await expect(panel.getByRole('button',{name:'Ricalcola stima Elo'})).toBeVisible({timeout:30000})
})
