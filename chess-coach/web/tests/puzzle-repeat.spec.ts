import {test,expect} from '@playwright/test'

test.afterEach(async({page})=>{await page.unrouteAll({behavior:'ignoreErrors'})})

test('the same mistake in two games is one puzzle that says it was repeated',async({page,request})=>{
  // The same position reached by different move orders, with the same 2.Qb8+? mistake.
  const pgns=['[FEN "1k6/8/1QK5/8/8/8/8/8 b - - 0 1"]\n[SetUp "1"]\n\n1... Ka8 2. Qb8+ *',
              '[FEN "8/k7/1QK5/8/8/8/8/8 b - - 0 1"]\n[SetUp "1"]\n\n1... Ka8 2. Qb8+ *']
  const games:string[]=[]
  for(const pgn of pgns){
    const game=await(await request.post('/api/import',{data:{pgn,color:'w'}})).json()
    const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
    await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
    games.push(game.id)
  }
  const mine=(await(await request.get('/api/exercises')).json()).filter((ex:{gameId:string})=>games.includes(ex.gameId))
  expect(mine).toHaveLength(1)
  await page.route('**/api/exercises',async route=>{
    const exercises=await(await route.fetch()).json()
    await route.fulfill({json:exercises.filter((ex:{gameId:string})=>games.includes(ex.gameId))})
  })
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  await expect(page.locator('.puzzle-panel .puzzle-repeat')).toHaveText('↻ Errore ripetuto in 2 partite')
})
