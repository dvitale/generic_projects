import { defineConfig } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const data = mkdtempSync(join(tmpdir(),'chess-coach-e2e-'))
export default defineConfig({
  testDir:'./tests', workers:1, timeout:120000,
  use:{baseURL:'http://127.0.0.1:8011',headless:true,launchOptions:{executablePath:'/usr/bin/chromium',args:['--no-sandbox']},trace:'retain-on-failure'},
  webServer:{command:'../.venv/bin/python -m uvicorn backend.main:app --app-dir .. --host 127.0.0.1 --port 8011',url:'http://127.0.0.1:8011/api/health',env:{CHESS_COACH_DATA:data,CHESS_COACH_DISABLE_LLM:'1'},reuseExistingServer:false},
})
