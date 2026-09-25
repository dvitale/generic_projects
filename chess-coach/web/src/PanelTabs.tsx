export default function PanelTabs({id,label,items,value,onChange}:{id:string;label:string;items:{id:string;label:string}[];value:string;onChange:(value:string)=>void}) {
  return <div className="panel-tabs" role="tablist" aria-label={label}>{items.map((item,index)=><button
    key={item.id} id={`${id}-tab-${item.id}`} role="tab" aria-selected={value===item.id}
    aria-controls={`${id}-panel-${item.id}`} tabIndex={value===item.id?0:-1}
    onClick={()=>onChange(item.id)} onKeyDown={event=>{
      const next=event.key==='ArrowRight'?(index+1)%items.length:event.key==='ArrowLeft'?(index+items.length-1)%items.length:event.key==='Home'?0:event.key==='End'?items.length-1:-1
      if(next<0)return
      event.preventDefault();onChange(items[next].id)
      document.getElementById(`${id}-tab-${items[next].id}`)?.focus()
    }}>{item.label}</button>)}</div>
}
