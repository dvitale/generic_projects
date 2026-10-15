import {test,expect} from '@playwright/test'

test('The evaluation bar follows the live game and can be hidden from the board settings',async({page,request})=>{
  let game=await(await request.post('/api/games',{data:{color:'w',elo:1500}})).json()
  for(const move of ['e2e4','e7e5','d1h5','b8c6'])game=await(await request.post(`/api/games/${game.id}/moves`,{data:{move,version:game.version,revision:game.revision,actor:game.turn==='w'?'human':'maia'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  const bar=page.locator('.eval-bar')
  await expect(bar).toHaveAttribute('aria-label',/Valutazione Stockfish [+-]\d/,{timeout:30000})
  const boardBox=await page.locator('.board-stage').boundingBox(),barBox=await bar.boundingBox()
  expect(barBox!.x).toBeLessThan(boardBox!.x+30)
  await page.screenshot({path:'test-results/eval-bar.png'})
  await page.getByRole('button',{name:/^\W*Scacchiera$/}).click()
  await page.getByRole('checkbox',{name:'Barra di valutazione'}).uncheck()
  await expect(bar).toHaveCount(0)
})
