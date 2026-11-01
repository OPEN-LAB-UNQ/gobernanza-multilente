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
  showModal() {}
  close() {}
  focus() {}
}
function entorno() {
  const body = new Elemento('body');
  const window = {};
  const ctx = { window, FormData, Map, Set, Promise, setTimeout: fn => setImmediate(fn), document: { body, createElement: tag => new Elemento(tag) } };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('static/interpretacion.js', 'utf8'), ctx);
  return { window, body };
}
const pausa = () => new Promise(resolve => setImmediate(resolve));
const cuadro = (n, hoja, extra = {}) => ({ id: `c${n}`, archivo: 'libro.xlsx', hoja, bloque: n, columnas: ['Importe'], lecturas_validas: 3,
  propuesta: { tipo: 'presupuesto', institucion: 'organismo_publico', regimen: 'publico', eje: 'ninguno', descripcion: `Cuadro ${n}`, roles: { Importe: 'importe' } },
  cobertura: { filas_total: 1, filas_presentadas: 1 }, ...extra });
function propuesta(cuadros) {
  return { informe_id: 7, estado: 'pendiente_confirmacion', interpretacion: { revision: 1,
    catalogos: { instituciones: ['organismo_publico'], regimenes: ['publico'], tipos: ['presupuesto', 'desconocido'], roles: ['importe'], ejes: ['ninguno'] }, cuadros } };
}
const textos = el => [el.textContent, ...el.children.flatMap(textos)];

test('muchos cuadros: resumen por tipo, detalle plegado y a la vista sólo los que piden revisión', async () => {
  const e = entorno();
  const dudoso = cuadro(9, 'Salta', { lecturas_validas: 1, propuesta: { ...cuadro(9).propuesta, tipo: 'desconocido' } });
  const cuadros = [...Array.from({ length: 8 }, (_, i) => cuadro(i + 1, i < 4 ? 'Jujuy' : 'Chaco')), dudoso];
  e.window.prepararYConfirmarInforme(new FormData(), async () => propuesta(cuadros));
  await pausa();
  const dialog = e.body.children[0];
  const visibles = dialog.children.map(c => c.textContent);
  assert.ok(visibles.includes('9 cuadros en 3 hojas; 1 necesita tu revisión y se muestra abajo:'));
  const lista = dialog.children.find(c => c.tag === 'ul');
  assert.deepEqual(lista.children.map(c => c.textContent), ['8 cuadros: presupuesto · organismo público · régimen público', '1 cuadro: sin clasificar · organismo público · régimen público']);
  const plegado = dialog.children.find(c => c.tag === 'details');
  assert.equal(plegado.children[0].textContent, 'Ver los 9 cuadros uno por uno');
  assert.equal(plegado.children.filter(c => c.tag === 'section').length, 8);
  const sueltos = dialog.children.filter(c => c.tag === 'section');
  assert.equal(sueltos.length, 1);
  assert.ok(textos(sueltos[0]).includes('libro.xlsx · Salta · cuadro 9'));
  assert.notEqual(plegado.open, true);
  dialog.querySelectorAll('button').find(b => b.textContent === 'No, modificar').onclick();
  assert.equal(plegado.open, true);
});

test('pocos cuadros se siguen mostrando uno por uno, sin resumen', async () => {
  const e = entorno();
  e.window.prepararYConfirmarInforme(new FormData(), async () => propuesta([cuadro(1, 'A'), cuadro(2, 'A')]));
  await pausa();
  const dialog = e.body.children[0];
  assert.equal(dialog.children.filter(c => c.tag === 'details').length, 0);
  assert.equal(dialog.children.filter(c => c.tag === 'section').length, 2);
});
