import {test,expect} from '@playwright/test'

test('finishing a game starts analysis without leaving play or requesting it twice',async({page,request})=>{
  const game=await(await request.post('/api/games',{data:{fen:'7k/8/5KQ1/8/8/8/8/8 w - - 0 1',color:'w'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  let manualRequests=0
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/analysis'))manualRequests++})
  await page.goto('/')
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g7"]').click()
  await expect(page.getByText('Partita conclusa · 1-0')).toBeVisible()
  await expect.poll(async()=>(await(await request.get('/api/games/'+game.id)).json()).analysis?.version).toBe(1)
  await expect(page.getByRole('button',{name:'Gioca',exact:true})).toHaveAttribute('aria-current','page')
  expect(manualRequests).toBe(0)
  await page.reload()
  await expect(page.getByRole('button',{name:'Ricalcola analisi',exact:true})).toBeVisible()
  expect(manualRequests).toBe(0)
})

test('puzzle and prevention identify the originating game and open the exact decision',async({page,request})=>{
  const fen='r6k/8/5KQ1/8/8/8/8/8 w - - 0 17'
  const game=await(await request.post('/api/games',{data:{fen,color:'w'}})).json()
  await request.post(`/api/games/${game.id}/moves`,{data:{move:'g6g8',version:0,actor:'human'}})
  const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status).toBe('complete')
  // Limit the exercise catalog to this fixture.
  await page.route('**/api/exercises',async r=>{const response=await r.fetch();await r.fulfill({json:(await response.json()).filter((e:any)=>e.gameId===game.id)})})
  await page.route('**/api/prevention',async r=>{const response=await r.fetch();const data=await response.json();data.positions=data.positions.filter((p:any)=>p.gameId===game.id);await r.fulfill({json:data})})
  await page.goto('/')
  for(const mode of ['Puzzle','Blunder prevention']){
    await page.getByRole('button',{name:mode==='Puzzle'?/^Puzzle/:mode,exact:mode!=='Puzzle'}).click()
    if(mode!=='Puzzle')await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
    const source=page.getByRole('region',{name:'Partita di origine'})
    await expect(source).toContainText(game.title)
    await expect(source).toContainText('Mossa 17. · Bianco')
    await source.getByRole('button',{name:'Rivedi questa mossa nella partita'}).click()
    await expect(page.getByRole('button',{name:'Rivedi',exact:true})).toHaveAttribute('aria-current','page')
    await expect(page.getByLabel('Mossa da confrontare')).toHaveValue('0')
    await expect(page.locator('[data-square="g6"] img')).toBeVisible()
    expect(await page.evaluate(()=>localStorage.getItem('chess-coach-game'))).toBe(game.id)
  }
})
