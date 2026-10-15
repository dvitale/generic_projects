import {test,expect} from '@playwright/test'

test('A reviewed position can be flipped and played against Maia from the chosen side',async({page,request})=>{
  let game=await(await request.post('/api/games',{data:{color:'w',elo:1100}})).json()
  for(const move of ['e2e4','e7e5','g1f3','b8c6'])game=await(await request.post(`/api/games/${game.id}/moves`,{data:{move,version:game.version,revision:game.revision,actor:game.turn==='w'?'human':'maia'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Rivedi',exact:true}).first().click()
  await page.getByRole('button',{name:'Mossa precedente'}).click()
  await page.getByRole('button',{name:'Mossa precedente'}).click()
  const flip=page.getByRole('button',{name:'Inverti scacchiera'})
  const a1=await page.locator('[data-square="a1"]').boundingBox()
  await flip.click()
  await expect(flip).toHaveAttribute('aria-pressed','true')
  const flipped=await page.locator('[data-square="a1"]').boundingBox()
  expect(flipped!.y).toBeLessThan(a1!.y)
  await page.screenshot({path:'test-results/play-from-review.png'})
  await page.getByRole('button',{name:'Gioca da qui col Nero'}).click()
  await expect(page.getByRole('heading',{name:'Gioca contro Maia'})).toBeVisible()
  // White (Maia) is to move after 2. Nf3 is taken back, so Maia answers first.
  await expect.poll(async()=>{
    const id=await page.evaluate(()=>localStorage.getItem('chess-coach-game'))
    const next=await(await request.get('/api/games/'+id)).json()
    return [next.id!==game.id,next.playerColor,next.initialFen.split(' ')[0],next.title]
  }).toEqual([true,'b','rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR',expect.stringMatching(/^Da .* · 2\.$/)])
  // The chosen side is now the player's colour: the board is no longer flipped and Black is at the bottom.
  await expect(flip).toHaveAttribute('aria-pressed','false')
  expect((await page.locator('[data-square="a1"]').boundingBox())!.y).toBeLessThan(a1!.y)
  await page.keyboard.press('f')
  await expect(flip).toHaveAttribute('aria-pressed','true')
})
