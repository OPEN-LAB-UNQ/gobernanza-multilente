const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const HELPERS = app.slice(app.indexOf('function contar('), app.indexOf('const RECORRIDOS ='));
const crearContexto = (base) => { const c = vm.createContext(base); vm.runInContext(HELPERS, c); return c; };
const fuente = app.slice(app.indexOf('function ordenarControles('),app.indexOf('function renderHallazgos('));
const ctx=crearContexto({});vm.runInContext(fuente,ctx);
test('contexto nunca desplaza controles aunque tenga un puntaje alto',()=>{
 const datos=[{id:1,severidad:'alta',evidencia:{naturaleza:'contexto',puntaje_prioridad:999}},{id:2,severidad:'media',evidencia:{naturaleza:'control',puntaje_prioridad:55}}];
 assert.equal(ctx.ordenarControles(datos)[0].id,2);
 assert.equal(datos[0].id,1);
});
test('la prioridad no depende de importes absolutos ni elimina resultados',()=>{
 const datos=[{id:1,evidencia:{puntaje_prioridad:60,valor_observado:1e12}},{id:2,evidencia:{puntaje_prioridad:120,valor_observado:2}}];
 const salida=ctx.ordenarControles(datos);
 assert.equal(salida.length,2);assert.equal(salida[0].id,2);
});

test('un informe por cuadros sin lista de condiciones pendientes se puede abrir',()=>{
 const el={innerHTML:''};const local=crearContexto({document:{getElementById:()=>el},escapeHtml:x=>String(x ?? '')});
 const fn=app.slice(app.indexOf('function renderGarantiasEjecucion('),app.indexOf('function renderEvaluacionPiloto('));
 vm.runInContext(fn,local);
 assert.doesNotThrow(()=>local.renderGarantiasEjecucion({id:201,devolucion:{cobertura:{lentes:[],control_interdocumental:{estado:'no_evaluable',motivo:'Cuadros separados'}}}}));
 assert.ok(el.innerHTML.includes('Ver detalle por cuadro'));
});

test('la interfaz separa ejecutado de seleccionado y muestra cero antecedentes sin inventar confianza',()=>{
 const local=crearContexto({escapeHtml:x=>String(x??'').replaceAll('<','&lt;').replaceAll('>','&gt;')});
 vm.runInContext(app.slice(app.indexOf('function renderTrazabilidadCuadros('),app.indexOf('function renderCoberturaLimites(')),local);
 const html=local.renderTrazabilidadCuadros([{archivo:'<script>libro</script>.xlsx',hoja:'Datos',bloque:1,
   trazabilidad_controles:{ajedrecista:{seleccionado:true,estado:'ejecutado',motivo:'Sin señales'},
     relaciones:{seleccionado:true,estado:'sin_traza_de_ejecucion',motivo:'Pendiente'},
     matematico:{seleccionado:false,estado:'no_aplicable'}},
   experiencia_comparable:[{control:'ajedrecista',casos_comparables:0,revisados_por_persona:0}]}]);
 assert.match(html,/1 control ejecutado/);
 assert.match(html,/1 selección sin traza propia/);
 assert.match(html,/ajedrecista: 0 lecturas confirmadas, 0 resultados revisados/);
 assert.match(html,/&lt;script&gt;/);
 assert.doesNotMatch(html,/<script>/);
});


test('cobertura parcial usa el mismo porcentaje en tarjeta y advertencia',()=>{
 const elements={};const doc={getElementById:id=>elements[id] ||= {innerHTML:''}};
 const local=crearContexto({document:doc,escapeHtml:x=>String(x??'')});
 const fn=app.slice(app.indexOf('function porcentajeLectura('),app.indexOf('function tituloAlcanceSeries('));
 vm.runInContext(fn,local);
 local.renderResumenTiles({hallazgos:[],devolucion:{cobertura:{excel:{lectura:{estado:'completa',series_leidas:689,series_aparentes:690,proporcion:.999}}}}});
 assert.match(elements['resumen-tiles'].innerHTML,/99.9 %/);
 assert.match(elements['resumen-principales'].innerHTML,/99.9 %/);
 assert.doesNotMatch(elements['resumen-principales'].innerHTML,/100 %/);
 assert.match(elements['resumen-tiles'].innerHTML,/parcial/);
});

test('contexto de IA visible separado y texto de celdas escapado',()=>{
 const panel={style:{},innerHTML:'',hidden:false};
 const local=crearContexto({document:{getElementById:()=>panel},escapeHtml:x=>String(x??'').replaceAll('<','&lt;').replaceAll('>','&gt;')});
 const fn=app.slice(app.indexOf('function renderExploracionSemantica('),app.indexOf('function renderTriangulacion('));
 vm.runInContext(fn,local);
 local.renderExploracionSemantica({devolucion:{cobertura:{exploracion_semantica:{estado:'con_hallazgos',modelos:[],hallazgos:[{tipo:'unidad',modelo:'gpt',explicacion:'Revisar unidades',alternativa:'Cambio explícito',evidencia_comparativa:[{archivo:'libro.xlsx',hoja:'Buenos Aires',celda:'A3',texto:'<img src=x onerror=alert(1)>'}]}]}}}});
 assert.match(panel.innerHTML,/Independientes de los controles determinísticos/);
 assert.match(panel.innerHTML,/A3/);
 assert.match(panel.innerHTML,/&lt;img/);
 assert.doesNotMatch(panel.innerHTML,/<img/);
 local.renderExploracionSemantica({devolucion:{cobertura:{}}});
 assert.equal(panel.hidden,true);
});

test('sin series aplicables no se informa cero por ciento de lectura del archivo',()=>{
 const elements={};const local=crearContexto({document:{getElementById:id=>elements[id]||={innerHTML:''}},escapeHtml:x=>String(x??'')});
 vm.runInContext(app.slice(app.indexOf('function porcentajeLectura('),app.indexOf('function tituloAlcanceSeries(')),local);
 local.renderResumenTiles({hallazgos:[],devolucion:{cobertura:{excel:{lectura:{estado:'insuficiente',series_leidas:0,series_aparentes:0}}}}});
 assert.match(elements['resumen-principales'].innerHTML,/No se pudo calcular/);
 assert.doesNotMatch(elements['resumen-principales'].innerHTML,/0 %/);
 assert.doesNotMatch(elements['resumen-tiles'].innerHTML,/0 %/);
});

test('sin series por periodo se informan las filas incorporadas, no el silencio',()=>{
 const elements={};const local=crearContexto({document:{getElementById:id=>elements[id]||={innerHTML:''}},escapeHtml:x=>String(x??'')});
 vm.runInContext(app.slice(app.indexOf('function porcentajeLectura('),app.indexOf('function tituloAlcanceSeries(')),local);
 const hojas=[{hoja:'Avances',filas_datos:5},{hoja:'Guia',filas_datos:0}];
 local.renderResumenTiles({hallazgos:[],devolucion:{cobertura:{excel:{lectura:{},hojas}}}});
 assert.match(elements['resumen-tiles'].innerHTML,/Filas de datos incorporadas/);
 assert.match(elements['resumen-tiles'].innerHTML,/1 de 2 hojas con datos/);
 assert.doesNotMatch(elements['resumen-tiles'].innerHTML,/0 %/);
});

test('resumen conserva sujeto y explicacion después de dos puntos',()=>{
 const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
 const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');const el={innerHTML:''};
 const ctx=crearContexto({document:{getElementById:()=>el},escapeHtml:s=>String(s),porcentajeLectura:()=>null});
 vm.runInContext(app.slice(app.indexOf('function botonOrigenHallazgo('),app.indexOf('function tituloAlcanceSeries(')),ctx);
 const descripcion='Importaciones y exportaciones se mueven juntas: queda como pregunta abierta para revisar sus causas.';
 ctx.renderPrincipalesHallazgos({hallazgos:[{descripcion,evidencia:{}}],saneamiento:{orientacion_analisis:'Verificar suma',controles_solicitados:{controles:[{nombre:'Suma',estado:'no_evaluable',resultado:'Faltan componentes'}]}}},null);
 assert.ok(el.innerHTML.includes(descripcion));
 assert.ok(el.innerHTML.indexOf('sin evaluar')<el.innerHTML.indexOf('Principales revisiones'));
});

test('reporte conserva referencias técnicas desplegables y oculta grupos vacíos',()=>{
 const ctx=crearContexto({escapeHtml:s=>String(s)});
 vm.runInContext(app.slice(app.indexOf('function nombreLenteLegible('),app.indexOf('function resumenEvidencia(')),ctx);
 vm.runInContext(app.slice(app.indexOf('function botonOrigenHallazgo('),app.indexOf('function renderPrincipalesHallazgos(')),ctx);
 vm.runInContext(app.slice(app.indexOf('function renderDeltaCorridas(')),ctx);
 const r={casos_revision:1,senales_control:1,senales_contexto:0,informe_id:1,aclaracion:'',contexto:[],casos:[{primary_finding:{id:1,lente:'cronista',descripcion:'Revisar variación',evidencia:{}},prioridad:'media',cantidad_senales:1,criterio:'Temporal',root_cause_id:'caso-abc',related_findings:[]}]};
 const html=ctx.renderCasosRevision(r,{});assert.match(html,/Cambios entre períodos/);assert.match(html,/<summary>Cómo se agruparon<\/summary>/);assert.match(html,/caso-abc/);assert.doesNotMatch(html,/0 grupos/);
 r.contexto=[{periodo:'2026',hoja:'Hoja',cuadro:1,cantidad:1,referencias:[{descripcion:'Variación real'}]}];assert.match(ctx.renderCasosRevision(r,{}),/Variación real/);
});

test('el resto de las señales se anuncia en singular o plural, nunca «señal(es)»',()=>{
 const elements={};const doc={getElementById:id=>elements[id] ||= {innerHTML:''}};
 const local=crearContexto({document:doc,escapeHtml:x=>String(x??'')});
 const fn=app.slice(app.indexOf('function porcentajeLectura('),app.indexOf('function tituloAlcanceSeries('));
 vm.runInContext(fn,local);
 const señal=(i)=>({id:i,descripcion:'Diferencia a verificar',evidencia:{puntaje_prioridad:i,hoja:'H1',celda:'B2'}});
 local.renderPrincipalesHallazgos({hallazgos:Array.from({length:6},(_,i)=>señal(i+1))},null);
 assert.match(elements['resumen-principales'].innerHTML,/Y 1 señal más/);
 local.renderPrincipalesHallazgos({hallazgos:Array.from({length:8},(_,i)=>señal(i+1))},null);
 assert.match(elements['resumen-principales'].innerHTML,/Y 3 señales más/);
 assert.doesNotMatch(elements['resumen-principales'].innerHTML,/señal\(es\)/);
});

test('el resumen no muestra entidades escapadas dos veces ni abre HTML',()=>{
 const elements={};
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
 const local=crearContexto({document:{getElementById:id=>elements[id]||={innerHTML:''}},escapeHtml:esc});
 vm.runInContext(app.slice(app.indexOf('function porcentajeLectura('),app.indexOf('function tituloAlcanceSeries(')),local);
 local.renderPrincipalesHallazgos({hallazgos:[{id:1,descripcion:esc("Total de l'área <b>"),evidencia:{}}]},null);
 const html=elements['resumen-principales'].innerHTML;
 assert.ok(html.includes("l&#39;área &lt;b&gt;"));
 assert.doesNotMatch(html,/&amp;#39;/);
 assert.doesNotMatch(html,/<b>/);
});
