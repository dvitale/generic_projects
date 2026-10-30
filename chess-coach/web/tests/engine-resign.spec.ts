import {test,expect} from '@playwright/test'

async function lostGame(request:import('@playwright/test').APIRequestContext){
  // Queen and rook against a lone king, 21 quiet plies: Maia's next turn is the third lost one past move 20.
  let game=await(await request.post('/api/games',{data:{color:'w',elo:600,fen:'7k/8/8/8/8/8/8/2QRK3 w - - 0 1'}})).json()
  const king=['e1e2','e2e3','e3e4','e4d4','d4d5','d5c5','c5c4','c4b4','b4b3','b3a3','a3a4']
  for(const [i,human] of king.entries()){
    game=await(await request.post(`/api/games/${game.id}/moves`,{data:{move:human,actor:'human',version:game.version,revision:game.revision}})).json()
    if(i<king.length-1)game=await(await request.post(`/api/games/${game.id}/moves`,{data:{move:i%2?'g8h8':'h8g8',actor:'maia',version:game.version,revision:game.revision}})).json()
  }
  expect(game.moves).toHaveLength(21)
  return game
}

test('Maia asks to resign a clearly lost game and the accepted offer ends it',async({page,request})=>{
  const game=await lostGame(request)
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  const offer=page.getByRole('alertdialog',{name:'Maia ha manifestato l’intenzione di abbandonare. Accetti?'})
  await expect(offer).toBeVisible({timeout:30000})
  // The offer lies over the middle of the board, in view, not below it where it went unnoticed.
  await expect(offer).toBeInViewport()
  const [box,board]=[await offer.boundingBox(),await page.locator('.board-stage').first().boundingBox()]
  const middle=(b:{x:number;y:number;width:number;height:number})=>({x:b.x+b.width/2,y:b.y+b.height/2})
  expect(Math.abs(middle(box!).y-middle(board!).y)).toBeLessThan(4)
  expect(box!.x).toBeGreaterThan(board!.x);expect(box!.x+box!.width).toBeLessThan(board!.x+board!.width)
  await expect(page.locator('.game-over')).toHaveCount(0)
  expect((await(await request.get('/api/games/'+game.id)).json()).termination).toBeNull()
  await offer.getByRole('button',{name:'Accetta l’abbandono'}).click()
  await expect(page.locator('.game-over')).toContainText('Maia abbandona · Hai vinto')
  await expect(offer).toHaveCount(0)
  await expect(page.locator('.game-over')).toContainText('1-0')
  const saved=await(await request.get('/api/games/'+game.id)).json()
  expect(saved).toMatchObject({termination:'engine_resign',result:'1-0'})
  expect(saved.moves).toHaveLength(21)
})

test('Declining the offer lets Maia play on',async({page,request})=>{
  const game=await lostGame(request)
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  const offer=page.getByRole('alertdialog')
  await expect(offer).toBeVisible({timeout:30000})
  await offer.getByRole('button',{name:'Continua a giocare'}).click()
  await expect(offer).toHaveCount(0)
  await expect.poll(async()=>(await(await request.get('/api/games/'+game.id)).json()).moves.length,{timeout:30000}).toBe(22)
  await expect(page.locator('.game-over')).toHaveCount(0)
})
