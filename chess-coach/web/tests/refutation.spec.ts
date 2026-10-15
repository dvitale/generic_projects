import {test,expect} from '@playwright/test'

test('A rejected puzzle move can be defended against Stockfish and the puzzle resumed',async({page,request})=>{
  const game=await(await request.post('/api/games',{data:{elo:600,fen:'7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}})).json()
  await request.post(`/api/games/${game.id}/moves`,{data:{move:'g6g8',version:0,revision:0,actor:'human'}})
  const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
  await page.route('**/api/exercises',async route=>{
    const exercises=await(await route.fetch()).json()
    await route.fulfill({json:exercises.filter((ex:{gameId:string})=>ex.gameId===game.id)})
  })
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  await page.locator('[data-square="g6"]').click()
  await page.locator('[data-square="g8"]').click()
  const mistakes=page.getByRole('region',{name:'Tentativi sbagliati'})
  await expect(mistakes).toContainText('Qg8+',{timeout:30000})
  await mistakes.getByRole('button',{name:'Gioca Qg8+ contro Stockfish'}).click()

  const panel=page.getByRole('region',{name:'Confutazione'})
  await expect(panel).toContainText('Difendi Qg8+ contro Stockfish')
  await expect(page.locator('.player-name',{hasText:'Stockfish'})).toBeVisible()
  // Stockfish punishes the queen sacrifice immediately.
  await expect.poll(async()=>{
    const id=await page.evaluate(()=>localStorage.getItem('chess-coach-game'))
    const next=await(await request.get('/api/games/'+id)).json()
    return [next.source,next.moves,next.title]
  },{timeout:30000}).toEqual(['stockfish',['g6g8','h8g8'],'Confutazione di 1. Qg8+'])
  await expect(page.locator('[data-square="g8"] img')).toBeVisible()

  await panel.getByRole('button',{name:'Torna al puzzle'}).click()
  await expect(page.getByRole('region',{name:'Esito del puzzle'})).toContainText('prova un’altra mossa')
  await expect(page.locator('[data-square="g6"] img')).toBeVisible()
})

test('The mistake explanation stays beside the board while the page scrolls and can be moved',async({page})=>{
  const fen='7k/8/5KQ1/8/8/8/8/8 w - - 0 1'
  const actual={pv:['g6g8','h8g8'],cp:-99999,mate:null,san:['Qg8+','Kxg8'],depth:18,nodes:1000,perspective:'w'}
  await page.route('**/api/prevention',route=>route.fulfill({json:{positions:[{id:'p',fen,turn:'w',legalMoves:['g6g7'],title:'Qg7',moveNumber:1}],stats:{firstAttempts:1,firstSuccesses:0},rule:{description:'Test'}}}))
  await page.route('**/api/prevention/p/sessions',route=>route.fulfill({json:{id:'s',version:1,exposure:'new'}}))
  await page.route('**/api/training/prevention/p/mistakes',route=>route.fulfill({json:[{id:1,fen,move:'g6g8',san:'Qg8+',createdAt:'2026-10-15T14:00:00Z',lossCp:null,reference:{cp:0,mate:1},actual}]}))
  await page.route('**/api/training/prevention/p/mistakes/1/explain',route=>route.fulfill({json:{cached:false,provider:'DeepSeek',explanation:{reason:'La donna è indifesa su g8.',continuation:'Il re la cattura.',lesson:'Controlla chi difende la casa d’arrivo.'}}}))
  await page.setViewportSize({width:1400,height:900})
  await page.goto('/');await page.getByRole('button',{name:'Blunder prevention',exact:false}).click();await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await expect(page.getByRole('button',{name:'Gioca Qg8+ contro Stockfish'})).toBeVisible()
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click()
  const panel=page.getByRole('dialog',{name:'Perché Qg8+ non va'})
  await expect(panel).toContainText('La donna è indifesa su g8.')
  const board=(await page.locator('.board-column').boundingBox())!,before=(await panel.boundingBox())!
  // Next to the board, not on top of it.
  expect(before.x).toBeGreaterThanOrEqual(board.x+board.width-1)
  await page.mouse.wheel(0,600)
  expect((await panel.boundingBox())!.y).toBe(before.y)
  const head=page.locator('.floating-head')
  const h=(await head.boundingBox())!
  await page.mouse.move(h.x+40,h.y+h.height/2);await page.mouse.down();await page.mouse.move(h.x-160,h.y+h.height/2-50,{steps:5});await page.mouse.up()
  const moved=(await panel.boundingBox())!
  expect(Math.round(moved.x)).toBe(Math.round(before.x-200));expect(Math.round(moved.y)).toBe(Math.round(before.y-50))
  await page.screenshot({path:'test-results/floating-explanation.png'})
  await page.keyboard.press('Escape');await expect(panel).toHaveCount(0)
  // The position is remembered for the next explanation.
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click()
  expect(Math.round((await panel.boundingBox())!.x)).toBe(Math.round(moved.x))
})
