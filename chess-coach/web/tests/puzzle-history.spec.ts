import {test,expect} from '@playwright/test'

test.beforeEach(async({page})=>{
  await page.route('**/api/maia/predict',route=>{
    const positions=route.request().postDataJSON().positions
    return route.fulfill({json:{predictions:positions.map(()=>({moves:[{uci:'g6g7',san:'Qg7#',probability:.9}],whiteExpectedScore:.9,whiteOutcome:{win:.9,draw:0,loss:.1}}))}})
  })
})
test.afterEach(async({page})=>{await page.unrouteAll({behavior:'ignoreErrors'})})

test('a wrong move played again in a later session is named in the puzzle and listed in Progressi',async({page,request})=>{
  const pgn='[FEN "6k1/8/5KQ1/8/8/8/6P1/8 b - - 0 1"]\n[SetUp "1"]\n\n1... Kh8 2. Qg8+ *'
  const game=await(await request.post('/api/import',{data:{pgn,color:'w'}})).json()
  const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
  const exercise=(await(await request.get('/api/exercises')).json()).find((ex:{gameId:string})=>ex.gameId===game.id)
  // An earlier session: the same wrong move, then the solution.
  const earlier=await(await request.post(`/api/exercises/${exercise.id}/sessions`,{data:{}})).json()
  await request.post(`/api/exercises/${exercise.id}/attempts`,{data:{session_id:earlier.id,move:'g6g8',version:0}})
  await request.post(`/api/exercises/${exercise.id}/reveal`,{data:{session_id:earlier.id}})
  await page.route('**/api/exercises',async route=>{
    const exercises=await(await route.fetch()).json()
    await route.fulfill({json:exercises.filter((ex:{gameId:string})=>ex.gameId===game.id)})
  })
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  const feedback=page.getByRole('region',{name:'Esito del puzzle'})
  await expect(feedback).toContainText('Trova una buona mossa')
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g8"]').click()
  const note=feedback.locator('.puzzle-repeated')
  await expect(note).toContainText('Avevi giocato Qg8+ in questa posizione anche il',{timeout:30000})
  await note.getByText('Mostra la risposta che la confuta').click()
  await expect(note.locator('.variation')).toContainText('Qg8+ Kxg8')
  await page.getByRole('button',{name:'Progressi',exact:true}).click()
  const gaps=page.getByRole('region',{name:'Lacune ricorrenti'})
  await expect(gaps.locator('.repeated-errors')).toContainText('Qg8+ in 2 sessioni')
  await expect(gaps.locator('.repeated-errors')).toContainText('ancora presente')
  await gaps.getByRole('button',{name:'Apri il puzzle'}).click()
  await expect(page.getByRole('region',{name:'Esito del puzzle'})).toBeVisible()
})

test('Progressi says after which hint the next guess was still wrong',async({page,request})=>{
  const pgn='[FEN "6k1/8/5KQ1/8/8/8/6P1/8 b - - 0 1"]\n[SetUp "1"]\n\n1... Kh8 2. Qg8+ *'
  const game=await(await request.post('/api/import',{data:{pgn,color:'w'}})).json()
  const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
  const exercise=(await(await request.get('/api/exercises')).json()).find((ex:{gameId:string})=>ex.gameId===game.id)
  const s=await(await request.post(`/api/exercises/${exercise.id}/sessions`,{data:{}})).json()
  await request.post(`/api/exercises/${exercise.id}/hint`,{data:{session_id:s.id}})
  // The first test may have left a session open on the same position: its version counts the guesses already made.
  await request.post(`/api/exercises/${exercise.id}/attempts`,{data:{session_id:s.id,move:'g6g8',version:s.version}})
  await page.goto('/')
  await page.getByRole('button',{name:'Progressi',exact:true}).click()
  const outcomes=page.locator('.hint-outcomes')
  await expect(outcomes).toContainText('Dopo «Tipo di mossa»')
  await expect(outcomes).toContainText('Ancora sbagliato 1')
})
