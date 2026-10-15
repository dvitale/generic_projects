/** Horizontal bars for counts: the longest bar is the largest group. */
export default function BarList({items,unit='posizioni'}:{items:{key:string;label:string;value:number}[];unit?:string}){
  const max=Math.max(1,...items.map(i=>i.value))
  return <ul className="bar-list">{items.map(i=><li key={i.key}>
    <div className="bar-label"><span>{i.label}</span><b>{i.value} <small>{unit}</small></b></div>
    <div className="bar-track" aria-hidden="true"><span style={{width:`${Math.max(3,100*i.value/max)}%`}}/></div>
  </li>)}</ul>
}
