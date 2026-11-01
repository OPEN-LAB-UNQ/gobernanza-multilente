const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const codigo=app.slice(app.indexOf('function contar('),app.indexOf('function contar(')+300).split('\n}\n')[0]+'\n}\n'+app.slice(app.indexOf('function renderResumenSimple('),app.indexOf('function renderResumenTiles('));
function entorno(){
 const els={};
 const crear=()=>({style:{},dataset:{},innerHTML:'',open:true,querySelector:()=>null});
 const ctx={document:{getElementById:id=>els[id]??=crear()},escapeHtml:x=>String(x),escapeHtmlUnaVez:x=>String(x),nombreLenteLegible:x=>'Lente '+x,botonOrigenHallazgo:h=>h.id?`<button data-origen-hallazgo="${h.id}">Ver origen</button>`:''};
 vm.createContext(ctx);vm.runInContext(codigo,ctx);
 return {ctx,els};
}
const caso=(n,prioridad)=>({prioridad,primary_finding:{id:n,lente:'cierre',resumen_llano:`Explicación ${n}`,evidencia:{hoja:'Cuadro 4',celda:`C${n}`}}});

test('muestra cuántos casos hay y sólo los cinco principales con su celda',()=>{
 const {ctx,els}=entorno();
 const casos=[1,2,3,4,5,6,7].map(n=>caso(n,n<3?'alta':'media'));
 ctx.renderResumenSimple({id:9,hallazgos:[],revision:{casos,casos_revision:7,prioridades:{alta:2,media:5}},devolucion:{cobertura:{registro_revision:{estado:'completo'}}}});
 const html=els['resumen-simple'].innerHTML;
 assert.match(html,/7 casos para revisar · 2 de prioridad alta/);
 assert.match(html,/Cuadro 4!C5/);
 assert.doesNotMatch(html,/Cuadro 4!C6/);
 assert.match(html,/Y 2 casos más en «Ver todo el detalle»/);
 assert.match(html,/data-origen-hallazgo="1"/);
 assert.doesNotMatch(html,/Lectura/);
 assert.equal(els['detalle-completo'].open,false);
});

test('sin casos no promete ausencia de errores y avisa la lectura parcial',()=>{
 const {ctx,els}=entorno();
 ctx.renderResumenSimple({id:3,hallazgos:[],devolucion:{cobertura:{registro_revision:{estado:'parcial'}}}});
 const html=els['resumen-simple'].innerHTML;
 assert.match(html,/No aparecieron casos con estos controles/);
 assert.match(html,/no garantiza que no haya errores/);
 assert.match(html,/Lectura parcial/);
 assert.doesNotMatch(html,/más en «Ver todo el detalle»/);
});

test('sin agrupación usa las señales de control por prioridad y deja afuera el contexto',()=>{
 const {ctx,els}=entorno();
 const hallazgos=[
  {id:1,severidad:'media',lente:'temporal',descripcion:'Variación anual',evidencia:{naturaleza:'contexto',puntaje_prioridad:99}},
  {id:2,severidad:'media',lente:'cierre',descripcion:'Total menor',evidencia:{hoja:'H',celda:'B2',puntaje_prioridad:40}},
  {id:3,severidad:'alta',lente:'cierre',descripcion:'No cierra',evidencia:{hoja:'H',celda:'B9',puntaje_prioridad:80}},
 ];
 ctx.renderResumenSimple({id:4,hallazgos,devolucion:{cobertura:{}}});
 const html=els['resumen-simple'].innerHTML;
 assert.match(html,/2 casos para revisar · 1 de prioridad alta/);
 assert.ok(html.indexOf('H!B9')<html.indexOf('H!B2'));
 assert.doesNotMatch(html,/Variación anual/);
});

test('volver a dibujar el mismo informe no cierra el detalle abierto',()=>{
 const {ctx,els}=entorno();
 const d={id:5,hallazgos:[],devolucion:{cobertura:{}}};
 ctx.renderResumenSimple(d);
 els['detalle-completo'].open=true;
 ctx.renderResumenSimple(d);
 assert.equal(els['detalle-completo'].open,true);
 ctx.renderResumenSimple({...d,id:6});
 assert.equal(els['detalle-completo'].open,false);
});

test('cada caso principal pregunta qué resultó ser, sólo a quien hizo el informe',()=>{
 const {ctx,els}=entorno();
 const casos=[1,2,3,4,5,6].map(n=>caso(n,'alta'));
 const hallazgos=[1,2,3,4,5,6].map(n=>({id:n,puede_responder:true,respuesta:n===2?{respuesta:'error_real',texto:'Era un error real',comentario:'corregido'}:null}));
 ctx.renderResumenSimple({id:9,hallazgos,revision:{casos,casos_revision:6,prioridades:{alta:6}},devolucion:{cobertura:{}}});
 const html=els['resumen-simple'].innerHTML;
 assert.equal((html.match(/¿Qué resultó ser\?/g)||[]).length,5);  // los cinco principales, no el sexto
 assert.match(html,/data-respuesta="error_real">Error real<\/button> · <button[^>]*data-respuesta="dato_correcto">Dato correcto<\/button> · <button[^>]*data-respuesta="no_se">Todavía no sé/);
 assert.match(html,/Sirve para medir la herramienta, no a vos\./);
 assert.match(html,/data-hallazgo="2" data-comentario="corregido"/);
 assert.match(html,/btn-respuesta activa" data-respuesta="error_real"/);
 assert.doesNotMatch(html,/data-hallazgo="6"/);
});

test('quien sólo mira ve la respuesta registrada y no los botones',()=>{
 const {ctx,els}=entorno();
 const hallazgos=[{id:1,puede_responder:false,respuesta:{respuesta:'dato_correcto',texto:'El dato estaba bien'}},{id:2,puede_responder:false,respuesta:null}];
 ctx.renderResumenSimple({id:9,hallazgos,revision:{casos:[caso(1,'alta'),caso(2,'media')],casos_revision:2,prioridades:{alta:1}},devolucion:{cobertura:{}}});
 const html=els['resumen-simple'].innerHTML;
 assert.match(html,/Respuesta registrada:<\/strong> El dato estaba bien/);
 assert.doesNotMatch(html,/data-respuesta=/);
});

test('la pregunta de cierre aparece al final, pendiente hasta que se responde',()=>{
 const {ctx,els}=entorno();
 ctx.renderCierreInforme({id:9,cierre_informe:{puede_responder:true,pendiente:true,es_prueba:false,respuesta:null}});
 let html=els['cierre-informe'].innerHTML;
 assert.equal(els['cierre-informe'].hidden,false);
 assert.match(html,/¿Corregiste algo del informe antes de entregarlo\?/);
 assert.match(html,/data-cierre="si"[^>]*>Sí<\/button> <button[^>]*data-cierre="no"[^>]*>No<\/button> <button[^>]*data-cierre="todavia_no"[^>]*>Todavía no/);
 assert.match(html,/¿Encontraste errores que la herramienta no señaló\? Cantidad <input type="number" min="0"/);
 assert.match(html,/Pendiente: todavía no respondiste\./);
 ctx.renderCierreInforme({id:9,cierre_informe:{puede_responder:true,pendiente:false,es_prueba:true,respuesta:{corrigio:'si',texto:'Sí',errores_no_senalados:2,registrado_en:'2026-10-24T10:00:00'}}});
 html=els['cierre-informe'].innerHTML;
 assert.match(html,/Respuesta registrada: corregiste algo: Sí · errores que no se señalaron: 2 \(2026-10-24\)/);
 assert.match(html,/Marcado como prueba: no cuenta para las mediciones/);
 assert.match(html,/btn-respuesta activa" data-cierre="si"/);
 ctx.renderCierreInforme({id:9,cierre_informe:{puede_responder:false,pendiente:false,respuesta:null}});
 assert.equal(els['cierre-informe'].hidden,true);
});
