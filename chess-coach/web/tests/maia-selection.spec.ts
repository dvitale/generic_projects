import {test,expect} from '@playwright/test'

test('Play fixes the chosen Maia move selection for the new game and remembers it for the next one',async({page,request})=>{
  await page.goto('/')
  const setup=page.locator('.play-setup')
  const group=setup.getByRole('group',{name:'Scelta delle mosse di Maia'})
  await expect(group.getByRole('button',{name:'Completa'})).toHaveAttribute('aria-pressed','true')
  await group.getByRole('button',{name:'Solida'}).click()
  await expect(setup).toContainText('Temperatura 0,4 e top-p 0,8')
  await setup.getByRole('button',{name:'Nero',exact:true}).click()
  await setup.getByRole('button',{name:'Inizia partita →'}).click()
  await expect(page.locator('.current-opponent')).toContainText('Maia · livello 600 · scelta Solida')
  await expect(page.getByText('Tocca a te',{exact:false})).toBeVisible({timeout:30000})
  const id=(await(await request.get('/api/games')).json())[0].id
  const game=await(await request.get('/api/games/'+id)).json()
  expect(game).toMatchObject({moveSelection:'temperature-0.4-top-p-0.8',moves:[expect.any(String)]})
  expect(game.pgn).toContain('[MoveSelection "temperature-0.4-top-p-0.8"]')
  await page.reload()
  await expect(page.locator('.play-setup').getByRole('group',{name:'Scelta delle mosse di Maia'}).getByRole('button',{name:'Solida'})).toHaveAttribute('aria-pressed','true')
})
