import {test,expect} from '@playwright/test'
import {readFileSync} from 'node:fs'
const mapping=JSON.parse(readFileSync(new URL('../src/engine/data/all_moves_maia3.json',import.meta.url),'utf8'))

test('Puzzle feedback distinguishes retry, success and reveal and advances without repeating completed puzzles',async({page,request})=>{
  await page.addInitScript(({index})=>{
    ;(window as any).puzzlePredictions=[]
    ;(window as any).Worker=class {
      onmessage:any
      postMessage(message:any){
        setTimeout(()=>{
          if(message.type==='init')this.onmessage?.({data:{type:'status',status:'ready'}})
          if(message.type==='inference'){
            ;(window as any).puzzlePredictions.push(new Float32Array(message.eloSelfs)[0])
            const logitsMove=new Float32Array(4352);logitsMove[index]=20
            this.onmessage?.({data:{type:'inference-result',id:message.id,logitsMove:logitsMove.buffer,logitsValue:new Float32Array(3).buffer}})
          }
        },0)
      }
      terminate(){}
    }
  },{index:mapping.g6g7})
  const ids:string[]=[]
  for(let i=0;i<2;i++){
    const game=await(await request.post('/api/games',{data:{elo:600,fen:'7k/8/5KQ1/8/8/8/8/8 w - - 0 1'}})).json()
    await request.post(`/api/games/${game.id}/moves`,{data:{move:'g6g8',version:0,revision:0,actor:'human'}})
    const job=await(await request.post(`/api/games/${game.id}/analysis`,{data:{}})).json()
    await expect.poll(async()=>(await(await request.get('/api/jobs/'+job.jobId)).json()).status,{timeout:30000}).toBe('complete')
    ids.push(game.id)
  }
  await page.route('**/api/exercises',async route=>{
    const response=await route.fetch()
    const exercises=await response.json()
    await route.fulfill({json:exercises.filter((ex:{gameId:string})=>ids.includes(ex.gameId))})
  })
  const sessions:string[]=[]
  page.on('request',req=>{if(req.method()==='POST'&&/\/exercises\/[^/]+\/sessions$/.test(req.url()))sessions.push(req.url())})
  await page.goto('/')
  await page.getByRole('button',{name:/^Puzzle/}).click()
  const feedback=page.getByRole('region',{name:'Esito del puzzle'})
  await expect(feedback).toContainText('Trova una buona mossa')
  await expect(page.locator('.analysis-arrow')).toHaveCount(0)
  expect(await page.evaluate(()=>(window as any).puzzlePredictions)).toEqual([])
  await page.locator('[data-square="g6"]').click()
  await page.locator('[data-square="g8"]').click()
  await expect(page.locator('[data-square="g8"] img')).toBeVisible()
  await expect(feedback).toContainText('Osserva la mossa:')
  await expect(feedback).toContainText('La scacchiera è tornata alla posizione iniziale',{timeout:30000})
  await expect(page.getByRole('region',{name:'Tentativi sbagliati'})).toContainText('Qg8+')
  await expect(feedback.getByRole('button',{name:'Prossimo puzzle'})).toHaveCount(0)
  await expect(page.locator('[data-square="g6"] img')).toBeVisible()
  await page.setViewportSize({width:390,height:844})
  await page.locator('[data-square="g6"]').click()
  await page.locator('[data-square="g7"]').click()
  await expect(feedback).toContainText('Mossa corretta!',{timeout:30000})
  await expect(feedback.getByRole('button',{name:'Prossimo puzzle'})).toBeInViewport()
  await expect(page.locator('[data-square="g7"] img')).toBeVisible()
  await expect(page.locator('[data-square="g6"] img')).toHaveCount(0)
  await expect(page.locator('.analysis-arrow[data-source="played"]')).toHaveAttribute('data-move','g6g8')
  await expect(page.locator('.analysis-arrow[data-source="maia"]')).toHaveAttribute('data-move','g6g7')
  await expect(page.locator('.analysis-arrow')).toHaveCount(2)
  await expect(page.locator('[data-square="g6"] img')).toBeVisible()
  expect(await page.evaluate(()=>(window as any).puzzlePredictions)).toEqual([600])
  await expect(feedback).toContainText('resta nella lista')
  await expect(page.locator('.exercise-list button')).toHaveCount(2)
  await page.getByRole('button',{name:'Mostra la tua soluzione',exact:true}).click()
  await expect(page.locator('[data-square="g7"] img')).toBeVisible()
  await expect(page.locator('.analysis-arrow')).toHaveCount(0)
  const next=feedback.getByRole('button',{name:'Prossimo puzzle'})
  await expect(next).toBeEnabled()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:'test-results/puzzle-correct-mobile.png',fullPage:true})
  await next.click()
  await expect(feedback).toContainText('Trova una buona mossa')
  await expect(page.locator('.analysis-arrow')).toHaveCount(0)
  expect(sessions).toHaveLength(2)
  expect(sessions[0]).not.toBe(sessions[1])
  await expect(page.locator('[data-square="g6"] img')).toBeVisible()
  await page.getByRole('button',{name:'Mostra soluzione',exact:true}).click()
  await expect(feedback).toContainText('Soluzione mostrata')
  await expect(feedback).not.toContainText('Mossa corretta!')
  await expect(feedback).toContainText('Non ci sono altri puzzle')
  await expect(next).toHaveCount(0)
  await feedback.getByRole('button',{name:'Ricomincia gli esercizi'}).click()
  await expect(feedback).toContainText('Trova una buona mossa')
  await expect(feedback).not.toContainText('Non ci sono altri puzzle')
  expect(sessions).toHaveLength(3)
  await page.locator('[data-square="g6"]').click()
  await page.locator('[data-square="g7"]').click()
  await expect(feedback).toContainText('tolto dai puzzle da ripassare')
  await expect(page.locator('.exercise-list button')).toHaveCount(1)
  await page.reload()
  await page.getByRole('button',{name:/^Puzzle/}).click()
  await expect(page.locator('.exercise-list button')).toHaveCount(1)
  await expect(page.locator('.analysis-arrow')).toHaveCount(0)
})
