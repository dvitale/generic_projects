import {test,expect} from '@playwright/test'
import {Chess} from 'chess.js'
import {evaluationSeries,evaluationText} from '../src/evaluationSeries'
import type {Game,Decision,Evaluation} from '../src/types'

function fixture(sans:string[],initialFen?:string){
  const board=new Chess(initialFen),moves:string[]=[],rows:Decision[]=[]
  const first=board.fen()
  sans.forEach((san,ply)=>{
    const fen=board.fen(),side=board.turn(),move=board.move(san)
    const played=move.from+move.to+(move.promotion??'')
    const actual:Evaluation={cp:side==='w'?100:-150,mate:null,pv:[played],san:[san],perspective:side,depth:15,nodes:10000}
    moves.push(played)
    rows.push({ply,fen,played,playedSan:san,best:{...actual,cp:20},actual,loss:0,theme:'test',label:'test'})
  })
  return {initialFen:first,moves,analysis:{moves:rows,decisions:rows.filter(r=>r.actual.perspective==='w')}} as Game
}

test('scores keep White perspective on both turns and preserve initial evaluation',()=>{
  const game=fixture(['e4','e5','Nf3','Nc6'])
  game.analysis!.moves![3].actual.cp=200
  expect(evaluationSeries(game).points.map(p=>p.cp)).toEqual([20,100,150,100,-200])
  expect(evaluationSeries(game).complete).toBe(true)
  expect(evaluationText(evaluationSeries(game).points[2])).toBe('+1,50')
})

test('mates and terminal draws do not become enormous numeric values',()=>{
  const game=fixture(['f3','e5','g4','Qh4#'])
  game.analysis!.moves![2].actual={...game.analysis!.moves![2].actual,cp:-100000,mate:-1}
  const points=evaluationSeries(game).points
  expect(points.at(-2)).toMatchObject({cp:null,mate:'b',terminal:false})
  expect(points.at(-1)).toMatchObject({cp:null,mate:'b',terminal:true})
  expect(evaluationText(points.at(-1)!)).toBe('Scacco matto · Nero')
  const draw=evaluationSeries(fixture(['Qf7'],'7k/8/5KQ1/8/8/8/8/8 w - - 0 1')).points.at(-1)!
  expect(draw).toMatchObject({cp:0,mate:null,terminal:true})
  expect(evaluationText(draw)).toBe('Patta · 0,00')
})

test('custom Black starts, drill prefixes and sparse archives keep correct positions',()=>{
  const custom=fixture(['e5','Nf3'],'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 17')
  expect(evaluationSeries(custom).points.map(p=>p.label)).toEqual(['Posizione iniziale','17… e5','18. Nf3'])
  expect(evaluationSeries(custom).points[0].cp).toBe(-20)
  const game=fixture(['e4','e5','Nf3','Nc6'])
  game.analysis!.moves=game.analysis!.moves!.slice(2)
  expect(evaluationSeries(game)).toMatchObject({start:2,complete:true})
  expect(evaluationSeries(game).points.map(p=>p.position)).toEqual([2,3,4])
  game.analysis!.moves=undefined
  expect(evaluationSeries(game).complete).toBe(false)
  expect(evaluationSeries(game).points.map(p=>p.position)).toEqual([0,1,3])
})

test('analyze from chart, navigate board and keep compact responsive layout',async({page,request})=>{
  const game=await(await request.post('/api/import',{data:{pgn:'1. e4 e5 2. Qh5 Nc6 3. Qxe5+ Nxe5 *',color:'w'}})).json()
  await page.addInitScript(id=>localStorage.setItem('chess-coach-game',id),game.id)
  await page.goto('/')
  await page.getByRole('button',{name:'Rivedi',exact:true}).click()
  await page.getByRole('tab',{name:'Andamento',exact:true}).click()
  await page.getByRole('button',{name:'Calcola andamento',exact:true}).click()
  const chart=page.getByRole('region',{name:'Andamento della valutazione'})
  await expect(chart.locator('svg')).toBeVisible({timeout:60000})
  await expect(chart.locator('[data-position]')).toHaveCount(7)
  const analyzed=await(await request.get('/api/games/'+game.id)).json()
  for(const row of analyzed.analysis.moves){
    await expect(chart.locator(`[data-position="${row.ply+1}"]`)).toHaveAttribute('data-score',String(row.actual.cp*(row.actual.perspective==='w'?1:-1)))
  }
  await chart.getByLabel('Posizione sul grafico').selectOption('5')
  await expect(page.locator('[data-square="e5"]')).toHaveAttribute('aria-label',/donna.*bianco/i)
  await chart.locator('svg').focus()
  await chart.locator('svg').press('End')
  await expect(chart.getByLabel('Posizione sul grafico')).toHaveValue('6')
  await expect(page.locator('[data-square="e5"]')).toHaveAttribute('aria-label',/cavallo.*nero/i)
  await chart.locator('[data-position="1"] circle').click({force:true})
  await expect(chart.getByLabel('Posizione sul grafico')).toHaveValue('1')
  await expect(page.locator('[data-square="e4"] img')).toBeVisible()
  await page.setViewportSize({width:1920,height:1080})
  const board=await page.locator('.board').boundingBox(),panel=await chart.boundingBox()
  expect(board!.x+board!.width).toBeLessThan(panel!.x)
  expect(panel!.y+panel!.height).toBeLessThan(1080)
  await page.screenshot({path:'test-results/evaluation-wide.png',fullPage:true})
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await chart.scrollIntoViewIfNeeded()
  await page.screenshot({path:'test-results/evaluation-mobile.png',fullPage:true})
  await chart.getByText('Tutte le valutazioni',{exact:true}).click()
  await expect(chart.locator('tbody tr')).toHaveCount(7)
  await chart.getByRole('button',{name:'Rivedi Posizione iniziale',exact:true}).click()
  await expect(chart.getByLabel('Posizione sul grafico')).toHaveValue('0')
})
