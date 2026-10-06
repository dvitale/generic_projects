import {test,expect,type Page} from '@playwright/test'
import {Chess} from 'chess.js'

const fen='7k/8/5KQ1/8/8/8/8/8 w - - 0 1'
async function checkLink(page:Page,expected:string){
  await page.getByRole('button',{name:/Analizza con Lichess/}).click()
  const href=await page.getByRole('link',{name:'apri Lichess in una nuova scheda'}).getAttribute('href')
  const url=new URL(href!)
  expect(decodeURIComponent(url.pathname.slice('/analysis/standard/'.length)).replaceAll('_',' ')).toBe(expected)
  expect(url.searchParams.get('color')).toBe('white')
}
test.beforeEach(async({page})=>{
  await page.addInitScript(()=>{window.open=()=>null})
})

test('prevention exports current board before, after solution and after original mistake',async({page})=>{
  const p={id:'lichess',gameId:'test',title:'Test',ply:0,fen,turn:'w',moveNumber:1,legalMoves:['g6g7','g6g8']}
  await page.route('**/api/prevention',r=>r.fulfill({json:{positions:[p],stats:{firstAttempts:0,firstSuccesses:0},rule:{description:'Test'}}}))
  await page.route('**/api/prevention/lichess/sessions',r=>r.fulfill({json:{id:'s',version:0,exposure:'new'}}))
  await page.route('**/api/training/prevention/lichess/mistakes',r=>r.fulfill({json:[]}))
  const e={cp:0,mate:null,san:[]}
  await page.route('**/api/prevention/lichess/reveal',r=>r.fulfill({json:{success:false,assisted:true,closed:true,version:1,move:'g6g7',san:'Qg7#',actual:e,original:{move:'g6g8',san:'Qg8+',evaluation:e},message:'Esempio'}}))
  await page.goto('/')
  await page.getByRole('button',{name:'Blunder prevention',exact:true}).click()
  await expect(page.getByRole('button',{name:/Analizza con Lichess/})).toHaveCount(0)
  await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await checkLink(page,fen)
  await page.getByRole('button',{name:'Mostra una mossa sicura'}).click()
  const b=new Chess(fen);b.move('Qg7#')
  await expect(page.locator('[data-square="g7"] img')).toBeVisible()
  await checkLink(page,b.fen())
  await page.getByRole('button',{name:'Mostra il vecchio errore'}).click()
  b.undo();b.move('Qg8+')
  await checkLink(page,b.fen())
})

test('puzzle and drill expose their displayed positions even without a normal game selected',async({page,request})=>{
  await page.route('**/api/exercises',r=>r.fulfill({json:[{id:'lichess',gameId:'test',ply:0,theme:'Test',fen,turn:'w',legalMoves:['g6g7'],streak:0,dueAt:'2000-01-01T00:00:00+00:00'}]}))
  await page.route('**/api/exercises/lichess/sessions',r=>r.fulfill({json:{id:'s',version:0,exposure:'new'}}))
  await page.route('**/api/training/puzzle/lichess/mistakes',r=>r.fulfill({json:[]}))
  await page.route('**/api/exercises/lichess/reveal',r=>r.fulfill({json:{success:false,assisted:true,closed:true,version:1,best:{cp:100000,mate:1,pv:['g6g7'],san:['Qg7#']},actual:null,message:'Soluzione mostrata'}}))
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  await checkLink(page,fen)
  await page.getByRole('button',{name:'Mostra soluzione',exact:true}).click()
  const b=new Chess(fen);b.move('Qg7#')
  await expect(page.locator('[data-square="g7"] img')).toBeVisible()
  await checkLink(page,b.fen())
  await page.getByRole('button',{name:'Drill',exact:true}).click()
  const started=page.waitForResponse(r=>r.url().includes('/api/drills/')&&r.url().endsWith('/start'))
  await page.getByRole('button',{name:/^Avvia/}).first().click()
  const game=await(await started).json()
  await checkLink(page,game.fen)
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})
