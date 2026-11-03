import {test,expect} from '@playwright/test'

test('following a book game: guess the black moves, white answers with a note',async({page})=>{
  await page.goto('/?section=lessons')
  const card=page.locator('.walk-card').filter({hasText:'von Scheve–Teichmann'})
  await expect(card).toContainText('giochi con il Nero, 17 mosse')
  await card.getByRole('button',{name:'Segui la partita →'}).click()

  const panel=page.getByRole('region',{name:'Segui la partita'})
  await expect(panel.locator('.eyebrow')).toContainText('MOSSA 1 DI 17')
  await expect(panel.locator('.walk-reply')).toContainText('Il Bianco gioca 1.e4.')
  await panel.getByRole('button',{name:'Indizio 1 di 2'}).click()
  await expect(panel.getByRole('list',{name:'Indizi'}).getByRole('listitem')).toHaveCount(1)
  await page.locator('[data-square="e7"]').click();await page.locator('[data-square="e5"]').click()
  await expect(panel.getByRole('status')).toContainText('✓ e5: La mossa della partita.')
  await expect(page.getByRole('region',{name:'Idea del libro'})).toContainText('Nella partita: e5')
  await expect(page.getByRole('region',{name:'Valutazione di Stockfish'})).toContainText('Migliore per il motore')
  await expect(page.getByLabel('Punteggio')).toHaveText('1 su 1 trovate')

  // White's reply is played for you; the second move is one of the lessons.
  await page.getByRole('button',{name:'Continua →'}).click()
  await expect(panel.locator('.eyebrow')).toContainText('MOSSA 2 DI 17 · LEZIONE')
  await expect(panel.locator('.walk-reply')).toContainText('Il Bianco gioca 2.Nf3.')
  await expect(panel.locator('.walk-reply')).toContainText('Stockfish:')
  await page.locator('[data-square="b8"]').click();await page.locator('[data-square="a6"]').click()
  await expect(panel.getByRole('status')).toContainText('✗ Na6')
  await expect(page.getByRole('region',{name:'Idea del libro'})).toContainText('Nella partita: Nc6')
  await page.screenshot({path:'test-results/lesson-walk.png',fullPage:true})
  await page.getByRole('button',{name:'Riprova questa mossa'}).click()
  await page.locator('[data-square="b8"]').click();await page.locator('[data-square="c6"]').click()
  await expect(panel.getByRole('status')).toContainText('✓ Nc6')
  await expect(page.getByText('Secondo tentativo: non cambia il punteggio.')).toBeVisible()
  await expect(page.getByLabel('Punteggio')).toHaveText('1 su 2 trovate')

  await page.getByRole('button',{name:'Tutte le lezioni'}).click()
  await expect(card).toContainText('In corso: 2 di 17 mosse, 1 trovate.')
  await card.getByRole('button',{name:'Riprendi →'}).click()
  await expect(panel.locator('.eyebrow')).toContainText('MOSSA 3 DI 17')
  await expect(panel.locator('.walk-reply')).toContainText('Il Bianco gioca 3.Bc4.')

  // The black moves up to the last one, through the API; then the end of the game on the board.
  const {walks}=await (await page.request.get('/api/lesson-walks')).json()
  const run=walks[0].current.id
  const black=['f8c5','d8e7','d7d6','c5b6','a7a6','b6a7','g8f6','c6e5','e7e5','c8h3','e5g3','g3h3','f6g4','h3g3']
  for(const [i,move] of black.entries())
    expect((await page.request.post('/api/lesson-walks/partita-1/answer',{data:{run,ply:5+2*i,move,hints:0}})).ok()).toBeTruthy()
  await page.getByRole('button',{name:'Interrompi'}).click()
  await card.getByRole('button',{name:'Riprendi →'}).click()
  await expect(panel.locator('.eyebrow')).toContainText('MOSSA 17 DI 17')
  await expect(panel.locator('.walk-reply')).toContainText('Il Bianco gioca 17.Kh1.')
  await page.locator('[data-square="a7"]').click();await page.locator('[data-square="f2"]').click()
  const end=page.getByRole('region',{name:'Fine della partita'})
  await expect(end).toContainText('FINE · 0-1')
  await expect(end).toContainText('Hai trovato 16 mosse su 17 al primo tentativo')
  await expect(page.getByRole('region',{name:'Valutazione di Stockfish'}).locator('.lesson-disagree')).toContainText('18.Bxf7+')
  await expect(page.getByRole('button',{name:'Ricomincia la partita'})).toBeVisible()
  await page.screenshot({path:'test-results/lesson-walk-end.png',fullPage:true})
})
