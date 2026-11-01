const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const HELPERS = app.slice(app.indexOf('function contar('), app.indexOf('const RECORRIDOS ='));
const crearContexto = (base) => { const c = vm.createContext(base); vm.runInContext(HELPERS, c); return c; };
function entorno(data){
 const els={},timers=[],state={areas:[{}],detalleId:1,analysisTheaterId:1,analysisTheaterStartedAt:Date.now(),detallePollTimer:null};
 const ctx={state,Date,Set,DURACION_MINIMA_ESCENA_ANALISIS_MS:12000,apiFetch:async()=>data,cargarAreas:async()=>{},escapeDeep:x=>x,escapeHtml:x=>x,areaNombre:()=>'',fmtFecha:()=>'',descripcionNormalizacionSeries:()=>'',descripcionPdf:()=>'',renderLecturaCuadro:()=>'',toast:()=>{},setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length;},clearTimeout:()=>{},document:{getElementById:id=>els[id]??=( {style:{},textContent:'',innerHTML:''}),querySelector:()=>null},renderTrazaJob:(job,el)=>{el.textContent=job.estado;}};
 for(const name of ['actualizarStepper','renderResumenTiles','renderLecturaEjecutiva','renderTrazabilidadAnalisis','renderGarantiasEjecucion','renderEvaluacionPiloto','renderCriterioRazonable','renderCoberturaLimites','renderInformeLentes','renderHallazgos','renderTriangulacion','renderPreguntaSugerida','renderComoLeerResultado','actualizarGuiaPrimeraVez'])ctx[name]=()=>{};
 crearContexto(ctx);
 vm.runInContext(app.slice(app.indexOf('function renderJobEnProgreso('),app.indexOf('const ETAPAS_ANALISIS =')),ctx);
 return {ctx,state,els,timers};
}
const terminado={id:1,area_id:1,periodo:2026,n_filas:1,devolucion:{mensaje:'Resultado listo'},job:{estado:'finalizado'}};
test('resultado disponible se muestra sin temporizador artificial',async()=>{const e=entorno(terminado);await e.ctx.refrescarDetalle();assert.equal(e.els['detalle-resultado'].style.display,'block');assert.equal(e.els['devolucion-mensaje'].textContent,'Resultado listo');assert.equal(e.timers.length,0);});
test('procesamiento real conserva consulta de estado',async()=>{const e=entorno({...terminado,devolucion:null,job:{estado:'procesando'}});await e.ctx.refrescarDetalle();assert.equal(e.els['analizar-progreso'].style.display,'block');assert.equal(e.els['detalle-resultado'].style.display,'none');assert.deepEqual(e.timers.map(t=>t.ms),[4500]);});
test('fallo real se muestra sin espera artificial ni nueva consulta automática',async()=>{const e=entorno({...terminado,devolucion:null,job:{estado:'error'}});await e.ctx.refrescarDetalle();assert.equal(e.els['progreso-log'].textContent,'error');assert.equal(e.els['analizar-progreso'].style.display,'block');assert.equal(e.timers.length,0);});
test('respuesta tardía no reemplaza otro informe abierto',async()=>{const e=entorno(terminado);let finish;e.ctx.apiFetch=()=>new Promise(resolve=>finish=resolve);const pending=e.ctx.refrescarDetalle();e.state.detalleId=2;e.state.detalle={id:2};finish(terminado);await pending;assert.equal(e.state.detalle.id,2);assert.equal(e.timers.length,0);});
