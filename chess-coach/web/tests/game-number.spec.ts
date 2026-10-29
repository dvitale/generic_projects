import {test,expect} from '@playwright/test'

test('each game shows its unique number in the list and in Review',async({page,request})=>{
  const first=await(await request.post('/api/import',{data:{pgn:'1. e4 e5 *',color:'w'}})).json()
  const second=await(await request.post('/api/import',{data:{pgn:'1. d4 d5 *',color:'w'}})).json()
  expect(second.number).toBe(first.number+1)
  await page.goto('/')
  await page.getByRole('button',{name:'Partite',exact:true}).click()
  const row=page.locator('.game-list button').filter({hasText:`#${second.number}`})
  await expect(row).toHaveCount(1)
  await expect(row.locator('.game-number')).toHaveText(`#${second.number}`)
  await page.setViewportSize({width:390,height:844})
  await expect(row.locator('.game-number')).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.setViewportSize({width:1280,height:720})
  await row.click()
  await expect(page.getByRole('heading',{level:1})).toHaveText(`Rivedi la partita #${second.number}`)
  await page.screenshot({path:'test-results/game-number-review.png'})
})
