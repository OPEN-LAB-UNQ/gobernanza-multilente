// La espera de la interpretación muestra el avance real y no se rinde ante un corte breve del servidor.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Elemento {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.events = {}; this.textContent = ''; this.disabled = false; }
  append(el) { el.parent = this; this.children.push(el); }
  replaceChildren() { this.children = []; }
  setAttribute(k, v) { this[k] = v; }
  addEventListener(k, f) { this.events[k] = f; }
  querySelectorAll(s) { const tags = s.split(',').map(x => x.trim()); return this.children.flatMap(el => [...(tags.includes(el.tag) ? [el] : []), ...el.querySelectorAll(s)]); }
  querySelector(s) { return this.querySelectorAll(s)[0]; }
  remove() { this.parent.children = this.parent.children.filter(c => c !== this); }
  showModal() { this.abierto = true; }
  close() { this.abierto = false; }
}

function entorno(respuestas) {
  const body = new Elemento('body');
  const avance = new Elemento('p');
  const cancelar = new Elemento('button');
  const textos = [];
  const pedidos = [];
  const fetch = async (url, opciones) => {
    pedidos.push([url, (opciones || {}).method || 'GET']);
    if (url.endsWith('/cancelar')) return { ok: true, status: 200, json: async () => ({ estado: 'cancelada' }) };
    const r = respuestas.shift();
    if (r instanceof Error) throw r;
    return r;
  };
  const window = {};
  const nodos = { 'interpretacion-avance': avance, 'interpretacion-cancelar': cancelar };
  const document = { body, createElement: tag => new Elemento(tag), getElementById: id => nodos[id] || null };
  const ctx = { window, FormData, Map, Set, Promise, fetch, document, setTimeout: fn => setImmediate(() => { textos.push(avance.textContent); fn(); }) };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('static/interpretacion.js', 'utf8'), ctx);
  return { window, body, avance, cancelar, textos, pedidos };
}

const ok = dato => ({ ok: true, status: 200, json: async () => dato });
const propuesta = { informe_id: 7, estado: 'pendiente_confirmacion', interpretacion: { revision: 1, catalogos: { instituciones: ['organismo_publico'], regimenes: ['publico'], tipos: ['estadistica'], roles: ['importe'], ejes: ['ninguno'] },
  cuadros: [{ id: 'c', archivo: 'libro.xlsx', hoja: 'Córdoba', bloque: 1, columnas: ['Gasto'], lecturas_validas: 3,
    propuesta: { tipo: 'estadistica', institucion: 'organismo_publico', regimen: 'publico', eje: 'ninguno', descripcion: 'Gasto', roles: { Gasto: 'importe' } },
    cobertura: { modo: 'inicial', filas_total: 3, filas_presentadas: 3 } }] } };

test('muestra cuántos cuadros se leyeron y sigue esperando tras un corte breve', async () => {
  const e = entorno([
    ok({ informe_id: 7, estado: 'interpretando', avance: { leidos: 37, total: 172, hoja: 'Córdoba' } }),
    new Error('red caída'),
    { ok: false, status: 502, json: async () => ({}) },
    ok(propuesta),
  ]);
  const form = new FormData(); form.append('archivos', 'original');
  e.window.prepararYConfirmarInforme(form, async () => ({ informe_id: 7, estado: 'interpretando', avance: { leidos: 0, total: 172 } }));
  for (let i = 0; i < 12 && !e.body.querySelector('dialog'); i++) await new Promise(r => setImmediate(r));
  assert.ok(e.body.querySelector('dialog'), 'tras el corte breve llega la propuesta para confirmar');
  assert.ok(e.textos.some(t => t.includes('37 de 172') && t.includes('Córdoba')));
});

test('«Cancelar lectura» avisa al servidor y termina la espera sin analizar', async () => {
  const e = entorno(Array.from({ length: 50 }, () => ok({ informe_id: 7, estado: 'interpretando', avance: { leidos: 3, total: 172 } })));
  const form = new FormData(); form.append('archivos', 'original');
  const espera = e.window.prepararYConfirmarInforme(form, async () => ({ informe_id: 7, estado: 'interpretando' }));
  await new Promise(r => setImmediate(r));
  assert.equal(typeof e.cancelar.onclick, 'function');
  await e.cancelar.onclick();
  await assert.rejects(espera, err => err.cancelada === true && /Lectura cancelada/.test(err.message));
  assert.ok(e.pedidos.some(([url, metodo]) => url === '/api/interpretacion-previa/7/cancelar' && metodo === 'POST'));
  assert.equal(e.cancelar.onclick, null);
  assert.ok(!e.body.querySelector('dialog'), 'no se ofrece confirmar una lectura cancelada');
});

test('una cancelación hecha en otra pestaña se informa como cancelación, no como error', async () => {
  const e = entorno([ok({ informe_id: 7, estado: 'error', cancelada: true, error: 'Lectura cancelada a pedido.' })]);
  const form = new FormData(); form.append('archivos', 'original');
  await assert.rejects(e.window.prepararYConfirmarInforme(form, async () => ({ informe_id: 7, estado: 'interpretando' })),
    err => err.cancelada === true && err.message === 'Lectura cancelada a pedido.');
});

test('un 404 no se reintenta', async () => {
  const e = entorno([{ ok: false, status: 404, json: async () => ({}) }]);
  const form = new FormData(); form.append('archivos', 'original');
  await assert.rejects(e.window.prepararYConfirmarInforme(form, async () => ({ informe_id: 7, estado: 'interpretando' })),
    /No se pudo consultar la lectura previa/);
});
