// Revisión rápida y revisión profunda en la pantalla: los dos botones, el envío de cada modo y el paso a la profunda.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const leer = (f) => fs.readFileSync(path.join(__dirname, '..', 'static', f), 'utf8');
const html = leer('index.html');
const app = leer('app.js');

function modulo() {
  const window = {};
  const ctx = { window, FormData, Map, Number };
  vm.createContext(ctx);
  vm.runInContext(leer('revision-modo.js'), ctx);
  return window.RevisionModo;
}

// Las dos funciones de app.js que envían la carga, con lo que usan de la página reemplazado.
function pantalla({ guardadas = {} } = {}) {
  const inicio = app.indexOf('async function enviarRevision(');
  const codigo = app.slice(inicio, app.indexOf('async function ejecutarAnalisisRapido('));
  const els = {};
  const el = (id) => (els[id] ??= { id, style: {}, hidden: false, textContent: '', disabled: false });
  const llamadas = [];
  const ctx = {
    window: {
      RevisionModo: {
        guardar: (id, f) => { guardadas[id] = f; },
        paraProfunda: (id) => {
          if (!guardadas[id]) return null;
          const f = new FormData();
          for (const [k, v] of guardadas[id].entries()) f.append(k, v);
          f.set('modo_revision', 'profunda');
          return f;
        },
      },
      prepararYConfirmarInforme: async (form) => { llamadas.push(['profunda', form]); return { informe_id: 21, job: { id: 2 } }; },
    },
    document: { getElementById: el, querySelector: () => el('tarjeta') },
    apiFetchForm: async (ruta, form) => { llamadas.push(['directo', form]); return { informe_id: 20, job: { id: 1 } }; },
    botonesRevision: [el('r'), el('p')], btnDetectarFormulas: null, state: { detalleId: 20 },
    mostrarVista: (v) => llamadas.push(['vista', v]), toast: () => {}, cargarAreas: async () => {},
    abrirDetalle: (id) => llamadas.push(['abrir', id]), renderListaArchivos: () => {}, FormData,
  };
  vm.createContext(ctx);
  vm.runInContext(codigo, ctx);
  return { ctx, els, llamadas, guardadas };
}

test('Analizar ofrece dos revisiones: la rápida es la acción principal', () => {
  assert.match(html, /<button id="btn-revision-rapida" class="btn btn-primary" disabled>Revisión rápida<\/button>\s*<p class="hint">Sólo cuentas, sin IA\. El procesamiento suele tardar segundos; si hay otro análisis en curso, espera en cola\. Sirve para cualquier tamaño de libro\.<\/p>/);
  assert.match(html, /<button id="btn-revision-profunda" class="btn btn-secondary" disabled>Revisión profunda<\/button>\s*<p class="hint">La IA interpreta cada cuadro, vos confirmás y corren todas las lentes\. Minutos\.<\/p>/);
  assert.doesNotMatch(html, /btn-analizar-rapido|Interpretar y revisar/);
  assert.ok(html.indexOf('/revision-modo.js') < html.indexOf('/app.js'), 'el módulo carga antes que app.js');
  assert.match(html, /id="btn-pasar-profunda"[^>]*>Pasar a revisión profunda</);
  // Los ejemplos siguen mostrando el recorrido completo, con confirmación.
  assert.match(app, /form\.append\("modo_revision", "profunda"\);[\s\S]{0,120}prepararYConfirmarInforme\(form/);
});

test('un informe sin el campo fue una revisión profunda', () => {
  const m = modulo();
  assert.equal(m.nombre({}), 'Revisión profunda');
  assert.equal(m.nombre({ modo_revision: 'rapida' }), 'Revisión rápida');
  assert.equal(m.nombre({ saneamiento: { modo_revision: 'rapida' } }), 'Revisión rápida');
  assert.equal(m.modo(null), 'profunda');
});

test('la profunda reusa el mismo File de la rápida; si no está en la pestaña, no inventa nada', () => {
  const m = modulo();
  const archivo = new File(['a,b'], 'libro.csv');
  const form = new FormData();
  form.append('archivos', archivo);
  form.append('dominio', 'presupuestario');
  form.append('modo_revision', 'rapida');
  m.guardar(7, form);
  form.set('dominio', 'otro');  // cambiar el formulario después no altera lo guardado
  const profunda = m.paraProfunda(7);
  assert.equal(profunda.get('modo_revision'), 'profunda');
  assert.equal(profunda.get('archivos'), archivo);
  assert.equal(profunda.get('dominio'), 'presupuestario');
  assert.equal(m.paraProfunda(8), null);
});

test('la rápida va directo a la cola y guarda los archivos; la profunda pasa por la confirmación', async () => {
  const p = pantalla();
  const form = new FormData();
  form.append('archivos', new File(['x'], 'a.xlsx'));
  const r = await p.ctx.enviarRevision(form, 'rapida');
  assert.equal(r.informe_id, 20);
  assert.deepEqual(p.llamadas.map((l) => l[0]), ['directo']);
  assert.equal(p.llamadas[0][1].get('modo_revision'), 'rapida');
  assert.equal(p.guardadas[20], form);
  assert.equal(p.els['cargando-rapida'].hidden, false);
  assert.equal(p.els['cargando-profunda'].hidden, true);
  await p.ctx.enviarRevision(new FormData(), 'profunda');
  assert.equal(p.llamadas[1][0], 'profunda');
  assert.equal(p.llamadas[1][1].get('modo_revision'), 'profunda');
  assert.equal(p.els['analizar-cargando'].style.display, 'none');
});

test('«Pasar a revisión profunda» reenvía los mismos archivos o pide elegirlos de nuevo', async () => {
  const sin = pantalla();
  await sin.ctx.pasarARevisionProfunda();
  assert.match(sin.els['pasar-profunda-aviso'].textContent, /ya no están en esta pestaña.*Elegilos de nuevo/);
  assert.equal(sin.llamadas.length, 0);

  const archivo = new File(['x'], 'a.xlsx');
  const guardada = new FormData();
  guardada.append('archivos', archivo);
  guardada.append('modo_revision', 'rapida');
  const con = pantalla({ guardadas: { 20: guardada } });
  await con.ctx.pasarARevisionProfunda();
  const [vista, envio, abrir] = con.llamadas;
  assert.deepEqual(vista, ['vista', 'analizar']);
  assert.equal(envio[0], 'profunda');
  assert.equal(envio[1].get('archivos'), archivo);
  assert.equal(envio[1].get('modo_revision'), 'profunda');
  assert.deepEqual(abrir, ['abrir', 21]);
});
