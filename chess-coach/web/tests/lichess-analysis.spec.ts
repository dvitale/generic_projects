import {test,expect} from '@playwright/test'
import {Chess} from 'chess.js'

test('Lichess popup follows live, historical and analysis positions without changing the game',async({page,request,context})=>{
  const board=new Chess()
  let game=await(await request.post('/api/games',{data:{fen:board.fen(),color:'w'}})).json()
  for(const move of ['e2e4','e7e5']){
    board.move({from:move.slice(0,2),to:move.slice(2,4)})
    game=await(await request.post(`/api/games/${game.id}/moves`,{data:{move,version:game.version,revision:game.revision,actor:game.turn==='w'?'human':'maia'}})).json()
  }
  // Exercise real popup creation, without depending on an external service in CI.
  await context.route('https://lichess.org/**',route=>route.fulfill({contentType:'text/html',body:'<title>Lichess test destination</title>'}))
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  async function checkPopup(fen:string){
    const popupPromise=context.waitForEvent('page')
    await page.getByRole('button',{name:'Analizza con Lichess',exact:false}).click()
    const popup=await popupPromise
    await popup.waitForLoadState()
    const url=new URL(popup.url())
    expect(url.origin).toBe('https://lichess.org')
    expect(decodeURIComponent(url.pathname.slice('/analysis/standard/'.length)).replaceAll('_',' ')).toBe(fen)
    expect(url.searchParams.get('color')).toBe('white')
    expect(await popup.evaluate(()=>window.opener===null)).toBe(true)
    await popup.close()
  }
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  await checkPopup(board.fen())
  await page.getByRole('region',{name:'Mosse della partita'}).getByRole('button',{name:'1. e4',exact:true}).click()
  board.undo()
  await checkPopup(board.fen())
  await page.getByRole('button',{name:'Rivedi',exact:true}).click()
  await page.getByRole('button',{name:'Posizione iniziale',exact:true}).click()
  await checkPopup(new Chess().fen())
  await page.getByRole('button',{name:'Mossa successiva',exact:true}).click()
  await checkPopup(board.fen())
  const after=await(await request.get('/api/games/'+game.id)).json()
  expect(after.moves).toEqual(game.moves)
  expect(after.version).toBe(game.version)
  await page.setViewportSize({width:390,height:844})
  await expect(page.getByRole('button',{name:/Analizza con Lichess/})).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})

test('blocked popup offers a snapshot link preserving Black orientation and complete FEN',async({page,request})=>{
  const fen='r3k2r/ppp2ppp/2n5/3pP3/8/2N5/PPP2PPP/R3K2R w KQkq d6 0 17'
  const game=await(await request.post('/api/games',{data:{fen,color:'b'}})).json()
  await page.addInitScript(id=>{localStorage.setItem('chess-coach-game',id);window.open=()=>null},game.id)
  await page.goto('/')
  await page.getByRole('button',{name:/Analizza con Lichess/}).click()
  const link=page.getByRole('link',{name:'apri Lichess in una nuova scheda'})
  await expect(link).toBeVisible()
  const url=new URL((await link.getAttribute('href'))!)
  expect(decodeURIComponent(url.pathname.slice('/analysis/standard/'.length)).replaceAll('_',' ')).toBe(fen)
  expect(url.searchParams.get('color')).toBe('black')
  await expect(link).toHaveAttribute('rel','noopener noreferrer')
  await expect(link).toHaveAttribute('target','_blank')
})
