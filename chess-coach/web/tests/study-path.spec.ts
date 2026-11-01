import {test,expect} from '@playwright/test'

// Runs after problems.spec.ts: it changes the problem rating that test starts from.
test('a recurring gap in Problemi opens a study path with a lesson, graduated hints and the themed series',async({page,request})=>{
  // 001wr (fork, 989) is the only problem of its band: failing it six times at about 1200 is far below the rating expectation.
  for(let i=0;i<6;i++){
    const next=await(await request.post('/api/problems/next',{data:{band:1}})).json()
    expect(next.puzzle.id).toBe('001wr')
    await request.post(`/api/problems/sessions/${next.sessionId}/reveal`,{data:{step:1}})
  }
  await page.goto('/?section=progress')
  const gaps=page.getByRole('region',{name:'Lacune ricorrenti'})
  await expect(gaps.getByRole('heading',{name:'Confermate'})).toBeVisible()
  const fork=gaps.locator('.gap-row',{hasText:'Forchetta'})
  await expect(fork).toContainText('Motivo tattico · Problemi')
  // problems.spec.ts may already have failed the same problem once.
  await expect(fork).toContainText(/0 \/ [67] atteso/)
  await gaps.screenshot({path:'test-results/gaps-progress.png'})
  await fork.getByRole('button',{name:'Inizia il percorso di studio'}).click()
  const path=page.getByRole('region',{name:'Percorso di studio'})
  await expect(path.getByRole('heading',{name:'Attacco doppio'})).toBeVisible()
  await expect(path).toContainText('Come si riconosce')
  await expect(path).toContainText('Problema 001wr')
  await expect(path.locator('[aria-current="step"]')).toHaveText('Lezione')
  await page.screenshot({path:'test-results/study-path-lesson.png'})
  await path.getByRole('button',{name:'Ho letto: inizia la serie →'}).click()
  await expect(page.getByRole('heading',{name:'Tocca a te'})).toBeVisible()
  await expect(page.locator('.study-path-status')).toContainText('Attacco doppio · Serie a tema 1 / 8')
  // Hints: kind of move, the Lichess motif, Maia's tempting move refuted by Stockfish, then the piece, highlighted on the board.
  await page.getByRole('button',{name:'Chiedi un indizio'}).click()
  const hints=page.getByRole('list',{name:'Indizi'})
  await expect(hints.locator('li')).toHaveCount(1)
  await page.getByRole('button',{name:'Un altro indizio'}).click()
  await expect(hints.locator('li').nth(1)).toHaveText('Motivo Forchetta')
  await page.getByRole('button',{name:'Un altro indizio'}).click()
  const tempting=hints.locator('li').nth(2)
  await expect(tempting).toContainText(/^La mossa che tenta La mossa che viene più naturale è \S+: al tuo livello la sceglierebbe circa un giocatore su \d+\. Non funziona/)
  await tempting.getByRole('button',{name:'Mostra',exact:true}).click()
  const replay=page.getByRole('dialog',{name:'La mossa che tenta'})
  // Only the refuted line: the better move would give the solution away.
  await expect(replay.getByRole('group',{name:'Variante da guardare'})).toHaveCount(0)
  await expect(replay.getByRole('status')).toContainText(/^1\/\d+ · /)
  await page.screenshot({path:'test-results/study-path-tempting.png'})
  await page.keyboard.press('Escape')
  await expect(replay).toHaveCount(0)
  await page.getByRole('button',{name:'Un altro indizio'}).click()
  await expect(hints.locator('li').nth(3)).toContainText(/^Mosse candidate La soluzione è una di queste mosse: \S+(, \S+)? o \S+\. Per ognuna cerca la risposta più forte dell’avversario/)
  await page.getByRole('button',{name:'Un altro indizio'}).click()
  await expect(hints.locator('li').nth(4)).toContainText('Dove guardare')
  await expect(page.locator('.hint-square')).toHaveCount(1)
  await expect(page.getByRole('button',{name:'Un altro indizio'})).toBeDisabled()
  // Leaving the problem shows the path again; abandoning it brings back the free problems.
  await page.getByRole('button',{name:'Cambia fascia'}).click()
  await expect(path.locator('[aria-current="step"]')).toHaveText('Serie a tema')
  await path.getByRole('button',{name:'Abbandona il percorso'}).click()
  await expect(page.getByRole('heading',{name:'Punisci l’errore dell’avversario'})).toBeVisible()
})
