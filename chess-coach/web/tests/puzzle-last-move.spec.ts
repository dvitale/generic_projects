import {test,expect} from '@playwright/test'

test.afterEach(async({page})=>{await page.unrouteAll({behavior:'ignoreErrors'})})

test('a puzzle highlights the opponent move that led to the position, also after a wrong try',async({page,request})=>{
  // Black has just played 1...Kh8; White's Qg8+ is the mistake the puzzle comes from.
  const pgn='[FEN "6k1/8/5KQ1/8/8/8/8/8 b - - 0 1"]\n[SetUp "1"]\n\n1... Kh8 2. Qg8+ *'
  const game=await(await request.post('/api/import',{data:{pgn,color:'w'}})).json()
  const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
  await page.route('**/api/exercises',async route=>{
    const exercises=await(await route.fetch()).json()
    await route.fulfill({json:exercises.filter((ex:{gameId:string})=>ex.gameId===game.id)})
  })
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  const feedback=page.getByRole('region',{name:'Esito del puzzle'})
  await expect(feedback).toContainText('Trova una buona mossa')
  await expect(page.locator('.last-square')).toHaveCount(2)
  await expect(page.locator('[data-square="g8"]')).toHaveClass(/last-square/)
  await expect(page.locator('[data-square="h8"]')).toHaveClass(/last-square/)
  // A wrong try shows its own move, then the board goes back and the opponent's move is highlighted again.
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g8"]').click()
  await expect(page.locator('[data-square="g6"]')).toHaveClass(/last-square/)
  await expect(feedback).toContainText('La scacchiera è tornata alla posizione iniziale',{timeout:30000})
  await expect(page.locator('[data-square="h8"]')).toHaveClass(/last-square/)
  await expect(page.locator('[data-square="g6"]')).not.toHaveClass(/last-square/)
})
