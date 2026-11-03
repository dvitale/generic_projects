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
  const book=page.getByRole('region',{name:'Idea del libro'})
  await expect(book).toContainText('Nella partita: Qe7')
  await expect(book.locator('.eyebrow')).toContainText('PARTITA 1, P. 14')
  const engine=page.getByRole('region',{name:'Valutazione di Stockfish'})
  await expect(engine).toContainText('Imprecisione')
  await expect(engine).toContainText('Migliore per il motore: Nf6')
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
