const {test}=require('node:test'); const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');

test('contador distingue texto detectado, cierre humano y tema pospuesto',()=>{
 const el={innerHTML:'',querySelector(){return null;},querySelectorAll(){return [];}};
 const ctx=vm.createContext({document:{getElementById:()=>el},escapeHtml:s=>String(s),cambiarEstadoCriterio(){}});
 vm.runInContext(app.slice(app.indexOf('function renderProyectoClaridad('),app.indexOf('async function cambiarEstadoCriterio(')),ctx);
 ctx.renderProyectoClaridad({acompanamiento:{listo_para_entregar:true},checkpoint:{completos:2,total:3,criterios:[
  {clave:'datos',titulo:'Datos',ok:true,evidencia:'Dato aportado'},
  {clave:'supervision',titulo:'Supervisión',ok:true,cierre_manual:true},
  {clave:'riesgos',titulo:'Riesgos',ok:false,pospuesto:true},
 ]}});
 assert.match(el.innerHTML,/2\/3 temas marcados/);
 assert.match(el.innerHTML,/Texto para revisar: Datos/);
 assert.match(el.innerHTML,/Cerrado por vos: Supervisión/);
 assert.match(el.innerHTML,/Para después: Riesgos/);
 assert.doesNotMatch(el.innerHTML,/criterios listos|Listo: /);
 assert.match(el.innerHTML,/data-criterio-clave="datos" data-criterio-accion="posponer"/);
 assert.match(el.innerHTML,/data-criterio-clave="datos" data-criterio-accion="cerrar"/);
 assert.match(el.innerHTML,/data-criterio-clave="supervision" data-criterio-accion="reabrir"/);
 assert.match(el.innerHTML,/data-criterio-clave="riesgos" data-criterio-accion="reabrir"/);
});
function entorno(api){
 const els={};const get=id=>els[id]||=( {value:'',textContent:'',disabled:false,hidden:true,insertAdjacentHTML(){},querySelector(){return null;}} );
 const ctx=vm.createContext({document:{getElementById:get},state:{currentUser:{rol:'analista'}},
  apiFetch:api,renderProyectoIA(){},toast(){},cargarProyectoIASupervision(){},MAX_MENSAJE_CHARS:12000,MAX_ENTREGA_CHARS:30000,
  MAX_MENSAJE_DOCENTE_CHARS:30000,largoTexto:t=>Array.from(String(t||'').trim()).length});
 vm.runInContext(app.slice(app.indexOf('let enviandoMensajeProyectoIA ='),app.indexOf('const MAX_ENTREGA_CHARS')),ctx);
 return {ctx,get};
}
test('fallo de IA y consulta docente conserva el texto para reintentar',async()=>{
 const {ctx,get}=entorno(async()=>{throw Error('sin red');});
 get('proyecto-mensaje').value='Mi propuesta';get('proyecto-docente-consulta').value='Mi pregunta';
 await ctx.enviarMensajeProyectoIA();await ctx.consultarDocenteProyectoIA();
 assert.equal(get('proyecto-mensaje').value,'Mi propuesta');
 assert.equal(get('proyecto-docente-consulta').value,'Mi pregunta');
 assert.equal(get('btn-enviar-proyecto').disabled,false);
});
test('envío confirmado borra sólo el borrador enviado',async()=>{
 let resolve;const {ctx,get}=entorno(()=>new Promise(r=>resolve=r));
 get('proyecto-mensaje').value='Mensaje enviado';const job=ctx.enviarMensajeProyectoIA();
 get('proyecto-mensaje').value='Otro borrador durante la espera';resolve({});await job;
 assert.equal(get('proyecto-mensaje').value,'Otro borrador durante la espera');
 let resolve2;ctx.apiFetch=()=>new Promise(r=>resolve2=r);
 const again=ctx.enviarMensajeProyectoIA();resolve2({});await again;
 assert.equal(get('proyecto-mensaje').value,'');
});
test('prueba usa propuesta completa y no llama a IA si falló el guardado',async()=>{
 let llamadas=0;const status={textContent:''},button={disabled:false};
 const ctx=vm.createContext({proyectoCamposActuales:()=>({titulo:'Proyecto',entrega_final:'Mi propuesta completa'}),
  document:{getElementById:id=>id==='btn-probar-claridad'?button:id==='proyecto-prueba-estado'?status:{value:'Mi propuesta completa'}},
  enviandoMensajeProyectoIA:false,state:{proyectoIA:{}},MAX_ENTREGA_CHARS:30000,largoTexto:t=>Array.from(String(t||'').trim()).length,
  guardarProyectoIA:async()=>null,enviarMensajeProyectoIA:async()=>{llamadas++;}});
 vm.runInContext(app.slice(app.indexOf('function promptPruebaClaridadProyecto('),app.indexOf('// ---------- detalle / análisis / decisión ----------')),ctx);
 assert.match(ctx.promptPruebaClaridadProyecto(),/propuesta guardada completa/);
 assert.match(ctx.promptPruebaClaridadProyecto(),/diez criterios/);
 await ctx.probarClaridadProblema();assert.equal(llamadas,0);assert.equal(button.disabled,false);
 assert.match(status.textContent,/revisión no se inició/);
});
test('puntaje sin cambios deja explicación visible',async()=>{
 const status={textContent:''},button={disabled:false};
 const ctx=vm.createContext({proyectoCamposActuales:()=>({}),document:{getElementById:id=>id==='btn-probar-claridad'?button:id==='proyecto-prueba-estado'?status:{value:'Contenido'}},
  enviandoMensajeProyectoIA:false,state:{proyectoIA:{checkpoint:{completos:4}}},MAX_ENTREGA_CHARS:30000,largoTexto:t=>Array.from(String(t||'').trim()).length,
  guardarProyectoIA:async()=>({}),enviarMensajeProyectoIA:async()=>({checkpoint:{completos:4}})});
 vm.runInContext(app.slice(app.indexOf('function promptPruebaClaridadProyecto('),app.indexOf('// ---------- detalle / análisis / decisión ----------')),ctx);
 await ctx.probarClaridadProblema();assert.match(status.textContent,/sigue en 4/);assert.equal(button.disabled,false);
});

test('estado combina con tema, búsqueda y proyecto propio sin cambiar datos',()=>{
 const ctx=vm.createContext({normalizarBusqueda:s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()});
 vm.runInContext(app.slice(app.indexOf('function filtrarCasosProyecto('),app.indexOf('function renderCasosProyectos(')),ctx);
 const casos=[{id:1,titulo:'Atención',etiqueta:'Servicios',estado:'entregado',es_propio:true},{id:2,titulo:'Atención',etiqueta:'Servicios',estado:'en_proceso',es_propio:true},{id:3,titulo:'Atención',etiqueta:'Servicios',estado:'entregado',es_propio:false}];
 const before=JSON.stringify(casos);
 assert.deepEqual(Array.from(ctx.filtrarCasosProyecto(casos,{tema:'Servicios',estado:'entregado',busqueda:'atencion',propio:true}),x=>x.id),[1]);
 assert.equal(ctx.filtrarCasosProyecto(casos,{estado:'revisado'}).length,0);
 assert.equal(ctx.filtrarCasosProyecto(casos,{}).length,3);
 assert.equal(JSON.stringify(casos),before);
 assert.match(ctx.estadoCasoLegible('entregado'),/pendiente de revisión docente/);
});

test('abrir desde conexiones elimina filtro de estado anterior',async()=>{
 const els={'buscar-casos':{value:'otro'},'solo-mi-caso':{checked:true},'estado-casos':{value:'revisado'}};
 const ctx=vm.createContext({document:{getElementById:id=>els[id]},state:{proyectoCasosFiltro:'otro'},mostrarVista(){},cargarCasosProyectos:async()=>{}});
 vm.runInContext(app.slice(app.indexOf('async function abrirCasoDesdeConexion('),app.indexOf("document.getElementById('casos-rizoma-grid').addEventListener")),ctx);
 await ctx.abrirCasoDesdeConexion({target:{closest:()=>({dataset:{abrirCaso:'5'}})}});
 assert.equal(els['estado-casos'].value,'');assert.equal(ctx.state.casoEnfocado,5);
});

test('la revisión aparece junto al botón sin reinterpretar HTML ni modificar el contador',async()=>{
 const els={};const get=id=>els[id]||=( {value:'Contenido',textContent:'',disabled:false,hidden:true} );
 const ctx=vm.createContext({document:{getElementById:get},enviandoMensajeProyectoIA:false,state:{proyectoIA:{checkpoint:{completos:4}}},MAX_ENTREGA_CHARS:30000,largoTexto:t=>Array.from(String(t||'').trim()).length,
 guardarProyectoIA:async()=>({}),enviarMensajeProyectoIA:async()=>({checkpoint:{completos:4},mensajes:[{remitente:'ia',contenido:'Anterior'},{remitente:'ia',contenido:'<img src=x> Faltan indicadores'}]})});
 vm.runInContext(app.slice(app.indexOf('function promptPruebaClaridadProyecto('),app.indexOf('// ---------- detalle / análisis / decisión ----------')),ctx);
 await ctx.probarClaridadProblema();assert.equal(get('proyecto-prueba-respuesta').hidden,false);assert.match(get('proyecto-prueba-respuesta').textContent,/<img src=x> Faltan indicadores/);assert.match(get('proyecto-prueba-estado').textContent,/sigue en 4/);
});

test('aporte confirmado, doble clic bloqueado y fallo conserva texto',async()=>{
 const els={};const get=id=>els[id]||=( {value:'Aporte',textContent:'',disabled:false,hidden:true} );let calls=0,resolve;
 const ctx=vm.createContext({document:{getElementById:get},state:{reporteSeleccion:new Set([1]),detalleId:1},toast(){},apiFetch:()=>{calls++;return new Promise(r=>resolve=r);}});
 vm.runInContext(app.slice(app.indexOf('async function registrarAprendizajeSeleccionado('),app.indexOf('function renderExploracionSemantica(')),ctx);
 const first=ctx.registrarAprendizajeSeleccionado();await ctx.registrarAprendizajeSeleccionado();assert.equal(calls,1);
 get('aprendizaje-titulo').value='Otro aporte mientras guarda';resolve({});await first;
 assert.match(get('calibracion-confirmacion').textContent,/Guardado: «Aporte»/);assert.equal(get('aprendizaje-titulo').value,'Otro aporte mientras guarda');assert.equal(get('btn-registrar-aprendizaje-hallazgo').disabled,false);
 get('aprendizaje-hallazgo-contenido').value='Contenido nuevo';ctx.apiFetch=async()=>{throw Error('Sin red');};await ctx.registrarAprendizajeSeleccionado();assert.equal(get('aprendizaje-hallazgo-contenido').value,'Contenido nuevo');assert.match(get('calibracion-confirmacion').textContent,/No se pudo confirmar/);
});
test('mensaje que supera el tope del chat no se envía y conserva el texto',async()=>{
 let llamadas=0;const {ctx,get}=entorno(async()=>{llamadas++;return {};});
 get('proyecto-mensaje').value='a'.repeat(12001);await ctx.enviarMensajeProyectoIA();
 assert.equal(llamadas,0);assert.equal(get('proyecto-mensaje').value.length,12001);
 assert.equal(get('btn-enviar-proyecto').disabled,false);
});

function entornoDetalle(api) {
 const ctx=vm.createContext({apiFetch:api,fmtFecha:x=>x,estadoCasoLegible:x=>x});
 vm.runInContext(app.slice(app.indexOf('function escapeHtml('),app.indexOf('function escapeHtml(')+app.slice(app.indexOf('function escapeHtml(')).indexOf('\n}')+2),ctx);
 vm.runInContext(app.slice(app.indexOf('function renderDetalleCaso('),app.indexOf('function renderVotoCaso(')),ctx);
 ctx.activarLecturaCaso=()=>{}; // Las pruebas de carga aíslan los controles, ver pruebas de lectura abajo.
 const boton={addEventListener(tipo,fn){this.click=fn;}};
 const contenido={innerHTML:'',querySelector:()=>boton};
 const details={open:true,dataset:{casoDetalle:'2'},querySelector:()=>contenido};
 return {ctx,details,contenido,boton};
}
test('trabajo completo conserva párrafos y escapa HTML ajeno',()=>{
 const {ctx}=entornoDetalle();
 const texto='Primer párrafo\n\nSegundo párrafo. '+ 'Detalle '.repeat(4000)+'<img src=x onerror=alert(1)>';
 const html=ctx.renderDetalleCaso({situacion:texto,propuesta:'Entrega completa',estado:'en_proceso'});
 assert.ok(html.includes(texto.split('<')[0]));assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img/);
 assert.match(html,/Entrega completa/);
 assert.match(ctx.renderDetalleCaso({}),/Todavía no hay una propuesta guardada/);
});
test('detalle se carga al abrir una sola vez, sin duplicar solicitudes pendientes',async()=>{
 let terminar,llamadas=0;
 const {ctx,details,contenido}=entornoDetalle(url=>{assert.equal(url,'/proyectos-ia/casos/2');llamadas++;return new Promise(r=>terminar=r);});
 details.open=false;await ctx.cargarDetalleCaso(details);assert.equal(llamadas,0);
 details.open=true;const primera=ctx.cargarDetalleCaso(details);await ctx.cargarDetalleCaso(details);
 assert.equal(llamadas,1);assert.match(contenido.innerHTML,/Cargando/);
 terminar({situacion:'Caso íntegro',propuesta:'Texto completo'});await primera;
 details.open=false;await ctx.cargarDetalleCaso(details);details.open=true;await ctx.cargarDetalleCaso(details);
 assert.equal(llamadas,1);assert.match(contenido.innerHTML,/Texto completo/);
});
test('fallo en detalle permite reintentar y no lo marca como cargado',async()=>{
 let llamadas=0;const {ctx,details,contenido,boton}=entornoDetalle(async()=>{if(++llamadas===1)throw Error('<sin conexión>');return {propuesta:'Recuperada'};});
 await ctx.cargarDetalleCaso(details);assert.equal(details.dataset.cargado,undefined);
 assert.match(contenido.innerHTML,/&lt;sin conexión&gt;/);assert.match(contenido.innerHTML,/Reintentar/);
 await boton.click();assert.match(contenido.innerHTML,/Recuperada/);assert.equal(llamadas,2);
});

test('buscar escapa consulta literal y texto, conserva párrafos y admite mayúsculas',()=>{
 const {ctx}=entornoDetalle();
 assert.equal(ctx.resaltarTextoCaso('IA [a+b].\nIA <script>', '[a+b].'), 'IA <mark tabindex="-1">[a+b].</mark>\nIA &lt;script&gt;');
 assert.equal((ctx.resaltarTextoCaso('IA\nia\nIa','ia').match(/<mark /g)||[]).length,3);
 assert.equal(ctx.resaltarTextoCaso('a & b\n<script>', '   '),'a &amp; b\n&lt;script&gt;');
 assert.equal(ctx.resaltarTextoCaso('Sin esa palabra', 'inexistente'),'Sin esa palabra');
 assert.equal(ctx.resaltarTextoCaso('<img src=x>', '<img'),'<mark tabindex="-1">&lt;img</mark> src=x&gt;');
});

function lectorDePrueba() {
 const {ctx}=entornoDetalle();
 vm.runInContext(app.slice(app.indexOf('function activarLecturaCaso('),app.indexOf('async function cargarDetalleCaso(')),ctx);
 const nodo=()=>({value:'',textContent:'',disabled:false,dataset:{},eventos:{},addEventListener(t,f){this.eventos[t]=f;},focus(){this.enfocado=true;},scrollIntoView(){this.desplazamientos=(this.desplazamientos||0)+1;}});
 const buscar=nodo(),resultado=nodo(),anterior=nodo(),siguiente=nodo(),cerrar=nodo(),resumen=nodo(),ir=nodo(),titulo=nodo();
 ir.dataset.casoIr='propuesta';
 const textos=[{textContent:'IA revisa.\nSin decidir.',innerHTML:''},{textContent:'La ia ayuda.\nSegunda IA.',innerHTML:''}];
 let marcas=[];
 const controles={'[data-caso-buscar]':buscar,'[data-caso-resultados]':resultado,'[data-caso-anterior]':anterior,'[data-caso-siguiente]':siguiente,'[data-caso-seccion="propuesta"] h4':titulo};
 const contenido={querySelector:s=>controles[s],querySelectorAll(s){
  if(s==='.case-full-text')return textos;
  if(s==='[data-caso-ir]')return [ir];
  if(s==='[data-caso-cerrar]')return [cerrar];
  if(s==='.case-full-text mark')return marcas=textos.flatMap(t=>Array.from(t.innerHTML.matchAll(/<mark /g),()=>({...nodo(),classList:{add(){},remove(){}}})));
  throw Error(s);
 }};
 const details={open:true,querySelector:()=>resumen};
 ctx.activarLecturaCaso(details,contenido);
 return {buscar,resultado,anterior,siguiente,cerrar,resumen,ir,titulo,textos,details,marcas:()=>marcas};
}

test('búsqueda recorre ambas secciones, navega con teclado y limpia sin alterar textos',()=>{
 const l=lectorDePrueba();l.buscar.value='ia';l.buscar.eventos.input();
 assert.equal(l.resultado.textContent,'3 coincidencias.');assert.equal(l.siguiente.disabled,false);
 let prevenido=false;l.buscar.eventos.keydown({key:'Enter',shiftKey:false,preventDefault(){prevenido=true;}});
 assert.ok(prevenido);assert.equal(l.resultado.textContent,'1 de 3 coincidencias.');assert.equal(l.marcas()[0].desplazamientos,1);
 l.anterior.eventos.click();assert.equal(l.resultado.textContent,'3 de 3 coincidencias.');
 l.siguiente.eventos.click();assert.equal(l.resultado.textContent,'1 de 3 coincidencias.');
 l.buscar.value='ausente';l.buscar.eventos.input();assert.equal(l.resultado.textContent,'No hay coincidencias.');assert.equal(l.anterior.disabled,true);
 l.buscar.value='';l.buscar.eventos.input();assert.equal(l.textos[0].innerHTML,l.textos[0].textContent);assert.equal(l.textos[1].innerHTML,l.textos[1].textContent);
});

test('ir a propuesta y cerrar devuelven foco sin cambiar de vista',()=>{
 const l=lectorDePrueba();l.ir.eventos.click();assert.equal(l.titulo.enfocado,true);assert.equal(l.titulo.desplazamientos,1);
 l.cerrar.eventos.click();assert.equal(l.details.open,false);assert.equal(l.resumen.enfocado,true);assert.equal(l.resumen.desplazamientos,1);
});