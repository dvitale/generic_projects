import { defineConfig } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const data = mkdtempSync(join(tmpdir(),'chess-coach-e2e-'))
export default defineConfig({
  testDir:'./tests', workers:1, timeout:120000,
  use:{baseURL:'http://127.0.0.1:8011',headless:true,launchOptions:{executablePath:'/usr/bin/chromium',args:['--no-sandbox']},trace:'retain-on-failure'},
  // A stand-in for the experimental move service, so the Play selector is exercised end to end.
  webServer:[{command:'../.venv/bin/python ../tests/fixtures/fake_policy_service.py --port 8012',port:8012,reuseExistingServer:false},
  {command:`../.venv/bin/python ../scripts/import_lichess_puzzles.py --file ../tests/fixtures/lichess-puzzles.csv --per-band 5 --data ${data} >/dev/null && ../.venv/bin/python -m uvicorn backend.main:app --app-dir .. --host 127.0.0.1 --port 8011`,url:'http://127.0.0.1:8011/api/health',env:{CHESS_COACH_DATA:data,CHESS_COACH_DISABLE_LLM:'1',CHESS_COACH_DISABLE_AUTH:'1',SPARRINGMATE_EXPERIMENTAL_ENGINE:'http://127.0.0.1:8012'},reuseExistingServer:false}],
})
