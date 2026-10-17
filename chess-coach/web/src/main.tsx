import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import AuthGate from './Login'
import '@fontsource-variable/inter'
import '@fontsource-variable/fraunces'
import './style.css'
createRoot(document.getElementById('root')!).render(<AuthGate>{logout => <App onLogout={logout} />}</AuthGate>)
