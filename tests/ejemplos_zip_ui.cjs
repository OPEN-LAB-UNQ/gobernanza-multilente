// Ejecuta las funciones reales del botón con red/DOM simulados; sin navegador ni IA.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const block = app.split('// ---------- pares de ejemplos: flujo real sin espera visual artificial ----------')[1]
  .split('// ---------- fin de pares de ejemplos ----------')[0];
assert.ok(block);

function fixture({ states = ['finalizado'], role = true, selected = ['claude'], downloadFailure = false, confirm = async () => {} } = {}) {
  const calls = { uploads: [], polls: [], downloads: [], clicks: 0, delays: [], messages: [], confirmations: 0 };
  let failures = downloadFailure ? 1 : 0;
  const status = { classList: { toggle() {} }, innerHTML: '' };
  const button = { dataset: { samplePair: '1' } };
  const anew = { dataset: { samplePairNew: '1' } };
  class Form {
    constructor() { this.fields = []; }
    append(...args) { this.fields.push(args); }
  }
  const context = vm.createContext({
    samplePairRuns: new Map(), samplePairBusy: false,
    state: { sampleDocs: ['bueno', 'malo'].map((columna, i) => ({ orden: 1, columna,
      archivo: `/samples/${i}.xlsx`, nombre: `Ejemplo ${i}`, opciones: { revisar_metodo_calculo: true } })) },
    document: {
      querySelectorAll(selector) { return selector === '[data-sample-pair]' ? [button]
        : selector === '[data-sample-pair-new]' ? [anew]
        : selected.map(value => ({ value })); },
      getElementById() { return status; },
      createElement() { return { click() { calls.clicks++; }, remove() {} }; },
      body: { appendChild() {} },
    },
    optModoUsoMultilente: { value: 'informe_en_construccion' },
    puedeOperarInformes: () => role,
    escapeHtml: s => String(s).replaceAll('<', '&lt;'),
    toast: (...args) => calls.messages.push(args),
    // El diálogo compartido se prueba con su DOM en interpretacion_previa_ui.cjs.
    // Este adaptador representa su resolución tras la decisión de la persona.
    window: { prepararYConfirmarInforme: async (form, enviar) => {
      calls.confirmations++;
      await confirm();
      return enviar(form);
    } },
    fetch: async () => ({ ok: true, blob: async () => ({ content: 'xlsx' }) }),
    FormData: Form, URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
    setTimeout: (fn, duration) => { calls.delays.push(duration); fn(); },
    apiFetchForm: async (url, form) => {
      calls.uploads.push({ url, fields: form.fields });
      const id = calls.uploads.length;
      return { informe_id: id, job: { id } };
    },
    apiFetch: async url => {
      const round = Math.floor(calls.polls.length / 2);
      calls.polls.push(url);
      return { estado: states[Math.min(round, states.length - 1)] };
    },
    apiFetchDownload: async (url, ids) => {
      calls.downloads.push({ url, ids });
      if (failures-- > 0) throw new Error('Fallo de descarga');
      return { blob: {}, filename: 'ejemplos-caso-1.zip' };
    },
  });
  vm.runInContext(block, context);
  return { context, calls, button, anew, status, run: (...args) => context.ejecutarParEjemplos(...args) };
}

test('un clic: dos cargas con opciones y modelos, un ZIP y sin espera artificial', async () => {
  const f = fixture();
  await f.run(1);
  assert.equal(f.calls.uploads.length, 2);
  assert.equal(f.calls.confirmations, 2);
  for (const upload of f.calls.uploads) {
    assert.equal(upload.url, '/analisis-rapido');
    const fields = Object.fromEntries(upload.fields.map(([k, v]) => [k, v]));
    assert.equal(fields.notificar, 'false');
    assert.equal(fields.modelos, 'claude');
    assert.equal(fields.revisar_metodo_calculo, 'true');
    assert.equal(fields.modo_uso_multilente, 'informe_en_construccion');
  }
  assert.equal(f.calls.downloads.length, 1);
  assert.equal(JSON.stringify(f.calls.downloads[0].ids), '{"sin_senal":1,"con_senal":2}');
  assert.equal(f.calls.clicks, 1);
  assert.deepEqual(f.calls.delays, [30000]); // sólo liberar el blob, no retrasar el reporte
  assert.match(f.button.textContent, /Descargar ZIP otra vez/);
});

test('la espera sólo consulta el estado real hasta finalizar ambos trabajos', async () => {
  const f = fixture({ states: ['pendiente', 'procesando', 'finalizado'] });
  await f.run(1);
  assert.equal(f.calls.polls.length, 6);
  assert.deepEqual(f.calls.delays, [1500, 1500, 30000]);
  assert.equal(f.calls.downloads.length, 1);
});

test('reintentar una descarga fallida no duplica informes', async () => {
  const f = fixture({ downloadFailure: true });
  await f.run(1);
  assert.equal(f.calls.clicks, 0);
  await f.run(1);
  assert.equal(f.calls.uploads.length, 2);
  assert.equal(f.calls.downloads.length, 2);
  assert.equal(f.calls.clicks, 1);
});

test('un trabajo fallido no permite un ZIP incompleto', async () => {
  const f = fixture({ states: ['error'] });
  await f.run(1);
  assert.equal(f.calls.downloads.length, 0);
  assert.equal(f.button.disabled, true);
  assert.equal(f.anew.hidden, false);
  assert.match(f.status.innerHTML, /terminó con error/);
  assert.match(f.status.innerHTML, /#\/informe\/1/);
});

test('sin permisos o sin modelos no inicia tareas', async () => {
  for (const options of [{ role: false }, { selected: [] }]) {
    const f = fixture(options);
    await f.run(1);
    assert.equal(f.calls.uploads.length, 0);
    assert.equal(f.calls.downloads.length, 0);
  }
});

test('doble clic no duplica; ejecutar nuevamente requiere acción explícita', async () => {
  const f = fixture();
  await Promise.all([f.run(1), f.run(1)]);
  assert.equal(f.calls.uploads.length, 2);
  await f.run(1);
  assert.equal(f.calls.uploads.length, 2);
  await f.run(1, true);
  assert.equal(f.calls.uploads.length, 4);
});

test('el par espera la confirmación de cada ejemplo antes de consultar trabajos o descargar', async () => {
  const decisiones = [];
  const f = fixture({ confirm: () => new Promise(resolve => decisiones.push(resolve)) });
  const proceso = f.run(1);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.calls.confirmations, 1);
  assert.equal(f.calls.uploads.length, 0);
  assert.equal(f.calls.polls.length, 0);
  decisiones[0]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.calls.confirmations, 2);
  assert.equal(f.calls.uploads.length, 1);
  assert.equal(f.calls.polls.length, 0);
  assert.equal(f.calls.downloads.length, 0);
  decisiones[1]();
  await proceso;
  assert.equal(f.calls.uploads.length, 2);
  assert.equal(f.calls.downloads.length, 1);
});

test('cancelar la confirmación de un ejemplo no permite descargar un par incompleto', async () => {
  const f = fixture({ confirm: async () => { throw new Error('Carga pendiente de confirmación'); } });
  await f.run(1);
  assert.equal(f.calls.confirmations, 1);
  assert.equal(f.calls.uploads.length, 0);
  assert.equal(f.calls.polls.length, 0);
  assert.equal(f.calls.downloads.length, 0);
});
