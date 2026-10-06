export default function ExerciseSource({title,createdAt,fen,onReview,disabled=false}:{title?:string;createdAt?:string;fen:string;onReview:()=>void;disabled?:boolean}){
  const fields=fen.split(' ')
  const date=createdAt?new Date(createdAt):null
  return <section className="panel exercise-source" aria-label="Partita di origine">
    <span className="eyebrow">DALLA TUA PARTITA</span>
    <h3>{title||'Partita salvata'}</h3>
    <p className="footnote">{date&&!Number.isNaN(date.getTime())&&<>{date.toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'})} · </>}Mossa {fields[5]}{fields[1]==='b'?'…':'.'} · {fields[1]==='b'?'Nero':'Bianco'}</p>
    <button onClick={onReview} disabled={disabled}>Rivedi questa mossa nella partita</button>
  </section>
}
