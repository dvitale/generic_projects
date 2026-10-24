import {test,expect,type APIRequestContext} from '@playwright/test'

// playwright.config.ts starts tests/fixtures/fake_policy_service.py here and points the app at it.
const SERVICE='http://127.0.0.1:8012'
const control=(request:APIRequestContext,mode:string)=>request.post(SERVICE+'/control',{data:{mode}})

test.beforeEach(async({request})=>{await control(request,'ok')})

test('Play can start a game against the experimental engine, list it, then go back to Maia',async({page,request})=>{
  await page.goto('/')
  const setup=page.locator('.play-setup')
  await expect(setup.getByRole('group',{name:'Motore'})).toBeVisible()
  await expect(setup.getByRole('button',{name:'Maia',exact:true})).toHaveAttribute('aria-pressed','true')
  await setup.getByRole('button',{name:'Sperimentale',exact:true}).click()
  await expect(setup).toContainText('Servizio disponibile · fake-step1-000000000000')
  await expect(setup).toContainText('Livello Elo non ancora calibrato')
  await expect(setup.getByLabel('Livello Sperimentale')).toHaveAttribute('max','2500')
  await setup.getByRole('button',{name:'1100',exact:true}).click()
  await setup.getByRole('button',{name:'Nero',exact:true}).click()
  await setup.getByRole('button',{name:'Inizia partita →'}).click()
  // The engine moves first, from the server, and its name is on the opponent bar.
  await expect(page.locator('.player-name').filter({hasText:'Sperimentale'})).toBeVisible()
  await expect(page.getByText('Tocca a te',{exact:false})).toBeVisible({timeout:15000})
  const games=await(await request.get('/api/games')).json()
  const game=games[0]
  expect(game).toMatchObject({engine:'experimental',engineLabel:'Sperimentale',engineVersion:'fake-step1-000000000000',elo:1100,plies:1})
  const pgn=await(await request.get(`/api/games/${game.id}/pgn`)).text()
  expect(pgn).toContain('[OpponentEngine "experimental"]')
  expect(pgn).toContain('[MoveSelection "sample-full-distribution"]')

  // Back to Maia for the next game: the running game asks for confirmation and stays saved.
  await setup.getByRole('button',{name:'Maia',exact:true}).click()
  await expect(setup.getByLabel('Livello Maia')).toHaveAttribute('max','2600')
  await setup.getByRole('button',{name:'Bianco',exact:true}).click()
  page.once('dialog',dialog=>dialog.accept())
  await setup.getByRole('button',{name:'Nuova partita →'}).click()
  await expect(page.locator('.player-name').filter({hasText:'Maia'})).toBeVisible()
  const latest=(await(await request.get('/api/games')).json())[0]
  expect(latest).toMatchObject({engine:'maia',engineLabel:'Maia'})
  expect(latest.engineVersion).toMatch(/^maia3_simplified\.onnx@/)
  expect((await(await request.get('/api/games/'+game.id)).json()).moves).toHaveLength(1)
  await page.getByRole('button',{name:/^Partite/}).click()
  await expect(page.getByText('Contro Sperimentale (fake-step1-000000000000)')).toBeVisible()
  await expect(page.getByText('Contro Maia').first()).toBeVisible()
})

test('a failing experimental service stops the game with a message and a retry, never with Maia',async({page,request})=>{
  const game=await(await request.post('/api/games',{data:{color:'w',engine:'experimental',elo:1500}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  await control(request,'down')
  await page.locator('[data-square="e2"]').click();await page.locator('[data-square="e4"]').click()
  await expect(page.getByRole('alert')).toContainText('Errore del motore sperimentale',{timeout:15000})
  expect((await(await request.get('/api/games/'+game.id)).json()).moves).toEqual(['e2e4'])
  await control(request,'ok')
  await page.getByRole('alert').getByRole('button',{name:'Riprova'}).click()
  await expect.poll(async()=>(await(await request.get('/api/games/'+game.id)).json()).moves.length,{timeout:15000}).toBe(2)
  await expect(page.getByText('Tocca a te',{exact:false})).toBeVisible()
  // While the service is down a new experimental game cannot start; Maia stays available.
  await control(request,'down')
  const setup=page.locator('.play-setup')
  await setup.getByRole('button',{name:'Sperimentale',exact:true}).click()
  await setup.getByRole('button',{name:'Ricontrolla'}).click()
  await expect(setup).toContainText('Servizio non disponibile')
  await expect(setup.getByRole('button',{name:'Nuova partita →'})).toBeDisabled()
  await setup.getByRole('button',{name:'Maia',exact:true}).click()
  await expect(setup.getByRole('button',{name:'Nuova partita →'})).toBeEnabled()
})
