import {test,expect} from '@playwright/test'
import {performanceFromAccuracies,performanceFromAccuracy} from '../src/performance'

test('the estimate starts from every level alike and narrows as games add up',()=>{
  const one=performanceFromAccuracies([80])!,ten=performanceFromAccuracies(Array(10).fill(80))!
  expect(ten.high-ten.low).toBeLessThan(one.high-one.low)
  expect(performanceFromAccuracies(Array(10).fill(60))!.rating).toBeLessThan(performanceFromAccuracies(Array(10).fill(90))!.rating)
  for(const p of [one,ten]){expect(p.low).toBeGreaterThanOrEqual(600);expect(p.high).toBeLessThanOrEqual(2600)}
  expect(performanceFromAccuracies([])).toBeNull()
  expect(performanceFromAccuracy(80,9)).toBeNull()
  expect(performanceFromAccuracy(80,12)).toEqual(one)
})

test('Progressi estimates the performance from the analysed games against Maia',async({page,request})=>{
  const moves=['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4','g8f6','e1g1','f8e7','f1e1','b7b5','a4b3','d7d6','c2c3','e8g8','h2h3','c6a5','b3c2','c7c5','d2d4','d8c7']
  let g=await(await request.post('/api/games',{data:{color:'w',elo:1100}})).json()
  for(const [i,move] of moves.entries())g=await(await request.post(`/api/games/${g.id}/moves`,{data:{move,actor:i%2?'maia':'human',version:g.version,revision:g.revision}})).json()
  await request.post(`/api/games/${g.id}/analysis`,{data:{}})
  await expect.poll(async()=>(await(await request.get('/api/games/'+g.id)).json()).analysis?.version,{timeout:60000}).toBe(moves.length)
  await page.goto('/')
  await page.getByRole('button',{name:'Progressi',exact:true}).click()
  const panel=page.getByRole('region',{name:'Prestazione stimata'})
  await expect(panel.locator('.performance-value b')).toHaveText(/^≈ \d+$/)
  await expect(panel.locator('.performance-value span')).toHaveText(/^plausibile \d+–\d+$/)
  await expect(panel).toContainText('Sull’unica partita analizzata contro Maia, precisione media')
  await expect(panel).toContainText('Con 10 partite l’intervallo si restringe.')
})
