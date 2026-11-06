import {test,expect} from '@playwright/test'

test.afterEach(async({page})=>{await page.unrouteAll({behavior:'ignoreErrors'})})

test('due puzzles can be filtered by phase and theme',async({page,request})=>{
  // An opening mistake with Black (3...Nf6?? allows Qxf7#) and an endgame one with White (Qb8+? Kxb8).
  const games:string[]=[]
  for(const [pgn,color] of [['1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0','b'],
                            ['[FEN "1k6/8/1QK5/1P6/8/8/8/8 b - - 0 1"]\n[SetUp "1"]\n\n1... Ka8 2. Qb8+ *','w']]){
    const game=await(await request.post('/api/import',{data:{pgn,color}})).json()
    const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
    await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
    games.push(game.id)
  }
  await page.route('**/api/exercises',async route=>{
    const exercises=await(await route.fetch()).json()
    await route.fulfill({json:exercises.filter((ex:{gameId:string})=>games.includes(ex.gameId))})
  })
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  const list=page.locator('.exercise-list .exercise-link')
  await expect(list).toHaveCount(2)
  await expect(list.filter({hasText:'Apertura · Mossa 3'})).toHaveCount(1)
  await page.getByLabel('Fase del puzzle').selectOption('endgame')
  await expect(list).toHaveCount(1)
  await expect(list.first()).toContainText('Finale · Mossa 2')
  await expect(page.locator('.count-chip').first()).toHaveText('1 di 2')
  await page.getByLabel('Fase del puzzle').selectOption('middlegame')
  await expect(page.getByText('Nessun puzzle da ripassare con questi filtri.')).toBeVisible()
  await page.getByLabel('Fase del puzzle').selectOption('')
  const theme=(await list.first().locator('span').textContent())!
  await page.getByLabel('Tema del puzzle').selectOption(theme)
  await expect(list.locator('span').filter({hasNotText:theme})).toHaveCount(0)
})
