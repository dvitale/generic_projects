import {test,expect,type APIRequestContext} from '@playwright/test'

// After 1.e4 e5 2.Nf3 Nc6: 3.Nxe5? loses the knight to 3...Nxe5.
const FEN='r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3'

async function analysedGame(request:APIRequestContext){
  const game=await(await request.post('/api/games',{data:{fen:FEN,title:'Studio e2e'}})).json()
  await request.post(`/api/games/${game.id}/moves`,{data:{move:'f3e5',version:0,revision:0,actor:'human'}})
  const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:60000}).toBe('complete')
  return game.id as string
}

test('A game pack leads to a lesson card, the recall quiz and the position tutor',async({page,request})=>{
  const id=await analysedGame(request)
  await page.goto('/?section=study')
  await expect(page.getByRole('heading',{name:'Studio',level:1})).toBeVisible()
  await page.getByRole('tab',{name:'Impara da una partita'}).click()
  await page.getByRole('combobox',{name:'Partita'}).selectOption(id)
  const moment=page.getByRole('region',{name:'Momento selezionato'})
  await expect(moment).toContainText('Nxe5')
  await expect(moment.getByRole('button',{name:'Puzzle',exact:true})).toBeEnabled()
  await page.screenshot({path:'test-results/study-pack.png'})
  await moment.getByLabel('La mia lezione').fill('Prima di catturare conto chi difende la casa d’arrivo.')
  await moment.getByRole('button',{name:'Crea flashcard'}).click()
  await expect(moment.getByRole('status')).toContainText('Scheda creata')

  await page.getByRole('button',{name:/Quiz della partita/}).click()
  const question=page.getByRole('region',{name:'Domanda del quiz'})
  await expect(question).toContainText('Domanda 1',{timeout:60000})
  await question.locator('.quiz-option').first().click()
  await expect(question.getByRole('status')).toContainText(/Esatto|Non proprio/)
  await question.getByRole('button',{name:'Prossima domanda →'}).click()
  await expect(question).toContainText('Dopo 3. Nxe5, qual era la risposta più forte dell’avversario?')
  await question.getByRole('button',{name:'Nxe5',exact:true}).click()
  await expect(question.getByRole('status')).toContainText('✓ Esatto')
  await page.screenshot({path:'test-results/study-quiz.png'})

  await page.getByRole('tab',{name:'Impara da una partita'}).click()
  await page.getByRole('region',{name:'Momento selezionato'}).getByRole('button',{name:'Chiedi al tutor'}).click()
  await expect(page.getByLabel('La tua domanda')).toHaveValue('Perché Nxe5 è un errore?')
  await page.getByRole('button',{name:'Chiedi',exact:true}).click()
  const reply=page.getByRole('region',{name:'Risposta 1'})
  await expect(reply).toContainText('Nxe5 peggiora la posizione',{timeout:60000})
  await expect(reply).toContainText('Varianti verificate da Stockfish')
  await page.screenshot({path:'test-results/study-tutor.png'})

  await page.getByRole('tab',{name:'Flashcard'}).click()
  const card=page.getByRole('region',{name:'Scheda'})
  // Lessons from other explained attempts may be due first: rate them until this one shows.
  for(let i=0;i<10&&!(await card.textContent())?.includes('Avevi scelto Nxe5');i++){
    await card.getByRole('button',{name:/Mostra risposta/}).click();await card.getByRole('button',{name:/^Bene/}).click()
    await expect(page.getByText(`${i+1} ripassate in questa sessione`)).toBeVisible()
  }
  await expect(card).toContainText('Avevi scelto Nxe5')
  await card.getByRole('button',{name:/Mostra risposta/}).click()
  await expect(card).toContainText('Prima di catturare conto chi difende')
  await page.screenshot({path:'test-results/study-flashcard.png'})
  await card.getByRole('button',{name:/^Bene/}).click()
  await expect(page.getByText('Prima di catturare conto chi difende')).toHaveCount(0)
  const cards=await(await request.get('/api/study/cards')).json()
  expect(cards.due.some((c:{lesson:string})=>c.lesson.startsWith('Prima di catturare'))).toBe(false)

  await page.getByRole('tab',{name:'Quaderno'}).click()
  const notebook=await(await request.get('/api/study/notebook')).json()
  const theme=notebook.themes.find((t:{examples:{gameId:string}[]})=>t.examples.some(e=>e.gameId===id))
  const section=page.locator('.notebook-theme',{has:page.getByRole('heading',{name:theme.theme,exact:true})})
  if(!await section.evaluate(node=>(node as HTMLDetailsElement).open))await section.locator('summary').click()
  await expect(section.locator('.notebook-example',{hasText:'Nxe5'}).first()).toBeVisible()
  await expect(section).toContainText('Prima di catturare conto chi difende')
  await expect(page.getByRole('link',{name:/Esporta PGN annotato/})).toHaveAttribute('href','/api/study/notebook.pgn')
})

test('The mock exam gives no feedback until it is handed in',async({page})=>{
  const fen='7k/8/5KQ1/8/8/8/8/8 w - - 0 1'
  const item={fen,turn:'w',legalMoves:['g6g7','g6g8','g6h6'],answered:false}
  const exam={id:'e',createdAt:new Date().toISOString(),deadline:new Date(Date.now()+600000).toISOString(),finishedAt:null,size:2,answered:0,items:[{...item,index:0},{...item,index:1}]}
  const answers:unknown[]=[]
  await page.route('**/api/study/exams',route=>route.request().method()==='POST'?route.fulfill({json:exam}):route.fulfill({json:{history:[],active:null,nextRecommended:null,cadenceDays:14}}))
  await page.route('**/api/study/exams/e/answers',route=>{answers.push(route.request().postDataJSON());route.fulfill({json:{recorded:true,answered:answers.length}})})
  await page.route('**/api/study/exams/e/finish',route=>route.fulfill({json:{...exam,finishedAt:new Date().toISOString(),answered:2,score:1,
    themes:[{theme:'Riconoscere il matto',total:2,solved:1}],
    items:exam.items.map((i,n)=>({...i,answered:true,exerciseId:'x'+n,gameId:'g',ply:0,theme:'Riconoscere il matto',success:n===0,move:n===0?'g6g7':'g6g8',san:n===0?'Qg7#':'Qg8+',lossCp:n===0?0:99999,best:{cp:100000,mate:1,pv:['g6g7'],san:['Qg7#'],depth:1,nodes:1,perspective:'w'}}))}}))
  await page.goto('/?section=study')
  await page.getByRole('tab',{name:'Esame di prova'}).click()
  await page.getByRole('button',{name:'Inizia l’esame →'}).click()
  const status=page.getByRole('region',{name:'Esame in corso'})
  await expect(status).toContainText('Posizione 1 di 2')
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g7"]').click()
  await expect(status).toContainText('Posizione 2 di 2')
  await expect(page.getByText(/Esatto|✓/)).toHaveCount(0)
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g8"]').click()
  await expect(page.getByRole('heading',{name:'1 posizioni risolte su 2'})).toBeVisible()
  expect(answers).toEqual([{item:0,move:'g6g7'},{item:1,move:'g6g8'}])
  await page.getByRole('button',{name:/✗ 2\. Riconoscere il matto/}).click()
  await expect(page.getByRole('button',{name:'Apri come puzzle'})).toBeVisible()
})
