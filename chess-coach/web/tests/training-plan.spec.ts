import {test,expect} from '@playwright/test'

test('Maia PGN files import once, generate exercises, and a successful review persists in the plan',async({page,request})=>{
  const baseline=(await(await request.get('/api/training-plan')).json()).completed
  const pgn=(id:string)=>`[ID "${id}"]\n[Site "https://maiachess.com/"]\n[White "TrainingTest"]\n[Black "Maia 600"]\n[SetUp "1"]\n[FEN "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"]\n[Result "*"]\n\n1. Qg8+ *`
  await page.goto('/')
  await page.getByRole('button',{name:/Importa PGN/}).click()
  await page.getByLabel('File PGN',{exact:true}).setInputFiles([
    {name:'maia-a.pgn',mimeType:'text/plain',buffer:Buffer.from(pgn('schedule-test-a'))},
    {name:'maia-b.pgn',mimeType:'text/plain',buffer:Buffer.from(pgn('schedule-test-b'))},
  ])
  await page.getByRole('button',{name:'Importa partite',exact:true}).click()
  await expect(page.getByRole('region',{name:'Importazione partite'})).toContainText('2 importate')
  await expect(page.getByText(/Esercizi pronti/)).toHaveCount(2,{timeout:60000})
  await page.getByRole('button',{name:'Importa partite',exact:true}).click()
  await expect(page.getByRole('region',{name:'Importazione partite'})).toContainText('2 già presenti')
  await page.getByRole('button',{name:/Importa PGN/}).click()
  await page.getByRole('button',{name:'Allenamento',exact:true}).click()
  await page.getByLabel('Minuti per sessione').fill('60')
  await page.getByLabel('Posizioni nuove al giorno').fill('10')
  await page.getByRole('button',{name:'Salva piano'}).click()
  await expect(page.getByRole('button',{name:'Salva piano'})).toBeEnabled()
  await page.locator('.exercise-list button').filter({hasText:'TrainingTest'}).first().click()
  await expect(page.getByRole('region',{name:'Esito del puzzle'})).toContainText('Trova una buona mossa')
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g7"]').click()
  await expect(page.getByRole('region',{name:'Esito del puzzle'})).toContainText('tolto dai puzzle da ripassare')
  await page.getByRole('button',{name:'Allenamento',exact:true}).click()
  await expect(page.getByText(`${baseline+1} / 30 verifiche oggi`,{exact:false})).toBeVisible()
  await expect(page.getByText(/Prossimo richiamo:/)).toBeVisible()
  await page.reload();await page.getByRole('button',{name:'Allenamento',exact:true}).click()
  await expect(page.getByLabel('Minuti per sessione')).toHaveValue('60')
  await expect(page.getByText(`${baseline+1} / 30 verifiche oggi`,{exact:false})).toBeVisible()
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/training-plan-mobile.png',fullPage:true})
})
