const paths:Record<string,string>={
  schedule:'M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm4 9 2 2 4-4',
  play:'M9 20h6M8 17h8l-1-6h-6l-1 6ZM10 11c-1.5-1-2-2.5-1.3-4C9.5 5.3 11 4.5 12 4.5s2.5.8 3.3 2.5c.7 1.5.2 3-1.3 4',
  review:'M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14Zm5-2 4 4M8 11h6M11 8v6',
  drill:'M4 12a8 8 0 0 1 13.7-5.6L20 9M20 4v5h-5M20 12a8 8 0 0 1-13.7 5.6L4 15M4 20v-5h5',
  train:'M10 4h4v2a2 2 0 1 0 4 0V4h2v6h-2a2 2 0 1 0 0 4h2v6h-6v-2a2 2 0 1 0-4 0v2H4v-6h2a2 2 0 1 0 0-4H4V4h6Z',
  problems:'M13 3 5 14h6l-1 7 8-11h-6l1-7Z',
  visual:'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  lessons:'M4 5h5a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H4V5Zm16 0h-5a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h6V5ZM15 10l1.5 1.5L19 9',
  prevention:'M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3Zm-3 9 2 2 4-4',
  progress:'M4 19h16M6 15l4-4 3 3 6-7M15 7h4v4',
  archive:'M4 5h16v4H4zM5 9v10h14V9M10 13h4',
  study:'M12 6.5C10 5 7.5 4.5 4 4.5v13c3.5 0 6 .5 8 2 2-1.5 4.5-2 8-2v-13c-3.5 0-6 .5-8 2Zm0 0v13',
  alternative:'M4 12h6l3-6M13 6h7M10 12l3 6h7M4 12',
  more:'M5 12h.01M12 12h.01M19 12h.01',
  // Gear from Lucide (ISC licence).
  settings:'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
}

export default function Icon({name}:{name:keyof typeof paths|string}){
  return <svg className="icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
    <path d={paths[name]} fill="none" stroke="currentColor" strokeWidth={name==='more'?3:1.8} strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
}
