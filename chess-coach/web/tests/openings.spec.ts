import {test,expect} from '@playwright/test'
import {Chess} from 'chess.js'

test('games carry their opening name, and review shows it with the book exit',async({page,request})=>{
  const game=await(await request.post('/api/import',{data:{pgn:'1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. h4 e5 *',color:'w'}})).json()
  await page.goto('/')
  await page.getByRole('button',{name:'Partite',exact:true}).click()
  const row=page.locator('.game-list button').filter({hasText:game.title}).first()
  await expect(row.locator('.game-opening')).toHaveText(' · B90 Sicilian Defense: Najdorf Variation')
  await row.click()
  // Review opens on the final position, past the book: the button jumps back to where the theory ends.
  const opening=page.locator('.review-opening')
  await expect(opening.locator('.review-opening-name')).toHaveText('B90 Sicilian Defense: Najdorf Variation')
  await expect(page.locator('.review-moves .move-cell.in-book')).toHaveCount(10)
  await page.screenshot({path:'test-results/openings.png'})
  await opening.getByRole('button',{name:'Fuori teoria dopo 5… a6'}).click()
  await expect(page.locator('.review-step')).toContainText('6. h4')
  await expect(opening.getByRole('button',{name:'Teoria fino a 5… a6'})).toBeVisible()
  // The name follows the board: after 1. e4 c5 it is the Sicilian, at the start nothing is named yet.
  await page.getByRole('button',{name:'Posizione iniziale',exact:true}).click()
  await expect(opening.locator('.review-opening-name')).toHaveText('Apertura non ancora riconosciuta')
  const next=page.locator('.review-controls').getByRole('button',{name:'Mossa successiva'})
  await next.click();await next.click()
  await expect(opening.locator('.review-opening-name')).toHaveText('B20 Sicilian Defense')
})

test('the game in progress shows its opening under the move list',async({page,request})=>{
  let game=await(await request.post('/api/games',{data:{fen:new Chess().fen(),color:'w'}})).json()
  for(const move of ['e2e4','e7e5','g1f3','b8c6','h2h3','h7h6'])game=await(await request.post(`/api/games/${game.id}/moves`,{data:{move,version:game.version,revision:game.revision,actor:game.turn==='w'?'human':'maia'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Continua partita',exact:true}).click()
  const history=page.getByRole('region',{name:'Mosse della partita'}),opening=history.locator('.move-history-opening')
  await expect(opening).toHaveText('C44 King\'s Knight Opening: Normal VariationFuori teoria dopo 2… Nc6')
  await expect(history.locator('button.in-book')).toHaveCount(4)
  await page.screenshot({path:'test-results/openings-play.png'})
  // Browsing back, the name follows the board.
  await history.getByRole('button',{name:'1. e4',exact:true}).click()
  await expect(opening).toHaveText('B00 King\'s Pawn GameIn teoria')
})

test('Progress lists the repertoire by opening and trains from the end of the theory',async({page,request})=>{
  for(const [third,result] of [['Bd3','0-1'],['Qe2','0-1'],['Na3','1/2-1/2']])
    await request.post('/api/import',{data:{pgn:`1. e4 e5 2. Nf3 d6 3. ${third} h6 ${result}`,color:'w'}})
  await page.goto('/')
  await page.getByRole('button',{name:'Progressi',exact:true}).click()
  const panel=page.getByRole('region',{name:'Il tuo repertorio'})
  const row=panel.locator('.repertoire-row').filter({hasText:'Philidor Defense'})
  await expect(row.locator('.repertoire-status')).toHaveText('Da curare')
  await expect(row.locator('.repertoire-games')).toHaveText('3 partite')
  await expect(row.locator('dd').first()).toHaveText('17%')
  await row.scrollIntoViewIfNeeded()
  await page.screenshot({path:'test-results/openings-repertoire.png'})
  await row.getByRole('button',{name:'Allena da lì'}).click()
  await expect(page.getByText('Fine della teoria: Philidor Defense').first()).toBeVisible()
  await expect(page.locator('[data-square="d6"] img')).toBeVisible()
})
