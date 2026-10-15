import type {ReactNode} from 'react'

/** Methodology and limits on demand: one line stays visible, the details open on request. */
export default function InfoNote({summary='Come si calcola',children}:{summary?:string;children:ReactNode}){
  return <details className="info-note"><summary><span aria-hidden="true">ⓘ</span> {summary}</summary><div className="info-note-body">{children}</div></details>
}
