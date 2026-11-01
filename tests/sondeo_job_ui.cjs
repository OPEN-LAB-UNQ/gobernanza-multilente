// Mientras se analiza se consulta el estado del trabajo, no el informe completo (8,5 MB en un libro de 172 cuadros).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const HELPERS = app.slice(app.indexOf('function contar('), app.indexOf('const RECORRIDOS ='));

function entorno(respuestasJob) {
  const els = {}, timers = [], pedidos = [];
  const state = { areas: [{}], detalleId: 1, detallePollTimer: null };
  const procesando = { id: 1, area_id: 1, periodo: 2026, n_filas: 1, devolucion: null, job: { id: 9, estado: 'procesando' } };
  const terminado = { ...procesando, devolucion: { mensaje: 'Resultado listo' }, job: { id: 9, estado: 'finalizado' } };
  const ctx = { state, Date, Set, DURACION_MINIMA_ESCENA_ANALISIS_MS: 12000,
    apiFetch: async (p) => {
      pedidos.push(p);
      if (p.startsWith('/jobs/')) {
        const r = respuestasJob.shift();
        if (r instanceof Error) throw r;
        return r;
      }
      return pedidos.filter(x => x.endsWith('/detalle')).length === 1 ? procesando : terminado;
    },
    cargarAreas: async () => {}, escapeDeep: x => x, escapeHtml: x => x, areaNombre: () => '', fmtFecha: () => '',
    descripcionNormalizacionSeries: () => '', descripcionPdf: () => '', renderLecturaCuadro: () => '', toast: () => {},
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; }, clearTimeout: () => {},
    document: { getElementById: id => els[id] ??= ({ style: {}, textContent: '', innerHTML: '' }), querySelector: () => null },
    renderTrazaJob: (job, el) => { el.textContent = job.estado; } };
  for (const n of ['actualizarStepper', 'renderResumenTiles', 'renderLecturaEjecutiva', 'renderTrazabilidadAnalisis', 'renderGarantiasEjecucion', 'renderEvaluacionPiloto', 'renderCriterioRazonable', 'renderCoberturaLimites', 'renderInformeLentes', 'renderHallazgos', 'renderTriangulacion', 'renderPreguntaSugerida', 'renderComoLeerResultado', 'actualizarGuiaPrimeraVez']) ctx[n] = () => {};
  vm.createContext(ctx);
  vm.runInContext(HELPERS, ctx);
  vm.runInContext(app.slice(app.indexOf('function renderJobEnProgreso('), app.indexOf('const ETAPAS_ANALISIS =')), ctx);
  return { ctx, els, timers, pedidos };
}

async function correrTimers(e, n) {
  for (let i = 0; i < n && e.timers.length; i++) await e.timers.shift().fn();
}

test('durante el análisis se consulta el trabajo y el informe completo se pide sólo al terminar', async () => {
  const e = entorno([{ id: 9, estado: 'procesando' }, { id: 9, estado: 'procesando' }, { id: 9, estado: 'finalizado' }]);
  await e.ctx.refrescarDetalle();
  await correrTimers(e, 5);
  assert.deepEqual(e.pedidos, ['/informes/1/detalle', '/jobs/9', '/jobs/9', '/jobs/9', '/informes/1/detalle']);
  assert.equal(e.els['detalle-resultado'].style.display, 'block');
});

test('un corte aislado del estado se reintenta sin pedir el informe completo', async () => {
  const e = entorno([new Error('red'), { id: 9, estado: 'finalizado' }]);
  await e.ctx.refrescarDetalle();
  await correrTimers(e, 4);
  assert.deepEqual(e.pedidos, ['/informes/1/detalle', '/jobs/9', '/jobs/9', '/informes/1/detalle']);
});
