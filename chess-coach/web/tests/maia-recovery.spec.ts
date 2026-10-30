import {test,expect,type Page} from '@playwright/test'

const pgn='1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. Nbd2 Bb7 12. Bc2 h6 *'

/** Counts the predict requests and, when asked, makes the server fail. */
async function watchMaia(page:Page,failure:'none'|'always'){
  const state={requests:0,positions:0,failure}
  await page.route('**/api/maia/predict',async route=>{
    state.requests++;state.positions+=route.request().postDataJSON().positions.length
    if(state.failure==='always')return route.fulfill({status:503,json:{detail:'Maia sul server non è disponibile.'}})
    return route.continue()
  })
  return state
}

async function openRating(page:Page,id:string){
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),id)
  await page.goto('/')
  await page.getByRole('tab',{name:'Decisioni',exact:true}).click()
  await page.getByText('Somiglianza con Maia · facoltativa',{exact:true}).click()
  return page.getByRole('region',{name:'Somiglianza con Maia'})
}

test('The rating asks every Maia level of a position in one server request',async({page,request})=>{
  const game=await(await request.post('/api/import',{data:{pgn}})).json()
  const state=await watchMaia(page,'none')
  const panel=await openRating(page,game.id)
  const before=state.requests
  await panel.getByRole('button',{name:/^(Confronta con i profili Maia|Ricalcola somiglianza)$/}).click()
  await expect(panel.getByRole('button',{name:'Ricalcola somiglianza'})).toBeVisible({timeout:60000})
  const plan=await(await request.get(`/api/games/${game.id}/rating-positions`)).json()
  // One request per decision, not one per decision and level.
  expect(state.requests-before).toBeLessThanOrEqual(plan.positions.length+2)
  expect(state.positions).toBeGreaterThanOrEqual(plan.positions.length*plan.levels.length)
  const saved=(await(await request.get('/api/games/'+game.id)).json()).rating
  expect(saved.logScores.every((v:number)=>Number.isFinite(v))).toBe(true)
})

test('A Maia server failure stops the rating without saving partial scores and allows a later retry',async({page,request})=>{
  const imported=await(await request.post('/api/import',{data:{pgn,color:'b'}})).json()
  const state=await watchMaia(page,'always')
  const panel=await openRating(page,imported.id)
  await panel.getByRole('button',{name:'Confronta con i profili Maia'}).click()
  await expect(panel.getByRole('alert')).toContainText('Maia sul server non è disponibile')
  expect((await(await request.get('/api/games/'+imported.id)).json()).rating).toBeNull()
  state.failure='none'
  await panel.getByRole('button',{name:'Confronta con i profili Maia'}).click()
  await expect(panel.getByRole('button',{name:'Ricalcola somiglianza'})).toBeVisible({timeout:60000})
})
