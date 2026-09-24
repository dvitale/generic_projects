import {test,expect,type Page,type APIRequestContext} from '@playwright/test'
import {Chess} from 'chess.js'

test.use({hasTouch:true})

async function prepare(page:Page,request:APIRequestContext,fen=new Chess().fen(),color='w') {
  const game=await(await request.post('/api/games',{data:{fen,color}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  const humanMoves:string[]=[]
  // Keep the board stable after the human move; the main suite tests real Maia replies.
  await page.route('**/api/games/*/moves',async route=>{
    const body=route.request().postDataJSON()
    if(body.actor==='maia'){await route.abort();return}
    humanMoves.push(body.move);await route.continue()
  })
  await page.goto('/')
  await expect(page.getByRole('button',{name:'Continua partita',exact:true})).toBeVisible()
  return {game,humanMoves}
}
async function centers(page:Page,from:string,to:string) {
  await page.getByRole('group',{name:'Scacchiera',exact:true}).scrollIntoViewIfNeeded()
  const a=await page.locator(`[data-square="${from}"]`).boundingBox()
  const b=await page.locator(`[data-square="${to}"]`).boundingBox()
  if(!a||!b)throw Error('Missing board squares')
  return {a:{x:a.x+a.width/2,y:a.y+a.height/2},b:{x:b.x+b.width/2,y:b.y+b.height/2}}
}
async function drag(page:Page,from:string,to:string) {
  const {a,b}=await centers(page,from,to)
  await page.mouse.move(a.x,a.y);await page.mouse.down()
  await page.mouse.move(b.x,b.y,{steps:8});await page.mouse.up()
}
async function play(page:Page){
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  await expect(page.getByText('Tocca a te · trascina un pezzo o usa due clic')).toBeVisible()
}

test('Drag respects read-only review, legal moves, cancellation and turn',async({page,request})=>{
  const {game,humanMoves}=await prepare(page,request)
  await drag(page,'e2','e4')
  expect(humanMoves).toEqual([])
  await play(page)
  await drag(page,'e7','e5')
  await drag(page,'e2','e5')
  expect(humanMoves).toEqual([])
  const {a,b}=await centers(page,'e2','e4')
  await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:5})
  await expect(page.locator('.dragged-piece')).toBeVisible()
  await page.keyboard.press('Escape');await page.mouse.up()
  await expect(page.locator('.dragged-piece')).toHaveCount(0)
  expect(humanMoves).toEqual([])
  const rect=await page.getByRole('group',{name:'Scacchiera',exact:true}).boundingBox()
  await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(rect!.x-15,rect!.y+100,{steps:5});await page.mouse.up()
  expect(humanMoves).toEqual([])
  await drag(page,'e2','e4')
  await expect.poll(()=>humanMoves.length).toBe(1)
  expect(humanMoves).toEqual(['e2e4'])
  await expect.poll(async()=>(await(await request.get('/api/games/'+game.id)).json()).version).toBe(1)
  await drag(page,'d2','d4')
  expect(humanMoves).toEqual(['e2e4'])
})

test('Black orientation maps the drop to the correct square',async({page,request})=>{
  const {humanMoves}=await prepare(page,request,new Chess().fen().replace(' w ',' b '),'b')
  await play(page)
  await drag(page,'e7','e5')
  await expect.poll(()=>humanMoves).toEqual(['e7e5'])
})

test('Dropping a pawn on the final rank still asks for promotion',async({page,request})=>{
  const {humanMoves}=await prepare(page,request,'4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
  await play(page)
  await drag(page,'a7','a8')
  await expect(page.getByRole('dialog',{name:'Scegli la promozione'})).toBeVisible()
  expect(humanMoves).toEqual([])
  await page.getByRole('button',{name:'cavallo',exact:true}).click()
  await expect.poll(()=>humanMoves).toEqual(['a7a8n'])
})

test('Touch dragging moves once without scrolling the page',async({page,request})=>{
  await page.setViewportSize({width:390,height:844})
  const {humanMoves}=await prepare(page,request)
  await play(page)
  const {a,b}=await centers(page,'e2','e4')
  const scroll=await page.evaluate(()=>scrollY)
  const cdp=await page.context().newCDPSession(page)
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:a.x,y:a.y,id:1}]})
  for(let step=1;step<=8;step++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:a.x+(b.x-a.x)*step/8,y:a.y+(b.y-a.y)*step/8,id:1}]})
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
  await expect.poll(()=>humanMoves).toEqual(['e2e4'])
  expect(await page.evaluate(()=>scrollY)).toBe(scroll)
  await cdp.detach()
})
