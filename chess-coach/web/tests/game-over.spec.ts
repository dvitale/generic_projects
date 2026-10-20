import {test,expect,type Page} from '@playwright/test'

async function open(page:Page,id:string,finished=false){
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),id)
  await page.goto('/')
  await page.getByRole('button',{name:finished?'Gioca':'Continua partita',exact:true}).click()
}

test('Delivering checkmate is announced and the mated king is highlighted',async({page,request})=>{
  const g=await(await request.post('/api/games',{data:{color:'w',fen:'7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}})).json()
  await open(page,g.id)
  await expect(page.locator('.game-over')).toHaveCount(0)
  await page.locator('[data-square="g6"]').click();await page.locator('[data-square="g7"]').click()
  const banner=page.locator('.game-over')
  await expect(banner).toContainText('Scacco matto · Hai vinto')
  await expect(banner).toContainText('il re avversario è sotto scacco e non ha mosse per salvarsi')
  await expect(banner).toHaveClass(/game-over-win/)
  await expect(page.locator('[data-square="h8"]')).toHaveClass(/check-square/)
  await expect(page.getByText('Partita conclusa · Scacco matto · Hai vinto')).toBeVisible()
  await page.screenshot({path:'test-results/game-over-checkmate.png',fullPage:true})
})

test('Being checkmated is announced as a defeat',async({page,request})=>{
  const g=await(await request.post('/api/games',{data:{color:'w',fen:'r5k1/8/8/8/8/8/5PPP/6K1 b - - 0 1'}})).json()
  await request.post(`/api/games/${g.id}/moves`,{data:{move:'a8a1',actor:'maia',version:0,revision:0}})
  await open(page,g.id,true)
  const banner=page.locator('.game-over')
  await expect(banner).toContainText('Scacco matto · Hai perso')
  await expect(banner).toContainText('il tuo re è sotto scacco')
  await expect(banner).toHaveClass(/game-over-loss/)
  await expect(page.locator('[data-square="g1"]')).toHaveClass(/check-square/)
})

test('Stalemate is explained as a draw without a king in check',async({page,request})=>{
  const s=await(await request.post('/api/games',{data:{color:'w',fen:'7k/8/5K2/6Q1/8/8/8/8 w - - 0 1'}})).json()
  await request.post(`/api/games/${s.id}/moves`,{data:{move:'g5g6',actor:'human',version:0,revision:0}})
  await open(page,s.id,true)
  const banner=page.locator('.game-over')
  await expect(banner).toContainText('Stallo · Patta')
  await expect(banner).toContainText('il Nero non ha mosse legali ma non è sotto scacco')
  await expect(page.locator('.check-square')).toHaveCount(0)
})
