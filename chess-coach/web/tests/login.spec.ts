import {test,expect} from '@playwright/test'

// The e2e server runs without credentials, so the session API is simulated here; tests/test_auth.py covers the server.
test('The login screen guards the app and logout returns to it',async({page})=>{
  let authenticated=false
  await page.route('**/api/auth/session',route=>route.fulfill({json:{required:true,authenticated,user:authenticated?'dante':null}}))
  await page.route('**/api/auth/login',route=>{
    const body=route.request().postDataJSON()
    if(body.password!=='giusta')return route.fulfill({status:401,json:{detail:'Nome utente o password non corretti.'}})
    authenticated=true;return route.fulfill({json:{required:true,authenticated:true,user:'dante'}})
  })
  await page.route('**/api/auth/logout',route=>{authenticated=false;route.fulfill({json:{authenticated:false}})})
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Accedi'})).toBeVisible()
  await expect(page.getByRole('navigation',{name:'Navigazione principale'})).toHaveCount(0)
  await page.getByLabel('Nome utente').fill('dante')
  await page.getByLabel('Password').fill('sbagliata')
  await page.getByRole('button',{name:'Entra'}).click()
  await expect(page.getByRole('alert')).toContainText('non corretti')
  await expect(page.getByLabel('Password')).toHaveValue('')
  await page.screenshot({path:'test-results/login.png'})
  await page.getByLabel('Password').fill('giusta')
  await page.getByRole('button',{name:'Entra'}).click()
  await expect(page.getByRole('navigation',{name:'Navigazione principale'})).toBeVisible()
  await page.getByRole('button',{name:'Esci'}).click()
  await expect(page.getByRole('heading',{name:'Accedi'})).toBeVisible()
})

test('An expired session brings back the login screen',async({page})=>{
  await page.route('**/api/auth/session',route=>route.fulfill({json:{required:true,authenticated:true,user:'dante'}}))
  await page.route('**/api/profile**',route=>route.fulfill({status:401,json:{detail:'Accesso richiesto'}}))
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Accedi'})).toBeVisible()
})
