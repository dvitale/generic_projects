import {test,expect,type Page} from '@playwright/test'
async function boardMove(page:Page,move:string){await page.locator(`[data-square="${move.slice(0,2)}"]`).click();await page.locator(`[data-square="${move.slice(2,4)}"]`).click()}
test('Real Maia play, black orientation, drill and mobile layout',async({page,request})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
  let humanResponseAt=0,maiaRequestAt=0
  page.on('response',response=>{if(response.url().endsWith('/moves')&&response.request().postDataJSON()?.actor==='human')humanResponseAt=Date.now()})
  page.on('request',request=>{if(request.url().endsWith('/moves')&&request.postDataJSON()?.actor==='maia')maiaRequestAt=Date.now()})
  await page.goto('/')
  await expect(page.locator('.piece-image,.piece')).toHaveCount(32)
  await expect.poll(()=>page.locator('.piece-image').evaluateAll(images=>images.every(img=>(img as HTMLImageElement).complete&&(img as HTMLImageElement).naturalWidth>0))).toBe(true)
  await page.screenshot({path:'test-results/green-neo.png',fullPage:true})
  await page.getByRole('button',{name:'Inizia partita'}).click()
  await expect(page.getByText('Tocca a te · trascina un pezzo o usa due clic')).toBeVisible()
  const humanResponse=page.waitForResponse(r=>r.url().endsWith('/moves')&&r.request().method()==='POST')
  await boardMove(page,'e2e4')
  await humanResponse
  await expect(page.getByText('Maia pronto',{exact:false})).toBeVisible({timeout:90000})
  await expect(page.getByText('Tocca a te · trascina un pezzo o usa due clic')).toBeVisible({timeout:60000})
  const id=await page.evaluate(()=>localStorage.getItem('chess-coach-game'))
  await expect.poll(async()=>(await (await request.get('/api/games/'+id)).json()).version).toBe(2)
  expect(maiaRequestAt-humanResponseAt).toBeGreaterThanOrEqual(1150)
  await page.locator('.coach-column select').selectOption('b')
  page.once('dialog',dialog=>dialog.dismiss())
  await page.getByRole('button',{name:'Nuova partita'}).click()
  expect(await page.evaluate(()=>localStorage.getItem('chess-coach-game'))).toBe(id)
  page.once('dialog',async dialog=>{
    expect(dialog.type()).toBe('confirm')
    expect(dialog.message()).toContain('resterà salvata')
    await dialog.accept()
  })
  const newResponse=page.waitForResponse(r=>r.url().endsWith('/api/games')&&r.request().method()==='POST')
  await page.getByRole('button',{name:'Nuova partita'}).click();await newResponse
  await expect(page.getByText('Tocca a te · trascina un pezzo o usa due clic')).toBeVisible({timeout:60000})
  const blackId=await page.evaluate(()=>localStorage.getItem('chess-coach-game'))
  const black=await(await request.get('/api/games/'+blackId)).json()
  expect(black.version).toBe(1);expect(black.playerColor).toBe('b')
  await page.getByRole('button',{name:'Drill',exact:true}).click()
  await page.getByLabel('Durata drill').selectOption('3')
  await page.getByRole('button',{name:'Avvia Partita italiana'}).click()
  for(let i=0;i<3;i++){
    await expect(page.getByText(/Maia 1500 · Tocca a te/)).toBeVisible({timeout:60000})
    const drillId=await page.evaluate(()=>localStorage.getItem('chess-coach-drill'))
    const g=await(await request.get('/api/games/'+drillId)).json()
    const response=page.waitForResponse(r=>r.url().endsWith('/moves')&&r.request().method()==='POST')
    await boardMove(page,g.legalMoves[0]);await response
  }
  await expect(page.getByText('Drill completato. Verifica le tue scelte prima di ripartire.')).toBeVisible()
  await page.screenshot({path:'test-results/drill-desktop.png',fullPage:true})
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/drill-mobile.png',fullPage:true})
  expect(errors).toEqual([])
})

test('Leaving play cancels the pending Maia move and returning resumes it',async({page,request})=>{
  await page.addInitScript(()=>{Math.random=()=>0.5})
  await page.goto('/')
  await page.getByRole('button',{name:'Inizia partita'}).click()
  await expect(page.getByText('Tocca a te · trascina un pezzo o usa due clic')).toBeVisible()
  const human=page.waitForResponse(r=>r.url().endsWith('/moves')&&r.request().postDataJSON()?.actor==='human')
  await boardMove(page,'e2e4');await human
  await expect(page.getByText('Maia sta pensando…',{exact:true})).toBeVisible()
  const id=await page.evaluate(()=>localStorage.getItem('chess-coach-game'))
  await page.getByRole('button',{name:'Progressi',exact:true}).click()
  await page.waitForTimeout(3500)
  expect((await(await request.get('/api/games/'+id)).json()).version).toBe(1)
  await page.getByRole('button',{name:'Gioca',exact:true}).click()
  await expect(page.getByText('Maia sta pensando…',{exact:true})).toBeVisible()
  await expect.poll(async()=>(await(await request.get('/api/games/'+id)).json()).version,{timeout:15000}).toBe(2)
})

test('PGN review creates personalized puzzles and tracks assistance',async({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:'↑ Importa PGN'}).click()
  await page.getByLabel('Partita PGN').fill('[White "Demo"]\n[Black "Opponent"]\n\n1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *')
  await page.getByRole('button',{name:'Importa partita',exact:true}).click()
  await page.getByRole('button',{name:/^(Analizza partita|Ricalcola analisi)$/}).click()
  await expect(page.getByText(/Revisione pronta/)).toBeVisible({timeout:60000})
  await page.getByRole('button',{name:/^Puzzle/}).click()
  await expect(page.getByRole('button',{name:'Chiedi un indizio'})).toBeVisible()
  await page.getByRole('button',{name:'Chiedi un indizio'}).click()
  await expect(page.locator('.hint')).toContainText('mosse candidate')
  await page.getByRole('button',{name:'Mostra soluzione'}).click()
  await expect(page.getByText(/Soluzione mostrata/)).toBeVisible({timeout:30000})
  await page.getByRole('button',{name:'Drill',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Riparti da una tua decisione'}).first()).toBeVisible()
})

test('Tutor is explicitly requested and renders a saved explanation',async({page})=>{
  let requests=0
  const review={provider:'DeepSeek',model:'test-double',createdAt:new Date().toISOString(),reflection:'',cached:false,
    evidence:[{ply:4,playedSan:'Qxe5+',bestSan:['Qf3'],theme:'Calcolo'}],
    coaching:{summary:'Una decisione da rivedere con attenzione.',observations:[{ply:4,explanation:'Confronta la tua scelta con la variante verificata.',hypothesis:'Forse non hai considerato la risposta avversaria.',question:'Quale risposta avevi previsto?'}],plan:[{title:'Pratica delle mosse candidate',minutes:5,description:'Confronta due opzioni.',exerciseId:null,drillId:'italiana'}]}}
  await page.route('**/api/tutor/status',r=>r.fulfill({json:{configured:true,model:'test-double'}}))
  await page.route('**/api/games/*/tutor',async r=>{
    if(r.request().method()==='POST'){requests++;expect(r.request().postDataJSON().reflection).toBe('Volevo attaccare il re.');await r.fulfill({json:review})}
    else await r.fulfill({json:null})
  })
  await page.goto('/')
  await page.getByRole('button',{name:'↑ Importa PGN'}).click()
  await page.getByLabel('Partita PGN').fill('1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *')
  await page.getByRole('button',{name:'Importa partita',exact:true}).click()
  await page.getByRole('button',{name:/^(Analizza partita|Ricalcola analisi)$/}).click()
  await expect(page.getByText(/Revisione pronta/)).toBeVisible({timeout:60000})
  expect(requests).toBe(0)
  await page.getByRole('tab',{name:'Tutor',exact:true}).click()
  await page.getByLabel('Il tuo ragionamento').fill('Volevo attaccare il re.')
  await page.getByRole('button',{name:'Chiedi al tutor DeepSeek'}).click()
  await expect(page.getByText('Una decisione da rivedere con attenzione.')).toBeVisible()
  expect(requests).toBe(1)
  await page.getByRole('button',{name:'Avvia il Drill',exact:true}).click()
  await expect(page.getByText('0 / 5 decisioni')).toBeVisible()
})
