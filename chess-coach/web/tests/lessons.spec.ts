import {test,expect} from '@playwright/test'

test('a book lesson takes a move, then shows the book idea and Stockfish apart',async({page})=>{
  await page.goto('/?section=lessons')
  await expect(page.getByRole('heading',{name:'Ragionamento mossa per mossa'}).last()).toBeVisible()
  const list=page.getByRole('list',{name:'Lezioni'})
  await expect(list.getByRole('button')).toHaveCount(10)
  await list.getByRole('button',{name:/Prevenire la minaccia/}).click()

  const lesson=page.getByRole('region',{name:'Lezione'})
  await expect(lesson.locator('.lesson-line')).toHaveText('1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3')
  await expect(lesson.locator('.eyebrow')).toContainText('MUOVE IL NERO')
  await lesson.getByRole('button',{name:'Indizio 1 di 3'}).click()
  await expect(lesson.getByRole('list',{name:'Indizi'}).getByRole('listitem')).toHaveCount(1)
  await page.screenshot({path:'test-results/lessons.png'})

  // The game move 4...Qe7: right for the book, an inaccuracy for Stockfish.
  await page.locator('[data-square="d8"]').click();await page.locator('[data-square="e7"]').click()
  await expect(lesson.getByRole('status')).toContainText('✓ Qe7: La mossa della partita.')
  // The game move is played on the board, and the way on sits right under the answer.
  await expect(page.locator('[data-square="e7"]')).toHaveAttribute('aria-label','e7 donna nero')
  await expect(page.locator('[data-square="d8"]')).toHaveAttribute('aria-label','d8')
  await expect(lesson.getByRole('button',{name:'Prossima lezione →'})).toBeInViewport()
  await expect(lesson.getByRole('button',{name:'Continua la partita →'})).toBeInViewport()
  const book=page.getByRole('region',{name:'Idea del libro'})
  await expect(book).toContainText('Nella partita: Qe7')
  await expect(book.locator('.eyebrow')).toContainText('PARTITA 1, P. 14')
  const engine=page.getByRole('region',{name:'Valutazione di Stockfish'})
  await expect(engine).toContainText('Imprecisione')
  await expect(engine).toContainText('Migliore per il motore: Nf6')
  // Scores are from White's side, whoever moves: Black's inaccuracy shows as an edge for White.
  await expect(engine).toContainText('La tua mossa Qe7: +1,00')
  await expect(engine).toContainText('Nf6 +0,18')
  await expect(engine.locator('.lesson-disagree')).toContainText('libro e motore non coincidono')
  await expect(engine.locator('tr.chosen')).toContainText('Qe7')
  await expect(page.getByText(/Prossimo ripasso: /)).toBeVisible()
  await page.screenshot({path:'test-results/lessons-answer.png',fullPage:true})

  // A second try before the review is due is practice and does not move the schedule.
  await page.getByRole('button',{name:'Riprova'}).click()
  await expect(lesson.getByText(/questa risposta è solo pratica/)).toBeVisible()
  await page.locator('[data-square="a7"]').click();await page.locator('[data-square="a6"]').click()
  await expect(lesson.getByRole('status')).toContainText('✗ a6')
  await expect(page.getByText('Risposta di pratica: il ripasso non cambia.')).toBeVisible()

  await page.getByRole('button',{name:'Tutte le lezioni'}).click()
  await expect(list.getByRole('button',{name:/Prevenire la minaccia/})).toContainText('Da rifare')
  await expect(page.getByRole('button',{name:'Inizia la prossima →'})).toBeVisible()
})

test('a lesson from game 1 continues into the followed game from the next move',async({page})=>{
  await page.goto('/?section=lessons')
  await page.getByRole('list',{name:'Lezioni'}).getByRole('button',{name:/Sviluppo con minaccia/}).click()
  await page.locator('[data-square="g1"]').click();await page.locator('[data-square="f3"]').click()
  await expect(page.locator('[data-square="f3"]')).toHaveAttribute('aria-label','f3 cavallo bianco')
  await page.getByRole('button',{name:'Continua la partita →'}).click()
  const panel=page.getByRole('region',{name:'Segui la partita'})
  await expect(panel.locator('.eyebrow')).toContainText('MOSSA 2 DI 17 · LEZIONE')
  await expect(panel.locator('.walk-reply')).toContainText('Il Bianco gioca 2.Nf3.')
  await page.locator('[data-square="b8"]').click();await page.locator('[data-square="c6"]').click()
  await expect(page.getByLabel('Punteggio')).toHaveText('1 su 1 trovate')
  await page.getByRole('button',{name:'Tutte le lezioni'}).click()
  await expect(page.locator('.walk-card')).toContainText('In corso dalla mossa 2: 1 di 16 mosse, 1 trovate.')
})
