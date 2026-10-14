import {test,expect} from '@playwright/test'
import {Chess} from 'chess.js'

const cases=[
  {name:'capture',fen:'6rk/8/5KQ1/8/8/8/8/8 w - - 0 1',move:'g6g8',piece:'donna bianco',restored:'g8'},
  {name:'castling',fen:'4k3/8/8/8/8/8/8/4K2R w K - 0 1',move:'e1g1',piece:'re bianco',rook:true},
  {name:'en passant',fen:'7k/8/8/3pP3/8/8/8/K7 w - d6 0 1',move:'e5d6',piece:'pedone bianco',restored:'d5'},
  {name:'promotion capture',fen:'k6r/6P1/8/8/8/8/8/K7 w - - 0 1',move:'g7h8q',piece:'pedone bianco',restored:'h8'},
  {name:'black capture',fen:'8/8/8/8/8/5kq1/8/6RK b - - 0 1',move:'g3g1',piece:'donna nero',restored:'g1'},
]
for(const c of cases)test(`wrong ${c.name} is visible before a slow, complete undo`,async({page})=>{
  const p={id:'animation',gameId:'none',title:'Test animazione',ply:0,fen:c.fen,turn:c.name==='black capture'?'b':'w',moveNumber:1,legalMoves:[c.move,...(c.move.endsWith('q')?[c.move.slice(0,4)+'n']:[])],dueAt:'2026-01-01',streak:0}
  await page.route('**/api/prevention',route=>route.fulfill({json:{positions:[p],stats:{firstAttempts:0,firstSuccesses:0},analyzedGames:1,rule:{description:'Test'}}}))
  await page.route('**/api/prevention/animation/sessions',route=>route.fulfill({json:{id:'s',version:0,exposure:'new'}}))
  let calls=0
  await page.route('**/api/prevention/animation/attempts',async route=>{
    calls++;await new Promise(resolve=>setTimeout(resolve,400))
    await route.fulfill({json:{success:false,closed:false,version:1,move:c.move,san:'Test',actual:{cp:-300,mate:null,pv:[c.move],san:['Test']},message:'Errore di prova'}})
  })
  await page.goto('/');await page.getByRole('button',{name:'Blunder prevention',exact:false}).click()
  await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await expect(page.getByRole('heading',{name:'Evita il blunder',exact:true})).toBeVisible()
  const from=c.move.slice(0,2),to=c.move.slice(2,4)
  await page.locator(`[data-square="${from}"]`).click();await page.locator(`[data-square="${to}"]`).click()
  if(c.move.endsWith('q'))await page.getByRole('dialog',{name:'Scegli la promozione'}).getByRole('button',{name:'donna',exact:true}).click()
  await expect(page.locator(`[data-square="${from}"] img`)).toHaveCount(0)
  await expect(page.locator(`[data-square="${to}"] img`)).toBeVisible()
  if(c.rook)await expect(page.locator('[data-square="f1"] img')).toBeVisible()
  await expect(page.getByText('Osserva la mossa:',{exact:false})).toBeVisible()
  await page.locator(`[data-square="${from}"]`).click();await page.locator(`[data-square="${to}"]`).click()
  await expect(page.getByText('Ritorno alla posizione iniziale…',{exact:true})).toBeVisible()
  expect(await page.evaluate(()=>document.getAnimations().some(a=>a.effect?.getTiming().duration===650))).toBe(true)
  await expect(page.getByRole('heading',{name:'↻ Riprova una mossa diversa'})).toBeVisible()
  await expect(page.locator(`[data-square="${from}"]`)).toHaveAttribute('aria-label',`${from} ${c.piece}`)
  if(c.restored)await expect(page.locator(`[data-square="${c.restored}"] img`)).toBeVisible()
  if(c.rook){await expect(page.locator('[data-square="h1"] img')).toBeVisible();await expect(page.locator('[data-square="f1"] img')).toHaveCount(0)}
  expect(calls).toBe(1)
})

test('an explanation can be opened, hidden and reopened without another provider request',async({page})=>{
  await page.route('**/api/prevention',route=>route.fulfill({json:{positions:[{id:'explain',fen:'r6k/8/5KQ1/8/8/8/8/8 w - - 0 1',turn:'w',legalMoves:['g6g7'],title:'Posizione',moveNumber:1}],stats:{firstAttempts:1,firstSuccesses:0},rule:{description:'Test'}}}))
  await page.route('**/api/prevention/explain/sessions',route=>route.fulfill({json:{id:'session',version:1,exposure:'new'}}))
  await page.route('**/api/training/prevention/explain/mistakes',route=>route.fulfill({json:[{id:1,san:'Qg8+',createdAt:'2026-09-30T10:00:00Z',lossCp:400,reference:{cp:80,mate:null},actual:{cp:-320,mate:null,san:['Qg8+','Kxg8']}}]}))
  let calls=0
  await page.route('**/api/training/prevention/explain/mistakes/1/explain',route=>{calls++;return route.fulfill({json:{explanation:{reason:'La donna rimane in presa.',continuation:'Il re può catturarla.',lesson:'Controlla le catture avversarie.'},provider:'DeepSeek',cached:false}})})
  await page.goto('/');await page.getByRole('button',{name:'Blunder prevention',exact:false}).click();await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await expect(page.getByText('Calo 4.00 punti')).toBeVisible();expect(calls).toBe(0)
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click();await expect(page.getByText('La donna rimane in presa.')).toBeVisible()
  await page.getByRole('button',{name:'Nascondi spiegazione'}).click();await expect(page.getByText('La donna rimane in presa.')).toHaveCount(0)
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click();await expect(page.getByText('La donna rimane in presa.')).toBeVisible();expect(calls).toBe(1)
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})

test('comparison replays why Qh2 is mate after Qb1 but only check after Rg1',async({page})=>{
  const fen='2k4r/p6q/1pp1p3/8/P2P1N2/2P2Pp1/1P3nK1/R1Q2R2 w - - 1 28'
  const line=(pv:string[],cp:number,mate:number|null)=>{
    const board=new Chess(fen)
    const steps=pv.map(uci=>{const side=board.turn(),number=Number(board.fen().split(' ')[5]);const move=board.move(uci);return {uci,san:move.san,side,number,fen:board.fen(),checkmate:board.isCheckmate()}})
    return {pv,cp,mate,san:steps.map(s=>s.san),steps,depth:18,nodes:320000,perspective:'w'}
  }
  const actual=line(['c1b1','h7h2'],-99999,-1),best=line(['f1g1','f2d3'],0,null),same=line(['f1g1','h7h2','g2f1'],260,null)
  await page.route('**/api/prevention',route=>route.fulfill({json:{positions:[{id:'contrast',fen,turn:'w',legalMoves:['f1g1'],title:'Rg1',moveNumber:28}],stats:{firstAttempts:1,firstSuccesses:0},rule:{description:'Test'}}}))
  await page.route('**/api/prevention/contrast/sessions',route=>route.fulfill({json:{id:'s',version:1,exposure:'new'}}))
  await page.route('**/api/training/prevention/contrast/mistakes',route=>route.fulfill({json:[{id:1,san:'Qb1',createdAt:'2026-10-13T14:00:00Z',lossCp:null,reference:{cp:0,mate:null},actual}]}))
  let calls=0
  await page.route('**/api/training/prevention/contrast/mistakes/1/explain',route=>{
    calls++;return route.fulfill({json:{cached:false,provider:'DeepSeek',explanation:{reason:'Qb1 permette Qh2 matto.',sharedIdea:'Sono mosse senza scacco.',difference:'Rg1 libera f1 per il re.',alternative:'Dopo Qh2+ esiste Kf1.',continuation:'Confronta la stessa risposta.',lesson:'Prima cerca le minacce di matto.'},comparison:{fen,turn:'w',actual,best,lossCp:null,criterion:'Mantieni almeno −1,00.',verification:{acceptedNow:false,note:'Ricerca limitata.'},sameReply:{attemptReply:'Qh2#',alternativeReply:'Qh2+',legalAfterAlternative:true,line:same}}}})
  })
  await page.goto('/');await page.getByRole('button',{name:'Blunder prevention',exact:false}).click();await page.getByRole('button',{name:'Inizia Blunder prevention'}).click()
  await page.getByRole('button',{name:'Spiega motivo',exact:true}).click()
  await expect(page.getByText('Rg1 libera f1 per il re.',{exact:false})).toBeVisible()
  const comparison=page.getByRole('region',{name:'Confronto verificato delle mosse'})
  await expect(comparison.getByText('Matto contro in 1',{exact:true})).toBeVisible()
  await expect(comparison.getByText('+0.00',{exact:true})).toBeVisible()
  await comparison.getByText('Rivedi le due idee sulla scacchiera',{exact:true}).click()
  await comparison.getByRole('button',{name:'Passo successivo del confronto'}).click()
  await comparison.getByRole('button',{name:'Passo successivo del confronto'}).click()
  await expect(comparison.getByText('Scacco matto in questa variante.',{exact:true})).toBeVisible()
  await comparison.getByRole('button',{name:'Stessa risposta avversaria',exact:true}).click()
  await expect(comparison.locator('[data-square="f1"]')).toHaveAttribute('aria-label','f1 torre bianco')
  for(let i=0;i<3;i++)await comparison.getByRole('button',{name:'Passo successivo del confronto'}).click()
  await expect(comparison.locator('[data-square="f1"]')).toHaveAttribute('aria-label','f1 re bianco')
  await expect(comparison.locator('[data-square="g1"]')).toHaveAttribute('aria-label','g1 torre bianco')
  await expect(comparison.getByText('Scacco matto in questa variante.',{exact:true})).toHaveCount(0)
  await comparison.getByRole('button',{name:'Alternativa Stockfish',exact:true}).click()
  await expect(comparison.getByText('Prima della scelta',{exact:true})).toBeVisible()
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.getByRole('button',{name:'Nascondi spiegazione'}).click();await page.getByRole('button',{name:'Spiega motivo',exact:true}).click();expect(calls).toBe(1)
})
