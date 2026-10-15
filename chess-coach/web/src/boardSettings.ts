import {useSyncExternalStore} from 'react'

export type BoardTheme='green'|'brown'|'blue'
export type BoardSettings={theme:BoardTheme;sound:boolean}
export const boardThemes:{id:BoardTheme;label:string}[]=[{id:'green',label:'Verde'},{id:'brown',label:'Legno'},{id:'blue',label:'Blu'}]

const storageKey='sparringmate-board'
const defaults:BoardSettings={theme:'green',sound:true}
const listeners=new Set<()=>void>()
let current=read()

function read():BoardSettings{
  try{
    const saved=JSON.parse(localStorage.getItem(storageKey)||'{}')
    return {theme:boardThemes.some(t=>t.id===saved.theme)?saved.theme:defaults.theme,sound:typeof saved.sound==='boolean'?saved.sound:defaults.sound}
  }catch{return defaults}
}

export function updateBoardSettings(change:Partial<BoardSettings>){
  current={...current,...change}
  try{localStorage.setItem(storageKey,JSON.stringify(current))}catch{/* Preferences stay in memory. */}
  listeners.forEach(listener=>listener())
}

export function boardSettings(){return current}

export function useBoardSettings(){
  return useSyncExternalStore(listener=>{listeners.add(listener);return()=>listeners.delete(listener)},()=>current)
}
