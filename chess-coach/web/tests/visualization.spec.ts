import {test,expect} from '@playwright/test'

const GAME='1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O Bxc3 9. d5 Bf6 10. Re1 Ne7 11. Rxe4 d6 12. Bg5 Bxg5 13. Nxg5 h6 14. Qe2 hxg5 15. Re1 Be6 16. dxe6 f6 17. Re3 c6 *'

test('visualization asks about the position a line of moves leads to, then shows it',async({page,request})=>{
  await request.post('/api/import',{data:{pgn:GAME,color:'w'}})
  await page.goto('/?section=visual')
  await expect(page.getByRole('heading',{name:'Allena la visualizzazione'})).toBeVisible()
  await page.getByRole('button',{name:'Inizia →'}).click()
  const question=page.getByRole('region',{name:'Domanda'})
  await expect(question.locator('.eyebrow')).toHaveText(/GIOCA A MENTE · \d SEMIMOSS[AE]/)
  await expect(question.locator('.visualization-line')).toHaveText(/^\d+(\.|…) \S+/)
  const start=await page.locator('[data-square] img').count()
  const options=question.getByRole('group',{name:'Risposte'}).getByRole('button')
  expect(await options.count()).toBeGreaterThanOrEqual(2)
  await page.screenshot({path:'test-results/visualization.png'})
  await options.first().click()
  await expect(question.getByRole('status')).toContainText(/^(✓ Giusto\.|✗ Non è così\.)/)
  await expect(question.locator('.option-right')).toHaveCount(1)
  await expect(page.getByRole('button',{name:'Dopo la linea'})).toHaveAttribute('aria-pressed','true')
  await page.getByRole('button',{name:'Partenza'}).click()
  await expect(page.locator('[data-square] img')).toHaveCount(start)
  await expect(question.locator('.footnote')).toContainText('Ultime 1 risposte')
  await page.getByRole('button',{name:'Prossima domanda →'}).click()
  await expect(question.getByRole('status')).toHaveCount(0)
  await expect(options.first()).toBeEnabled()
})
