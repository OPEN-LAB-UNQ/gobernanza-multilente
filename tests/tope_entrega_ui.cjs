// Tope de 30.000 caracteres de Incubadora en la pantalla (consulta de una participante, 24/10/2026).
// La entrega quedaba en la versión vieja porque re-dibujar el proyecto pisaba lo pegado y no guardado.
const {test}=require('node:test'); const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
const tramo=(desde,hasta)=>app.slice(app.indexOf(desde),app.indexOf(hasta,app.indexOf(desde)));
const largo=tramo('function largoTexto(','\n')+'\n';

function volcar(activo=null){
 const ctx=vm.createContext({document:{activeElement:activo}});
 vm.runInContext(tramo('function volcarCampoProyecto(','function renderProyectoIA('),ctx);
 return ctx;
}

test('re-dibujar el proyecto no pisa una entrega pegada y todavía sin guardar',()=>{
 const vieja='a'.repeat(16000), nueva='b'.repeat(29999);
 const el={value:nueva};
 const ctx=volcar();
 // El servidor devuelve la entrega vieja (p. ej. tras «Guardar contexto» o una consulta al docente).
 assert.equal(ctx.volcarCampoProyecto(el,vieja,vieja),true);
 assert.equal(el.value.length,29999);
});

test('sin cambios locales se muestra lo guardado; tras guardar no queda marcado como pendiente',()=>{
 const ctx=volcar();
 const el={value:''};
 assert.equal(ctx.volcarCampoProyecto(el,undefined,'texto guardado'),false);
 assert.equal(el.value,'texto guardado');
 const largoGuardado='c'.repeat(29999);
 el.value=largoGuardado+'  \n';
 assert.equal(ctx.volcarCampoProyecto(el,'texto guardado',largoGuardado),false);
 assert.equal(el.value,largoGuardado);
});

test('el campo con foco no se toca y avisa si tiene cambios propios',()=>{
 const el={value:'mi edición'};
 const ctx=volcar(el);
 assert.equal(ctx.volcarCampoProyecto(el,'guardado','guardado'),true);
 assert.equal(el.value,'mi edición');
});

test('el contador cuenta como el servidor: sin espacios de los bordes y un emoji vale 1',()=>{
 const ctx=vm.createContext({});vm.runInContext(largo,ctx);
 assert.equal(ctx.largoTexto('  '+'x'.repeat(29999)+'\n'),29999);
 assert.equal(ctx.largoTexto('😀'.repeat(10)),10);
 assert.equal(ctx.largoTexto(null),0);
});

function consulta(valor){
 const els={},llamadas=[],avisos=[];
 const get=id=>els[id]||=({value:'',textContent:'',disabled:false,hidden:true});
 get('proyecto-docente-consulta').value=valor;
 const ctx=vm.createContext({document:{getElementById:get},state:{currentUser:{rol:'analista'}},
  apiFetch:async(url,op)=>{llamadas.push([url,JSON.parse(op.body)]);return {};},
  renderProyectoIA(){},toast:(m,err)=>avisos.push([m,err]),cargarProyectoIASupervision(){},MAX_MENSAJE_DOCENTE_CHARS:30000});
 vm.runInContext(largo+tramo('let enviandoConsultaDocenteProyectoIA','const MAX_ENTREGA_CHARS'),ctx);
 return {ctx,llamadas,avisos,get};
}

test('consulta al docente de 29.999 caracteres se envía completa',async()=>{
 const t=consulta('d'.repeat(29999));
 await t.ctx.consultarDocenteProyectoIA();
 assert.equal(t.llamadas.length,1);
 assert.equal(t.llamadas[0][0],'/proyectos-ia/mio/docente');
 assert.equal(t.llamadas[0][1].mensaje.length,29999);
});

test('consulta al docente de 30.001 caracteres no se envía y explica el tope',async()=>{
 const t=consulta('d'.repeat(30001));
 await t.ctx.consultarDocenteProyectoIA();
 assert.equal(t.llamadas.length,0);
 assert.equal(t.avisos.length,1);
 assert.equal(t.avisos[0][1],true);
 assert.match(t.avisos[0][0],/30[.,]?001 caracteres y el máximo es 30[.,]?000/);
 assert.equal(t.get('proyecto-docente-consulta').value.length,30001);
});

test('la pantalla declara los mismos topes y muestra el contador de la consulta',()=>{
 assert.match(app,/const MAX_ENTREGA_CHARS = 30000;/);
 assert.match(app,/const MAX_SITUACION_CHARS = 30000;/);
 assert.match(app,/const MAX_MENSAJE_DOCENTE_CHARS = 30000;/);
 assert.match(html,/id="proyecto-docente-consulta-contador"/);
 assert.doesNotMatch(html,/id="proyecto-(entrega|situacion|docente-consulta)"[^>]*maxlength/);
});

test('un 422 de validación con lista de errores se muestra con texto, no vacío',async()=>{
 const ctx=vm.createContext({API:'/api',fetch:async()=>({ok:false,status:422,statusText:'Unprocessable Entity',
  json:async()=>({detail:[{loc:['body','mensaje'],msg:'String should have at most 12000 characters'}]})})});
 vm.runInContext(tramo('async function apiFetch(','async function apiFetchForm('),ctx);
 await assert.rejects(ctx.apiFetch('/x',{method:'POST'}),/at most 12000 characters/);
});
