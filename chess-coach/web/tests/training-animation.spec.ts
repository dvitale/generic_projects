import {test,expect} from '@playwright/test'

const cases=[
  {name:'capture',fen:'6rk/8/5KQ1/8/8/8/8/8 w - - 0 1',move:'g6g8',piece:'donna bianco',restored:'g8'},
  {name:'castling',fen:'4k3/8/8/8/8/8/8/4K2R w K - 0 1',move:'e1g1',piece:'re bianco',rook:true},
  {name:'en passant',fen:'7k/8/8/3pP3/8/8/8/K7 w - d6 0 1',move:'e5d6',piece:'pedone bianco',restored:'d5'},
  {name:'promotion capture',fen:'k6r/6P1/8/8/8/8/8/K7 w - - 0 1',move:'g7h8q',piece:'pedone bianco',restored:'h8'},
  {name:'black capture',fen:'8/8/8/8/8/5kq1/8/6RK b - - 0 1',move:'g3g1',piece:'donna nero',restored:'g1'},
]
for(const c of cases)test(`wrong ${c.name} is visible before a slow, complete undo`,async({page})=>{
  const p={id:'animation',gameId:'none',title:'Test animazione',ply:0,fen:c.fen,turn:c.name==='black capture'?'b':'w',moveNumber:1,legalMoves:[c.move,...(c.move.endsWith('q')?[c.move.slice(0,4)+'n']:[])],dueAt:'2026-01-01',streak:0}
  await page.route('**/api/prevention',route=>route.fulfill({json:{positions:[p],stats:{firstAttempts:0,firstSuccesses:0},analyzedGames:1,rule:{description:'Test'}}}))
  await page.route('**/api/prevention/animation/sessions',route=>route.fulfill({json:{id:'s',version:0,exposure:'new'}}))
  let calls=0
  await page.route('**/api/prevention/animation/attempts',async route=>{
    calls++;await new Promise(resolve=>setTimeout(resolve,400))
    await route.fulfill({json:{success:false,closed:false,version:1,move:c.move,san:'Test',actual:{cp:-300,mate:null,pv:[c.move],san:['Test']},message:'Errore di prova'}})
  })
  await page.goto('/');await page.getByRole('button',{name:'Blunder prevention',exact:false}).click()
  await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await expect(page.getByRole('heading',{name:'Evita il blunder',exact:true})).toBeVisible()
  const from=c.move.slice(0,2),to=c.move.slice(2,4)
  await page.locator(`[data-square="${from}"]`).click();await page.locator(`[data-square="${to}"]`).click()
  if(c.move.endsWith('q'))await page.getByRole('dialog',{name:'Scegli la promozione'}).getByRole('button',{name:'donna',exact:true}).click()
  await expect(page.locator(`[data-square="${from}"] img`)).toHaveCount(0)
  await expect(page.locator(`[data-square="${to}"] img`)).toBeVisible()
  if(c.rook)await expect(page.locator('[data-square="f1"] img')).toBeVisible()
  await expect(page.getByText('Osserva la mossa:',{exact:false})).toBeVisible()
  await page.locator(`[data-square="${from}"]`).click();await page.locator(`[data-square="${to}"]`).click()
  await expect(page.getByText('Ritorno alla posizione iniziale…',{exact:true})).toBeVisible()
  expect(await page.evaluate(()=>document.getAnimations().some(a=>a.effect?.getTiming().duration===650))).toBe(true)
  await expect(page.getByRole('heading',{name:'↻ Riprova una mossa diversa'})).toBeVisible()
  await expect(page.locator(`[data-square="${from}"]`)).toHaveAttribute('aria-label',`${from} ${c.piece}`)
  if(c.restored)await expect(page.locator(`[data-square="${c.restored}"] img`)).toBeVisible()
  if(c.rook){await expect(page.locator('[data-square="h1"] img')).toBeVisible();await expect(page.locator('[data-square="f1"] img')).toHaveCount(0)}
  expect(calls).toBe(1)
})

test('an explanation can be opened, hidden and reopened without another provider request',async({page})=>{
  await page.route('**/api/prevention',route=>route.fulfill({json:{positions:[{id:'explain',fen:'r6k/8/5KQ1/8/8/8/8/8 w - - 0 1',turn:'w',legalMoves:['g6g7'],title:'Posizione',moveNumber:1}],stats:{firstAttempts:1,firstSuccesses:0},rule:{description:'Test'}}}))
  await page.route('**/api/prevention/explain/sessions',route=>route.fulfill({json:{id:'session',version:1,exposure:'new'}}))
  await page.route('**/api/training/prevention/explain/mistakes',route=>route.fulfill({json:[{id:1,san:'Qg8+',createdAt:'2026-09-30T10:00:00Z',lossCp:400,reference:{cp:80,mate:null},actual:{cp:-320,mate:null,san:['Qg8+','Kxg8']}}]}))
  let calls=0
  await page.route('**/api/training/prevention/explain/mistakes/1/explain',route=>{calls++;return route.fulfill({json:{explanation:{reason:'La donna rimane in presa.',continuation:'Il re può catturarla.',lesson:'Controlla le catture avversarie.'},provider:'DeepSeek',cached:false}})})
  await page.goto('/');await page.getByRole('button',{name:'Blunder prevention',exact:false}).click();await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await expect(page.getByText('Perdita 4.00 pedoni')).toBeVisible();expect(calls).toBe(0)
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click();await expect(page.getByText('La donna rimane in presa.')).toBeVisible()
  await page.getByRole('button',{name:'Nascondi spiegazione'}).click();await expect(page.getByText('La donna rimane in presa.')).toHaveCount(0)
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click();await expect(page.getByText('La donna rimane in presa.')).toBeVisible();expect(calls).toBe(1)
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})
