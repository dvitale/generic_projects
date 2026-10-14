import {test,expect} from '@playwright/test'

test('final comment is requested explicitly, saved, and links to the exact decision',async({page,request})=>{
  const game=await(await request.post('/api/import',{data:{pgn:'1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *'}})).json()
  const job=await(await request.post(`/api/games/${game.id}/analysis`)).json()
  await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status).toBe('complete')
  let calls=0,saved:any=null
  await page.route('**/api/tutor/status',r=>r.fulfill({json:{configured:true}}))
  await page.route(`**/api/games/${game.id}/final-review`,async r=>{
    if(r.request().method()==='POST'){
      calls++
      expect(r.request().postDataJSON()).toEqual({version:6,revision:0})
      saved={createdAt:new Date().toISOString(),cached:false,provider:'DeepSeek',model:'test',result:'*',scope:'game',completeCoverage:true,
        references:[{ply:4,label:'3. Qxe5+'}],commentary:{summary:'Una svolta da rivedere.',course:'La cattura cambia il corso della partita.',strengths:[],
          focus:[{title:'Verifica le risposte',explanation:'La risposta avversaria è decisiva.',plies:[4],kind:'tactical',practice:'Confronta due alternative per 5 minuti.'}],uncertainty:'Analisi a budget limitato.'}}
    }
    await r.fulfill({json:saved})
  })
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('tab',{name:'Commento finale',exact:true}).click()
  const panel=page.getByRole('region',{name:'Commento finale della partita'})
  await expect(panel.getByRole('button',{name:'Genera commento finale'})).toBeEnabled()
  expect(calls).toBe(0)
  await panel.getByRole('button',{name:'Genera commento finale'}).click()
  await expect(panel).toContainText('Una svolta da rivedere.')
  await expect(panel).toContainText('provvisorio')
  await panel.getByRole('button',{name:'Rivedi 3. Qxe5+ ↗',exact:true}).click()
  await expect(page.getByRole('tab',{name:'Mosse',exact:true})).toHaveAttribute('aria-selected','true')
  await expect(page.getByRole('combobox',{name:'Mossa da confrontare'})).toHaveValue('4')
  await page.reload()
  await page.getByRole('tab',{name:'Commento finale',exact:true}).click()
  await expect(panel).toContainText('Una svolta da rivedere.')
  expect(calls).toBe(1)
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})
