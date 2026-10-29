import {test,expect} from '@playwright/test'

test('the count-up clock runs during the turn and survives a reload',async({page})=>{
  await page.goto('/')
  await page.getByRole('button',{name:'Gioca',exact:true}).click()
  await page.getByRole('button',{name:'Inizia partita →'}).click()
  await expect(page.getByText('Tocca a te · trascina un pezzo o usa due clic')).toBeVisible()
  const mine=page.locator('.player-row',{hasText:'Tu'}).locator('.player-clock')
  await expect(mine).toHaveText('0:00')
  await expect(mine).toHaveText('0:02',{timeout:5000})
  await page.reload()
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  await expect(mine).toHaveText(/^0:0[2-9]$/)
  await expect(page.locator('.player-row.to-move .player-clock')).toHaveCount(1)
})
