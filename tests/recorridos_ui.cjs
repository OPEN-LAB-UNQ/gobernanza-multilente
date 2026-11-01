const {test} = require('node:test');
require('./estados_produccion_044.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const fuente = app.slice(app.indexOf('const RECORRIDOS ='), app.indexOf('let estadoRecorridos ='));
test('historial distingue confirmación pendiente, casos y señales técnicas',()=>{
 const ctx=vm.createContext({badgeSeveridad:x=>String(x)});
 vm.runInContext(app.slice(app.indexOf('function badgeEstadoInforme('),app.indexOf('// Mediciones:')),ctx);
 assert.match(ctx.badgeEstadoInforme({n_hallazgos:0,interpretacion_estado:'pendiente_confirmacion'}),/pendiente de confirmación/);
 assert.match(ctx.badgeEstadoInforme({n_hallazgos:0,interpretacion_estado:'interpretando'}),/interpretando/);
 assert.match(ctx.badgeEstadoInforme({n_hallazgos:6,n_casos:0,analysis_status:'finalizado'}),/0 casos para revisar/);
 assert.doesNotMatch(ctx.badgeEstadoInforme({n_hallazgos:6,n_casos:0,analysis_status:'finalizado'}),/6 hallazgos/);
 assert.match(ctx.badgeEstadoInforme({n_hallazgos:6,n_casos:2,analysis_status:'finalizado'}),/2 casos para revisar/);
});
function contexto(){const c=vm.createContext({escapeHtml:x=>String(x??'')});vm.runInContext(fuente,c);return c;}

test('sin registro propio ningún paso se da por hecho',()=>{
 const ctx=contexto();
 const el={innerHTML:''};
 ctx.renderRuta(el,'incubadora',null);
 assert.doesNotMatch(el.innerHTML,/ruta-paso-hecho/);
 assert.match(el.innerHTML,/Tu avance se marca cuando haya registro propio/);
 assert.match(el.innerHTML,/5 pasos/);
});

test('el avance marca lo hecho y señala el paso siguiente, no el último',()=>{
 const ctx=contexto();
 const el={innerHTML:''};
 ctx.renderRuta(el,'incubadora',{incubadora:{hechos:['problema','conversar'],detalle:'6 de 10 criterios con evidencia.'}});
 assert.equal((el.innerHTML.match(/ruta-paso-hecho/g)||[]).length,2);
 assert.equal((el.innerHTML.match(/ruta-paso-actual/g)||[]).length,1);
 const posActual=el.innerHTML.indexOf('ruta-paso-actual');
 assert.ok(posActual>el.innerHTML.indexOf('Conversás para precisarlo'));
 assert.match(el.innerHTML,/2 de 5 pasos con registro\. 6 de 10 criterios con evidencia\./);
});

test('los pasos que el sistema no puede verificar lo declaran',()=>{
 const ctx=contexto();
 const el={innerHTML:''};
 ctx.renderRuta(el,'multilente',{multilente:{hechos:['cargar','analizar','leer'],detalle:'3 informes propios.'}});
 assert.match(el.innerHTML,/Verificás en el archivo/);
 assert.match(el.innerHTML,/fuera del sistema: no hay que marcarlo/);
 assert.equal((el.innerHTML.match(/ruta-paso-hecho/g)||[]).length,3);
});

test('cada paso dice qué aporta y el recorrido se resume en una línea',()=>{
 const ctx=contexto();
 for(const clave of ['multilente','incubadora','conexiones','monitoreo']){
  const el={innerHTML:''};
  ctx.renderRuta(el,clave,null);
  assert.match(el.innerHTML,/ruta-sintesis/);
  const pasos=vm.runInContext('RECORRIDOS',ctx)[clave].pasos;
  assert.ok(pasos.length>=3);
  for(const p of pasos){assert.ok(p.aporte && p.aporte.length>15,`${clave}/${p.clave} sin aporte`);}
  assert.match(el.innerHTML,/role="img"/);
 }
});

test('un estado desconocido no rompe la pantalla ni inventa pasos',()=>{
 const ctx=contexto();
 const el={innerHTML:''};
 assert.doesNotThrow(()=>ctx.renderRuta(el,'inexistente',{inexistente:{hechos:['x']}}));
 assert.equal(el.innerHTML,'');
 const el2={innerHTML:''};
 ctx.renderRuta(el2,'conexiones',{conexiones:{hechos:['clave-que-no-existe']}});
 assert.doesNotMatch(el2.innerHTML,/ruta-paso-hecho/);
});
