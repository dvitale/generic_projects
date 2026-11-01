import {test,expect} from '@playwright/test'
import {Chess} from 'chess.js'

test('in review a selected piece shows Maia’s probability for each move, coloured by Stockfish',async({page,request})=>{
  const game=await(await request.post('/api/import',{data:{pgn:'1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *',color:'w'}})).json()
  await page.goto('/')
  await page.getByRole('button',{name:'Partite',exact:true}).click()
  await page.locator('.game-list button').filter({hasText:game.title}).first().click()
  await page.getByRole('button',{name:'Posizione iniziale',exact:true}).click()
  const next=page.locator('.review-controls').getByRole('button',{name:'Mossa successiva'})
  for(let i=0;i<4;i++)await next.click()
  // White's queen on h5, before the blunder 3. Qxe5+.
  const queenMoves=new Chess('r1bqkbnr/pppp1ppp/2n5/4p2Q/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 2 3').moves({square:'h5'}).length
  await page.locator('[data-square="h5"]').click()
  await expect(page.locator('[data-square="h5"]')).toHaveAttribute('aria-pressed','true')
  const odds=page.locator('.move-odds')
  await expect(odds).toHaveCount(queenMoves)
  await expect(page.locator('.move-odds.odds-pending')).toHaveCount(0,{timeout:15000})
  await expect(page.locator('[data-square="e5"] .move-odds')).toHaveText(/^\d+,\d%$/)
  await expect(page.locator('[data-square="e5"] .move-odds')).toHaveClass(/odds-mistake/)
  await expect(page.locator('[data-square="e5"]')).toHaveAttribute('aria-label',/Qxe5\+ · Maia \d+,\d% .*Stockfish: errore \(−\d+ punti di punteggio atteso\)/)
  await page.screenshot({path:'test-results/piece-odds.png'})
  // A second click, a black piece or a new position clear the selection.
  await page.locator('[data-square="h5"]').click()
  await expect(odds).toHaveCount(0)
  await page.locator('[data-square="c6"]').click()
  await expect(odds).toHaveCount(0)
  await page.locator('[data-square="h5"]').click()
  await expect(odds).toHaveCount(queenMoves)
  await next.click()
  await expect(odds).toHaveCount(0)
  // After 3. Qxe5+ Black moves: the knight on c6 can be inspected, until the switch turns the feature off.
  await page.locator('[data-square="c6"]').click()
  await expect(odds).not.toHaveCount(0)
  await page.getByLabel('Mosse del pezzo',{exact:true}).uncheck()
  await expect(odds).toHaveCount(0)
  await page.locator('[data-square="c6"]').click()
  await expect(odds).toHaveCount(0)
})
