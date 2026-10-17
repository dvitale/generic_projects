import {useEffect,useState,type ReactNode} from 'react'
import {api,UNAUTHORIZED} from './api'

interface Session {required:boolean;authenticated:boolean;user:string|null}

function LoginForm({onLogin}:{onLogin:(s:Session)=>void}){
  const [username,setUsername]=useState('')
  const [password,setPassword]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  async function submit(){
    setBusy(true);setError('')
    try{onLogin(await api<Session>('/auth/login',{username,password}))}
    catch(e){setError(e instanceof Error?e.message:'Accesso non riuscito');setPassword('')}
    finally{setBusy(false)}
  }
  return <main className="login-page">
    <form className="panel login-card" aria-labelledby="login-title" onSubmit={e=>{e.preventDefault();void submit()}}>
      <div className="login-brand"><span className="brand-mark" aria-hidden="true">♞</span><span>Sparring<span className="brand-light">Mate</span></span></div>
      <h1 id="login-title">Accedi</h1>
      <p className="muted">Inserisci le credenziali configurate per questo spazio di allenamento.</p>
      <label htmlFor="login-user" className="field-label">Nome utente</label>
      <input id="login-user" type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus value={username} onChange={e=>setUsername(e.target.value)}/>
      <label htmlFor="login-password" className="field-label">Password</label>
      <input id="login-password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/>
      {error&&<p role="alert" className="error-text">{error}</p>}
      <button className="primary full" disabled={busy||!username||!password}>{busy?'Accesso…':'Entra'}</button>
    </form>
  </main>
}

/** Shows the login screen when the server requires credentials, and again whenever a request returns 401. */
export default function AuthGate({children}:{children:(logout:(()=>void)|null)=>ReactNode}){
  const [session,setSession]=useState<Session|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{
    api<Session>('/auth/session').then(setSession).catch(e=>setError(e instanceof Error?e.message:'Server non raggiungibile'))
    const expired=()=>setSession(s=>s&&{...s,authenticated:false,user:null})
    window.addEventListener(UNAUTHORIZED,expired)
    return ()=>window.removeEventListener(UNAUTHORIZED,expired)
  },[])
  async function logout(){
    try{await api('/auth/logout',{})}finally{setSession(s=>s&&{...s,authenticated:false,user:null})}
  }
  if(error)return <main className="login-page"><p role="alert" className="alert">{error}</p></main>
  if(!session)return null
  if(!session.authenticated)return <LoginForm onLogin={setSession}/>
  return <>{children(session.required?()=>void logout():null)}</>
}
