import {test,expect} from '@playwright/test'

const square=(page:import('@playwright/test').Page,name:string)=>page.locator(`[data-square="${name}"]`)

test('Problems from real games: rating bands, solving, mistakes and the Maia estimate',async({page})=>{
  await page.goto('/?section=problems')
  await expect(page.getByRole('heading',{name:'Problemi da partite reali'})).toBeVisible()
  await expect(page.getByText('il tuo rating problemi')).toBeVisible()
  await page.getByRole('button',{name:'Fino a 800'}).click()
  await page.getByRole('button',{name:'Inizia →'}).click()
  // 007mr: White plays Rxe4, Black mates on the back rank with Rd1+ Rxd1 Rxd1#.
  await expect(page.getByRole('heading',{name:'Tocca a te'})).toBeVisible()
  await expect(square(page,'e4')).toHaveAttribute('aria-label',/torre bianco/)
  await expect(page.getByText('Trova la sequenza vincente · 2 mosse')).toBeVisible()
  await square(page,'d5').click();await square(page,'d1').click()
  await expect(square(page,'d1')).toHaveAttribute('aria-label',/torre bianco/)
  await square(page,'d7').click();await square(page,'d1').click()
  await expect(page.getByRole('heading',{name:'✓ Problema risolto!'})).toBeVisible()
  await expect(page.getByText(/Rating 1200 → 12\d\d \(\+\d+\)/)).toBeVisible()
  await expect(page.getByRole('heading',{name:/^Rating 646/})).toBeVisible()
  await expect(page.locator('.chip',{hasText:'Matto sulla traversa'})).toBeVisible()
  await expect(page.locator('.maia-estimate .bar-list li')).toHaveCount(6,{timeout:90000})
  await page.screenshot({path:'test-results/problems-solved.png'})

  // A wrong first move is rated at once, the board goes back and the problem can still be finished.
  await page.getByRole('button',{name:'Cambia fascia'}).click()
  await page.getByRole('button',{name:'800–1000'}).click()
  await page.getByRole('button',{name:'Inizia →'}).click()
  await expect(page.getByRole('heading',{name:'Tocca a te'})).toBeVisible()
  await square(page,'a8').click();await square(page,'b8').click()
  await expect(page.getByRole('heading',{name:'✗ Non è la mossa giusta'})).toBeVisible()
  await expect(page.getByRole('heading',{name:'↻ Riprova'})).toBeVisible()
  await expect(square(page,'a8')).toHaveAttribute('aria-label',/torre nero/)
  await page.getByRole('button',{name:'Mostra soluzione'}).click()
  await expect(page.getByRole('heading',{name:'Soluzione completa'})).toBeVisible({timeout:10000})
  await expect(page.getByText(/Rating 12\d\d → 1\d\d\d \(-\d+\)/)).toBeVisible()
  await expect(page.locator('.prevention-summary')).toContainText('1 / 2')
})
