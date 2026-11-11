import {test,expect,type Page} from '@playwright/test'

async function boardMove(page:Page,move:string){
  const response=page.waitForResponse(r=>r.url().endsWith('/move')&&r.request().method()==='POST')
  await page.locator(`[data-square="${move.slice(0,2)}"]`).click();await page.locator(`[data-square="${move.slice(2,4)}"]`).click()
  return response
}

test('Line review rejects a move out of book, shows the theory and ends with the line and the next review',async({page})=>{
  await page.addInitScript(()=>{localStorage.removeItem('chess-coach-line');localStorage.setItem('chess-coach-lines:italiana:w',JSON.stringify(['italiana:hungarian']))})
  await page.goto('/?section=drill')
  await expect(page.getByRole('heading',{name:'Partita italiana',level:3})).toBeVisible()
  await page.getByText('Linee del ripasso (1/10)').click()
  await expect(page.getByRole('checkbox',{name:'Hungarian Defense'})).toBeChecked()
  await page.getByRole('button',{name:'Ripassa Partita italiana'}).click()
  await expect(page.getByRole('heading',{name:'RIPASSO DELLA LINEA'}).or(page.getByText('Tocca a te: gioca la mossa di teoria'))).toBeVisible()
  await boardMove(page,'d2d4')
  await expect(page.getByText('✗ d4 non è la teoria.')).toBeVisible()
  await expect(page.getByText('Qui si gioca e4',{exact:false})).toBeVisible()
  await expect(page.locator('[data-square="d2"] img')).toBeVisible()
  await boardMove(page,'e2e4')
  await expect(page.getByLabel('Mosse giocate')).toHaveText('1. e4 e5')
  await expect(page.locator('[data-square="e5"] img')).toBeVisible()
  await expect(page.getByText('Tocca a te: gioca la mossa di teoria')).toBeVisible()
  await page.getByRole('button',{name:'Mostra la mossa di teoria'}).click()
  await expect(page.getByText('La teoria qui:',{exact:false})).toContainText('Nf3')
  await boardMove(page,'g1f3')
  await expect(page.locator('[data-square="c6"] img')).toBeVisible()
  await expect(page.getByLabel('Mosse giocate')).toHaveText('1. e4 e5 2. Nf3 Nc6')
  await boardMove(page,'f1c4')
  await expect(page.getByRole('heading',{name:'Linea completata, con aiuti: Hungarian Defense'})).toBeVisible()
  await expect(page.locator('.line-errors')).toContainText('1. hai giocato d4; la teoria è e4')
  await expect(page.getByText('Prossimo ripasso:',{exact:false})).toBeVisible()
  // The opponent's last book move appears after the player's own.
  await expect(page.locator('[data-square="e7"] img')).toBeVisible()
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/line-review-mobile.png',fullPage:true})
  await page.setViewportSize({width:1280,height:900})
  // The end of the line continues against Maia as a drill.
  await page.getByRole('button',{name:'Continua contro Maia da qui →'}).click()
  await expect(page.getByText('Partita italiana: Hungarian Defense',{exact:true})).toBeVisible()
  await expect(page.getByText(/Maia 1500 · Tocca a te/)).toBeVisible({timeout:60000})
})

test('Each opening family starts a drill against Maia from the end of the chosen line',async({page})=>{
  await page.goto('/?section=drill')
  await page.getByLabel('Linea di Difesa russa (Petroff)').selectOption('russa:damiano-qe2')
  await page.getByRole('button',{name:'Avvia Difesa russa (Petroff) contro Maia'}).click()
  await expect(page.getByText('Difesa russa (Petroff): Damiano Variation, 4.Qe2',{exact:true})).toBeVisible()
  await expect(page.locator('[data-square="e4"] img')).toBeVisible()
  await page.screenshot({path:'test-results/opening-drill.png',fullPage:true})
})
