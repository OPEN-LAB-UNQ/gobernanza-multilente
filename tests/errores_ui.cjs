const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/errores.js'),'utf8');
function entorno(fetch){
 const handlers={},timers=[];
 function element(tag){return {tagName:tag.toUpperCase(),children:[],style:{},setAttribute(k,v){this[k]=v;},append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}},remove(){this.parent.children=this.parent.children.filter(x=>x!==this);}};}
 const body=element('body');const doc={body,documentElement:body,createElement:element,getElementById(id){function find(e){if(e.id===id)return e;for(const c of e.children){const x=find(c);if(x)return x;}}return find(body);}};
 const root={document:doc,fetch,location:{href:'https://g.test/',origin:'https://g.test'},setTimeout(fn,ms){timers.push({fn,ms});return timers.length;},clearTimeout(){},addEventListener(n,fn){handlers[n]=fn;}};
 vm.runInNewContext(source,{window:root,URL,AbortController});return {root,doc,handlers,timers};
}
function message(e){return e.doc.getElementById('error-persistente-texto')?.textContent;}
test('error HTTP persistente y sin repetir solicitudes',async()=>{let calls=0;const e=entorno(async()=>{calls++;return new Response('{"detail":"Datos inválidos"}',{status:422,headers:{'content-type':'application/json'}})});await e.root.fetch('/api/test');assert.match(message(e),/Datos inválidos/);assert.equal(calls,1);assert.equal(e.timers.some(t=>t.ms===4200),false);assert.ok(e.doc.getElementById('error-persistente'));});
test('sesión vencida tiene mensaje comprensible',async()=>{const e=entorno(async()=>new Response('',{status:401}));await e.root.fetch('/api/test');assert.match(message(e),/sesión/);});
test('fallo de red se muestra y se propaga',async()=>{const e=entorno(async()=>{throw Error('network')});await assert.rejects(e.root.fetch('/api/test'));assert.match(message(e),/conectar/);});
test('JSON inválido se muestra incluso con HTTP 200',async()=>{const e=entorno(async()=>new Response('{',{headers:{'content-type':'application/json'}}));await e.root.fetch('/api/test');assert.match(message(e),/interpretar/);});
test('error inesperado y recurso fallido quedan visibles',()=>{const e=entorno(async()=>new Response('{}'));e.handlers.unhandledrejection({});assert.match(message(e),/inesperado/);e.handlers.error({target:{tagName:'SCRIPT'}});assert.match(message(e),/cargar/);});
test('cancelación intencional no se presenta como fallo',async()=>{const e=entorno(async()=>{throw Error('abort')});const c=new AbortController();c.abort();await assert.rejects(e.root.fetch('/api/test',{signal:c.signal}));assert.equal(message(e),undefined);});
test('timeout informa resultado no confirmado',async()=>{const e=entorno((_,o)=>new Promise((resolve,reject)=>o.signal.addEventListener('abort',()=>reject(Error('abort')))));const p=e.root.fetch('/api/test');e.timers[0].fn();await assert.rejects(p);assert.match(message(e),/tiempo de espera/);});
test('éxito no muestra alerta y preserva respuesta',async()=>{const e=entorno(async()=>new Response('{"ok":true}',{headers:{'content-type':'application/json'}}));const r=await e.root.fetch('/api/test');assert.deepEqual(await r.json(),{ok:true});assert.equal(message(e),undefined);});

test('una ausencia esperada en consulta no tapa el formulario, pero un conflicto al escribir sí se informa',async()=>{
 const e=entorno(async()=>new Response('{"detail":"No hay actividad de votación activa"}',{status:409,headers:{'content-type':'application/json'}}));
 const r=await e.root.fetch('/api/proyectos-ia/votos/segunda-vuelta/estado',{estadosEsperados:[409]});
 assert.equal(r.status,409);assert.equal(message(e),undefined);
 await e.root.fetch('/api/test',{method:'POST',estadosEsperados:[409]});assert.match(message(e),/409/);
});
