import {test,expect} from '@playwright/test'
import {gameAccuracy,moveAccuracy,winPercent} from '../src/accuracy'
import type {Game} from '../src/types'
import {classifyMove} from '../src/moveClass'

test('accuracy follows the Lichess win-percentage formula',()=>{
  expect(winPercent({cp:0,mate:null})).toBe(50)
  expect(winPercent({cp:null,mate:'b'})).toBe(0)
  expect(winPercent({cp:5000,mate:null})).toBeCloseTo(winPercent({cp:1000,mate:null}))
  expect(moveAccuracy(60,60)).toBe(100)
  expect(moveAccuracy(60,70)).toBe(100)
  expect(moveAccuracy(100,0)).toBe(0)
  const point=(position:number,cp:number)=>({position,label:'',cp,mate:null,terminal:false,depth:10,initial:false})
  const game={initialFen:'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'} as Game
  const steady=gameAccuracy(game,[0,1,2,3].map(i=>point(i,20)),new Set())
  expect(steady.w).toBe(100)
  expect(steady.b).toBe(100)
  const swing=gameAccuracy(game,[point(0,20),point(1,20),point(2,-600),point(3,-600)],new Set())
  expect(swing.w).toBe(100)
  expect(swing.b).toBe(100)
  const white=gameAccuracy(game,[point(0,20),point(1,-600),point(2,-600),point(3,-600)],new Set())
  expect(white.w!).toBeLessThan(60)
  expect(gameAccuracy(game,[point(0,20),point(1,-600),point(2,-600),point(3,-600)],new Set([0])).w).toBe(100)
  expect(gameAccuracy(game,[point(0,20),point(2,20),point(3,20)],new Set()).w).toBeNull()
})

test('move classes separate errors from blunders that lose three points or allow mate',()=>{
  const move=(loss:number)=>classifyMove({loss,played:'e2e4',best:{pv:['d2d4']} as never,forced:false})
  expect([79,80,179,180,299,300,99395].map(move)).toEqual(['good','inaccuracy','inaccuracy','error','error','blunder','blunder'])
})

test('review summary compares both sides, marks mistakes on the graph and lists Stockfish lines',async({page,request})=>{
  const imported=await(await request.post('/api/import',{data:{pgn:'1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0',color:'w'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),imported.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Rivedi',exact:true}).click()
  await page.getByRole('button',{name:/^(Analizza partita|Ricalcola analisi)$/}).click()
  await expect(page.getByText(/Revisione pronta/)).toBeVisible({timeout:60000})
  const summary=page.getByRole('region',{name:'Riepilogo della partita'})
  const table=summary.getByRole('table',{name:'Confronto tra i due lati'})
  await expect(table.getByRole('rowheader',{name:'Precisione',exact:true})).toBeVisible()
  await expect(table.locator('.score-chip-w')).toHaveText(/^\d+%$/)
  await expect(table.locator('.score-chip-b')).toHaveText(/^\d+%$/)
  const mark=summary.getByRole('button',{name:'Grafico: 3… Nf6 · Errore grave'})
  await expect(mark).toBeVisible()
  await mark.click()
  await expect(mark).toHaveAttribute('aria-current','step')
  const lines=summary.getByRole('list',{name:'Scelte di Stockfish nella posizione mostrata'})
  await expect(lines.locator('li').first()).toContainText('3…')
  await expect(lines.locator('.score-chip').first()).toHaveText(/^[+-]?\d+\.\d\d$|^-?#\d+$/)
  await summary.getByRole('button',{name:/^Vai a 4\. Qxf7#/}).click()
  await page.keyboard.press('ArrowRight')
  await expect(lines).toContainText('Posizione finale')
})
