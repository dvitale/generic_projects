import {test,expect} from '@playwright/test'

test('the page links the SparringMate icons and they are served',async({page,request})=>{
  await page.goto('/')
  const links=await page.locator('link[rel="icon"],link[rel="apple-touch-icon"],link[rel="manifest"]').evaluateAll(l=>l.map(e=>e.getAttribute('href')))
  expect(links).toEqual(['/favicon.ico','/icon-192.png','/apple-touch-icon.png','/manifest.webmanifest'])
  for(const href of links){const r=await request.get(href!);expect(r.status(),href!).toBe(200)}
  const manifest=await(await request.get('/manifest.webmanifest')).json()
  expect(manifest.icons.map((i:{sizes:string})=>i.sizes)).toEqual(['192x192','512x512'])
})
