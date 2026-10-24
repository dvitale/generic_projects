const $=s=>document.querySelector(s);
let state={hosts:[],revision:0},editing=-1,busy=false,server='local';
let inventory={proxies:[],warnings:[]},inventoryLoading=false,inventoryError='',inventoryRequest=0;
function apiURL(path){return path+'?server='+encodeURIComponent(server)}
async function request(path,body){const r=await fetch(apiURL(path),body?{method:'POST',headers:{'Content-Type':'application/json','X-Proxyman':'1'},body:JSON.stringify(body)}:{});if(!r.ok){let msg;try{msg=(await r.json()).error}catch{msg='Richiesta fallita ('+r.status+')'}throw Error(msg)}return r.json()}
function message(text,error=false){$('#message').textContent=text;$('#message').className=error?'error':''}
async function load(){state=await request('/api/hosts');draw()}
function draw(){
 $('#total').textContent=state.hosts.length;$('#enabled').textContent=state.hosts.filter(h=>h.enabled).length;$('#tls').textContent=state.hosts.filter(h=>h.certificate).length;
 $('#mode').textContent=state.live?(state.remote?'Gestione Nginx via SSH':'Gestione Nginx locale'):'Modalità configurazione';
 $('#apply').disabled=!state.live||busy;
 $('#server').disabled=busy;$('#add').disabled=busy;$('#check').disabled=!state.remote||busy;
 $('#download').href=apiURL('/api/config');
 $('#pending').textContent=state.pending?'Configurazione da applicare o stato da confermare':'Ultima configurazione inviata a Nginx';
 const term=$('#search').value.toLowerCase();$('#rows').replaceChildren();let count=0;
 state.hosts.forEach((h,i)=>{if(!(h.domain+' '+h.target).toLowerCase().includes(term))return;count++;
 const tr=document.createElement('tr');
 for(const value of [h.domain,h.scheme+'://'+(h.target.includes(':')?'['+h.target+']':h.target)+':'+h.port,h.certificate?'HTTPS':'HTTP',h.enabled?'Abilitato':'Disabilitato']){
 const td=document.createElement('td');td.textContent=value;tr.append(td)}
 const td=document.createElement('td');const actions=document.createElement('div');actions.className='row-actions';
 for(const [label,fn] of [['Modifica',()=>edit(i)],[h.enabled?'Disabilita':'Abilita',()=>save(state.hosts.map((r,j)=>j===i?{...r,enabled:!r.enabled}:r))],['Elimina',()=>{if(confirm('Eliminare '+h.domain+' dalla configurazione?'))save(state.hosts.filter((_,j)=>j!==i))}]]){
 const button=document.createElement('button');button.textContent=label;button.disabled=busy;button.onclick=fn;actions.append(button)}
 td.append(actions);tr.append(td);$('#rows').append(tr)});
 $('#empty').hidden=count>0;$('#empty h3').textContent=state.hosts.length?'Nessun risultato':'Collega il tuo primo servizio';$('#empty p').textContent=state.hosts.length?'Prova a cercare un altro dominio.':'Aggiungi un dominio e indica dove inoltrare le richieste.';
}
async function save(hosts){if(busy)return false;busy=true;draw();try{await request('/api/hosts',{hosts,revision:state.revision});await load();message('Configurazione salvata. Applica le modifiche quando sei pronto.');return true}catch(e){message(e.message,true);$('#form-error').textContent=e.message;return false}finally{busy=false;draw()}}
function edit(i){editing=i;$('#form').reset();$('#form-error').textContent='';$('#form-title').textContent=i<0?'Nuovo proxy':'Modifica proxy';if(i>=0)for(const [key,value]of Object.entries(state.hosts[i])){const input=$('#form').elements.namedItem(key);if(input){if(input.type==='checkbox')input.checked=value;else input.value=value}}$('#editor').showModal()}
$('#add').onclick=()=>edit(-1);$('#close').onclick=$('#cancel').onclick=()=>$('#editor').close();$('#search').oninput=()=>{draw();drawInventory()};
$('#form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);const h={domain:f.get('domain').trim(),target:f.get('target').trim(),port:Number(f.get('port')),scheme:f.get('scheme'),enabled:f.has('enabled'),websocket:f.has('websocket'),certificate:f.get('certificate').trim(),key:f.get('key').trim()};const rows=[...state.hosts];if(editing<0)rows.push(h);else rows[editing]=h;if(await save(rows))$('#editor').close()};
$('#preview').onclick=async()=>{try{const r=await fetch(apiURL('/api/config'));if(!r.ok)throw Error('Impossibile caricare la configurazione');$('#config').textContent=await r.text();$('#config-dialog').showModal()}catch(e){message(e.message,true)}};
$('#close-config').onclick=()=>$('#config-dialog').close();
$('#apply').onclick=async()=>{if(busy||!confirm('Verificare e applicare la configurazione salvata sul server '+$('#server').selectedOptions[0].textContent+'?'))return;busy=true;draw();try{const result=await request('/api/apply',{revision:state.revision});await load();loadInventory();message(result.message)}catch(e){message(e.message,true)}finally{busy=false;draw()}};

$('#server').onchange=async()=>{const previous=server;server=$('#server').value;busy=true;draw();try{await load();localStorage.setItem('proxyman-server',server);loadInventory();message('Server selezionato: '+$('#server').selectedOptions[0].textContent)}catch(e){server=previous;$('#server').value=previous;message(e.message,true)}finally{busy=false;draw()}};
$('#check').onclick=async()=>{if(busy)return;busy=true;draw();try{const result=await request('/api/check',{revision:state.revision});message(result.message)}catch(e){message(e.message,true)}finally{busy=false;draw()}};
async function initialize(){const servers=await request('/api/servers');$('#server').replaceChildren();for(const s of servers){const option=document.createElement('option');option.value=s.id;option.textContent=s.name+(s.remote?' · '+s.address:'');$('#server').append(option)}const saved=localStorage.getItem('proxyman-server');const remotes=servers.filter(s=>s.remote);server=servers.some(s=>s.id===saved)?saved:(remotes.length===1?remotes[0].id:'local');$('#server').value=server;await load();loadInventory()}
initialize().catch(e=>message(e.message,true));


async function loadInventory(){
 const sequence=++inventoryRequest,selected=server;
 inventoryLoading=true;inventoryError='';inventory={proxies:[],warnings:[]};drawInventory();
 try{const result=await request('/api/inventory');if(sequence===inventoryRequest&&selected===server)inventory=result}
 catch(e){if(sequence===inventoryRequest&&selected===server)inventoryError=e.message}
 finally{if(sequence===inventoryRequest&&selected===server){inventoryLoading=false;drawInventory()}}
}
function drawInventory(){
 $('#existing-rows').replaceChildren();$('#refresh-inventory').disabled=inventoryLoading;
 $('#discovered-count').textContent=inventoryLoading?'…':inventoryError?'—':inventory.proxies.length;
 const status=$('#inventory-status');status.className=inventoryError?'error':'';
 status.textContent=inventoryLoading?'Lettura della configurazione Nginx dal server…':inventoryError?inventoryError:inventory.proxies.length?('Rilevati '+inventory.proxies.length+' blocchi reverse proxy. '+inventory.warnings.join(' ')):'Nessun reverse proxy HTTP rilevato. '+inventory.warnings.join(' ');
 if(inventoryLoading||inventoryError)return;
 const term=$('#search').value.toLowerCase();
 for(const proxy of inventory.proxies){
  if(!(proxy.domains.join(' ')+' '+proxy.routes.map(r=>r.destination+' '+r.backends.join(' ')).join(' ')+' '+proxy.file).toLowerCase().includes(term))continue;
  const row=document.createElement('tr');
  const domain=document.createElement('td');domain.textContent=proxy.domains.join(', ');const listens=document.createElement('small');listens.textContent=proxy.listeners.join(', ')||'Ascolto predefinito';domain.append(listens);row.append(domain);
  const destinations=document.createElement('td');for(const route of proxy.routes){const code=document.createElement('code');code.textContent=route.location+' → '+route.destination;destinations.append(code)}row.append(destinations);
  const tls=document.createElement('td');tls.textContent=proxy.tls?'HTTPS':'HTTP';row.append(tls);
  const file=document.createElement('td');file.textContent=proxy.file+':'+proxy.line;const source=document.createElement('small');source.textContent=proxy.managed?'File Proxyman':'Configurazione esistente';file.append(source);row.append(file);
  const action=document.createElement('td');const button=document.createElement('button');button.textContent='Dettagli';button.onclick=()=>{const lines=['Domini: '+proxy.domains.join(', '),'Ascolto: '+proxy.listeners.join(', '),'File: '+proxy.file+':'+proxy.line,''];for(const route of proxy.routes){lines.push(route.location+' → '+route.destination);if(route.backends.length)lines.push('Backend upstream: '+route.backends.join(', '))}$('#existing-detail').textContent=lines.join('\n');$('#existing-dialog').showModal()};action.append(button);if(!proxy.managed){const editButton=document.createElement('button');editButton.textContent='Modifica guidata';editButton.className='primary';editButton.onclick=()=>openGuided(proxy);action.append(editButton)}row.append(action);$('#existing-rows').append(row)
 }
}
$('#refresh-inventory').onclick=loadInventory;
$('#close-existing').onclick=()=>$('#existing-dialog').close();
