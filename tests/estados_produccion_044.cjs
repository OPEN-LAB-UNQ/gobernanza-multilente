const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const app = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');

test('una salida parcial utilizable no se presenta como cobertura completa', () => {
  const panel = {innerHTML:'', style:{}};
  const ctx = {document:{getElementById:()=>panel}, escapeHtml:String};
  vm.createContext(ctx);
  vm.runInContext(app.slice(app.indexOf('function renderExploracionSemantica('), app.indexOf('function renderTriangulacion(')),ctx);
  ctx.renderExploracionSemantica({devolucion:{cobertura:{exploracion_semantica:{
    estado:'no_completada', hallazgos:[], modelos:[{modelo:'gpt', evaluada:false,
      elementos_cubiertos:0, elementos_totales:28, hipotesis_conservadas:2}]
  }}}});
  assert.match(panel.innerHTML,/Salida parcial utilizable: 2 hipótesis conservadas/);
  assert.match(panel.innerHTML,/0\/28 elementos/);
  assert.doesNotMatch(panel.innerHTML,/Estrategia completada/);
});
test('el mapa diferencia no ejecutado de cero señales', () => {
  const el = {innerHTML: ''};
  const ctx = {document: {getElementById: () => el}, escapeHtml: String,
    LENTES: [{id:'cronista', nombre:'Cronista', pregunta:'Tiempo', salidaVacia:'Sin señales'}],
    estadoLente: () => ({texto:'sin señales', cls:'ok', nivel:0})};
  vm.createContext(ctx);
  vm.runInContext(app.slice(app.indexOf('function renderInformeLentes('), app.indexOf('function botonesDescargaReporte(')), ctx);
  ctx.renderInformeLentes([], [{lente:'cronista', estado:'no_aplicable', motivo:'Sin eje temporal'}]);
  assert.match(el.innerHTML, /no aplicable/);
  assert.match(el.innerHTML, /Sin eje temporal/);
  assert.doesNotMatch(el.innerHTML, /sin señales/);
  ctx.renderInformeLentes([], [{lente:'cronista', estado:'evaluable'}]);
  assert.match(el.innerHTML, /sin señales/);
});
test('sin señales ni contadores disponibles no muestra NaN ni un fallo de IA', () => {
  const els = {'triangulacion-body':{}, 'resumen-apoyo-ia':{}};
  const ctx = {document:{getElementById:id=>els[id]}, renderExploracionSemantica:()=>{}, escapeHtml:String, NOMBRE_MODELO_PROGRESO:{}};
  vm.createContext(ctx);
  vm.runInContext(app.slice(app.indexOf('function renderTriangulacion('), app.indexOf('function etiquetaEstadoCertificacion(')),ctx);
  ctx.renderTriangulacion({hallazgos:[], modelos_consultados:[{modelo:'gpt', estado:'solo_exploracion', detalle:'No había señales'}],
    coincidencias:[], divergencias:[], hallazgos_singulares:[], devolucion:{cobertura:{manifiesto:{modelos:[{proveedor:'gpt', alcance_ia:{semantica:{}}}]}}}});
  assert.doesNotMatch(els['triangulacion-body'].innerHTML,/NaN/);
  assert.match(els['resumen-apoyo-ia'].textContent,/No había señales/);
});
