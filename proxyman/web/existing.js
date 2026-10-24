let guidedModel=null,guidedStep=1,guidedWorking=false,guidedPreview=null,guidedSnapshot=null;
const guidedReaders=new Map();
let guidedNewRoutes=[];
function guidedMessage(text,error=true){$('#guided-message').textContent=text;$('#guided-message').className=error?'error':''}
function guidedSetWorking(value){
 guidedWorking=value;
 $('#guided-close').disabled=value;$('#guided-back').disabled=value;$('#guided-next').disabled=value;
 $('#guided-apply').disabled=value||!guidedPreview||!guidedModel?.live||!guidedPreview.changes.length;
 for(const el of $('#guided-form').querySelectorAll('input,select,textarea'))el.disabled=value||el.dataset.locked==='1';
}
function guidedLabel(text,input){
 const label=document.createElement('label');label.append(document.createTextNode(text));label.append(input);return label;
}
function guidedText(value,type='text'){const input=document.createElement('input');input.type=type;input.value=value;return input}
function guidedInput(field){
 const wrap=document.createElement('div');wrap.className='guided-field';
 let dirty=false,getValue;
 const changed=()=>{dirty=true;guidedPreview=null;$('#guided-apply').disabled=true};
 wrap.addEventListener('input',changed);wrap.addEventListener('change',changed);
 if(field.ReadOnly||field.readOnly){
  const input=guidedText(field.value);input.disabled=true;input.dataset.locked='1';wrap.append(guidedLabel(field.label,input));getValue=()=>field.value;
 }else if(field.kind==='listen'&&/^(?:\[[^\]]+\]:|[^\s:]+:)?\d+(?:\s.*)?$/.test(field.value||'80')){
  const tokens=(field.value||'80').trim().split(/\s+/);const endpoint=tokens.shift();const colon=endpoint.lastIndexOf(':');
  const address=guidedText(colon<0?'':endpoint.slice(0,colon));address.placeholder='Tutte le interfacce';
  const port=guidedText(colon<0?endpoint:endpoint.slice(colon+1),'number');port.min=1;port.max=65535;
  const tls=document.createElement('input');tls.type='checkbox';tls.checked=tokens.includes('ssl');
  const grid=document.createElement('div');grid.className='guided-listener';
  grid.append(guidedLabel('Indirizzo di ascolto',address),guidedLabel('Porta',port));
  const check=guidedLabel('Usa TLS (HTTPS)',tls);check.className='guided-check';grid.append(check);wrap.append(grid);
  const opts=document.createElement('small');opts.textContent='Altre opzioni conservate: '+(tokens.filter(v=>v!=='ssl').join(' ')||'nessuna');wrap.append(opts);
  getValue=()=>{let host=address.value.trim();if(host.includes(':')&&!host.startsWith('['))host='['+host+']';let options=tokens.filter(v=>v!=='ssl'||tls.checked);if(tls.checked&&!options.includes('ssl'))options.push('ssl');return [(host?host+':':'')+port.value,...options].join(' ')};
 }else if(field.kind==='destination'&&/^(https?):\/\/(\[[^\]]+\]|[^/:]+)(?::(\d+))?(.*)$/.test(field.value)){
  const parts=field.value.match(/^(https?):\/\/(\[[^\]]+\]|[^/:]+)(?::(\d+))?(.*)$/);
  const scheme=document.createElement('select');for(const v of ['http','https'])scheme.add(new Option(v,v));scheme.value=parts[1];
  const host=guidedText(parts[2].replace(/^\[|\]$/g,''));const port=guidedText(parts[3]||'','number');port.min=1;port.max=65535;port.placeholder='Predefinita';
  const path=guidedText(parts[4]||'');path.placeholder='Nessun percorso aggiunto';
  const grid=document.createElement('div');grid.className='guided-destination';grid.append(guidedLabel('Protocollo',scheme),guidedLabel('Host, IP o gruppo upstream',host),guidedLabel('Porta',port));wrap.append(grid,guidedLabel('Percorso sul servizio (barra finale inclusa)',path));
  getValue=()=>{let h=host.value.trim();if(h.includes(':')&&!h.startsWith('['))h='['+h+']';return scheme.value+'://'+h+(port.value?':'+port.value:'')+path.value.trim()};
 }else if(['upgrade','connection','httpversion'].includes(field.kind)){
  const select=document.createElement('select');let values=field.kind==='upgrade'?['','$http_upgrade']:field.kind==='connection'?['','upgrade','$connection_upgrade','close']:['','1.0','1.1','2'];
  if(!values.includes(field.value))values.push(field.value);
  for(const v of values)select.add(new Option(v||'Ereditato / non impostato',v));
  select.value=field.value;wrap.append(guidedLabel(field.label,select));getValue=()=>select.value;
 }else{
  const input=guidedText(field.value);if(field.kind==='duration')input.placeholder='Ereditato, oppure 60s';if(field.kind==='size')input.placeholder='Ereditato, oppure 20m';
  wrap.append(guidedLabel(field.label,input));getValue=()=>input.value;
 }
 const help=document.createElement('small');help.textContent=field.help||'';wrap.append(help);
 guidedReaders.set(field.id,()=>dirty?getValue():field.value);
 return wrap;
}
async function openGuided(proxy){
 if(busy||guidedWorking)return;
 busy=true;draw();guidedModel=null;guidedPreview=null;guidedSnapshot=null;guidedMessage('Caricamento del file originale…',false);
 $('#guided-dialog').showModal();$('#guided-fields').replaceChildren();$('#guided-summary').replaceChildren();$('#guided-apply').hidden=true;$('#guided-next').hidden=false;
 guidedSetWorking(true);
 try{
  guidedModel=await request('/api/existing/open',{file:proxy.file,line:proxy.line});
  guidedReaders.clear();guidedNewRoutes=[];guidedPreview=null;guidedSnapshot=null;
  $('#guided-file').textContent=guidedModel.file+':'+guidedModel.line;
  $('#guided-warning').textContent=guidedModel.warnings.join(' ');
  const groups=new Map();
  for(const field of guidedModel.fields){
   const key=field.step+':'+field.section;
   let group=groups.get(key);
   if(!group){group=document.createElement('section');group.className='guided-group';group.dataset.step=field.step;const heading=document.createElement('h3');heading.textContent=field.section;group.append(heading);groups.set(key,group);$('#guided-fields').append(group)}
   group.append(guidedInput(field));
  }
  const add=document.createElement('section');add.className='guided-group';add.dataset.step='2';
  const heading=document.createElement('h3');heading.textContent='Nuovi percorsi';add.append(heading);
  const list=document.createElement('div');list.id='guided-new-routes';add.append(list);
  const button=document.createElement('button');button.type='button';button.textContent='+ Aggiungi percorso';button.onclick=guidedAddRoute;add.append(button);$('#guided-fields').append(add);
  guidedMessage('',false);guidedShowStep(1);
 }catch(e){guidedMessage(e.message);$('#guided-next').disabled=true}
 finally{guidedSetWorking(false);busy=false;draw();if(!guidedModel)$('#guided-next').disabled=true}
}
function guidedAddRoute(){
 guidedPreview=null;
 const row=document.createElement('div');row.className='guided-new-route';
 const location=guidedText('');location.placeholder='/nuovo/';
 const destination=guidedText('');destination.placeholder='http://127.0.0.1:3000/';
 const websocket=document.createElement('input');websocket.type='checkbox';
 const wsLabel=guidedLabel('Supporto WebSocket',websocket);wsLabel.className='guided-check';
 const remove=document.createElement('button');remove.type='button';remove.textContent='Rimuovi nuovo percorso';
 const entry={row,location,destination,websocket};guidedNewRoutes.push(entry);
 remove.onclick=()=>{guidedNewRoutes=guidedNewRoutes.filter(r=>r!==entry);row.remove();guidedPreview=null};
 row.append(guidedLabel('Percorso pubblico',location),guidedLabel('URL del servizio',destination),wsLabel,remove);$('#guided-new-routes').append(row);
}
function guidedShowStep(step){
 guidedStep=step;$('#guided-step').textContent=['','1 · Domini e ascolto','2 · Percorsi e servizi','3 · TLS e opzioni','4 · Riepilogo delle modifiche'][step];
 for(const group of $('#guided-fields').children)group.hidden=Number(group.dataset.step)!==step;
 $('#guided-summary').hidden=step!==4;$('#guided-back').hidden=step===1;
 $('#guided-next').hidden=step===4;$('#guided-next').textContent=step===3?'Mostra anteprima':'Continua';
 $('#guided-apply').hidden=step!==4;$('#guided-apply').disabled=!guidedPreview||!guidedModel.live||!guidedPreview.changes.length;
}
function guidedPayload(){
 return {file:guidedModel.file,line:guidedModel.line,version:guidedModel.version,values:Object.fromEntries([...guidedReaders].map(([key,get])=>[key,get()])),routes:guidedNewRoutes.map(r=>({location:r.location.value.trim(),destination:r.destination.value.trim(),websocket:r.websocket.checked}))};
}
$('#guided-next').onclick=async()=>{
 if(!guidedModel||guidedWorking)return;
 if(guidedStep<3){guidedShowStep(guidedStep+1);return}
 guidedSetWorking(true);guidedMessage('Preparazione anteprima…',false);
 try{
  guidedSnapshot=guidedPayload();guidedPreview=await request('/api/existing/preview',guidedSnapshot);
  const summary=$('#guided-summary');summary.replaceChildren();
  if(!guidedPreview.changes.length){const p=document.createElement('p');p.textContent='Nessuna modifica da applicare.';summary.append(p)}
  for(const change of guidedPreview.changes){
   const section=document.createElement('section');section.className='guided-change';const title=document.createElement('h3');title.textContent=change.label;
   const before=document.createElement('pre');before.className='before';before.textContent='Prima: '+(change.before||'(non impostato)');
   const after=document.createElement('pre');after.className='after';after.textContent='Dopo: '+(change.after||'(rimosso / ereditato)');section.append(title,before,after);summary.append(section);
  }
  guidedMessage(guidedModel.live?'Il file sarà salvato con backup, verificato e applicato a Nginx.':'Applicazione disabilitata per questo server.',false);
  guidedShowStep(4);
 }catch(e){guidedMessage(e.message)}finally{guidedSetWorking(false)}
};
$('#guided-back').onclick=()=>{if(!guidedWorking){guidedPreview=null;guidedShowStep(guidedStep-1);guidedMessage('',false)}};
$('#guided-close').onclick=()=>{if(!guidedWorking)$('#guided-dialog').close()};
$('#guided-dialog').addEventListener('cancel',e=>{if(guidedWorking)e.preventDefault()});
$('#guided-form').onsubmit=async e=>{
 e.preventDefault();if(guidedWorking||!guidedPreview||!guidedPreview.changes.length)return;
 guidedSetWorking(true);guidedMessage('Backup, verifica e applicazione in corso…',false);
 try{
  const result=await request('/api/existing/apply',{...guidedSnapshot,preview:guidedPreview.hash});
  $('#guided-dialog').close();message(result.message);guidedPreview=null;loadInventory();
 }catch(e){guidedMessage(e.message);guidedPreview=null}
 finally{guidedSetWorking(false)}
};
