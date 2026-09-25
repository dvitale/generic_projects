import {test,expect} from '@playwright/test'

test('Review compares every move before it is played and uses the selected Maia level',async({page,request})=>{
  await page.addInitScript(()=>{
    const NativeWorker=window.Worker
    ;(window as any).reviewInputs=[]
    window.Worker=class extends NativeWorker{
      postMessage(message:any,transfer:any){
        if(message.type==='inference')(window as any).reviewInputs.push({self:new Float32Array(message.eloSelfs)[0],opponent:new Float32Array(message.eloOppos)[0]})
        super.postMessage(message,transfer)
      }
    }
  })
  await page.goto('/')
  await page.getByRole('button',{name:'↑ Importa PGN'}).click()
  await page.getByLabel('Partita PGN').fill('1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *')
  await page.getByRole('button',{name:'Importa partita',exact:true}).click()
  const review=page.getByRole('region',{name:'Revisione passo passo'})
  await page.getByRole('button',{name:/^(Analizza partita|Ricalcola analisi)$/}).click()
  await expect(page.getByText(/Revisione pronta/)).toBeVisible({timeout:60000})
  const id=await page.evaluate(()=>localStorage.getItem('chess-coach-game'))
  const game=await(await request.get('/api/games/'+id)).json()
  const table=review.getByRole('table',{name:'Confronto delle mosse'})
  await expect(review.getByRole('combobox',{name:'Mossa da confrontare'})).toHaveValue('0')
  await expect(table.locator('tbody td').nth(0)).toContainText('e4')
  await expect(table.locator('tbody td').nth(1)).toContainText(game.analysis.moves[0].best.san[0])
  await expect(table.locator('tbody td').nth(2)).toContainText('%',{timeout:60000})
  await expect(page.locator('[data-square="e2"] img')).toBeVisible()
  await review.getByRole('button',{name:'Decisione successiva'}).click()
  await expect(review.getByRole('combobox',{name:'Mossa da confrontare'})).toHaveValue('1')
  await expect(table.locator('tbody td').nth(0)).toContainText('e5')
  await expect(review).toContainText('del Nero, che deve muovere')
  await expect(page.locator('[data-square="e4"] img')).toBeVisible()
  await review.getByRole('combobox',{name:'Livello Maia per l’analisi'}).selectOption('2100')
  await expect(table.getByRole('columnheader',{name:'Maia 2100'})).toBeVisible()
  await expect(table.locator('tbody td').nth(2)).toContainText('%',{timeout:60000})
  expect(await page.evaluate(()=>(window as any).reviewInputs.at(-1))).toEqual({self:2100,opponent:2100})
  await review.getByRole('combobox',{name:'Mossa da confrontare'}).selectOption('4')
  await expect(table.locator('tbody td').nth(0)).toContainText('Qxe5+')
  await review.getByText('Varianti verificate da Stockfish').click()
  await expect(review).toContainText('Dopo la mossa giocata:')
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await expect(page.getByRole('alert')).toHaveCount(0)
})
