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
  focus() {}
}
function entorno(fetch = async () => { throw new Error('consulta inesperada'); }) {
  const body = new Elemento('body');
  const window = {};
  const ctx = { window, FormData, Map, Set, Promise, fetch, setTimeout: fn => setImmediate(fn), document: { body, createElement: tag => new Elemento(tag) } };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('static/interpretacion.js', 'utf8'), ctx);
  const boton = texto => body.querySelectorAll('button').find(el => el.textContent === texto);
  return { window, body, boton };
}
const pausa = () => new Promise(resolve => setImmediate(resolve));
function propuesta(revision = 1) {
  return { informe_id: 7, estado: 'pendiente_confirmacion', interpretacion: {
    revision, catalogos: { instituciones: ['universidad'], regimenes: ['publico'], tipos: ['presupuesto', 'pagos'], roles: ['importe', 'fecha_operacion'], ejes: ['ninguno', 'operaciones'] },
    cuadros: [{ id: 'cuadro', archivo: '<script>archivo</script>.xlsx', hoja: 'H', bloque: 1, columnas: ['Importe'], lecturas_validas: 3,
      propuesta: { tipo: 'presupuesto', institucion: 'universidad', regimen: 'publico', eje: 'ninguno', descripcion: '<img src=x>', roles: { Importe: 'importe' } },
      cobertura: { modo: revision === 1 ? 'inicial' : 'detallada', filas_total: 100, filas_presentadas: revision === 1 ? 24 : 100 } }],
  } };
}
test('no analiza automáticamente; relectura exige una confirmación nueva y usa la nueva revisión', async () => {
  const e = entorno(), llamadas = [];
  const form = new FormData(); form.append('archivos', 'original');
  const pendiente = e.window.prepararYConfirmarInforme(form, async f => {
    llamadas.push(f);
    if (f.get('interpretacion_accion') === 'detallada') return propuesta(2);
    if (f.get('interpretacion_accion') === 'confirmar') return { informe_id: 7, job: { id: 8 } };
    return propuesta();
  });
  await pausa();
  assert.equal(llamadas.length, 1);
  assert.ok(e.boton('Sí, analizar'));
  await e.boton('Reanalizar con más detalle').onclick(); await pausa();
  assert.equal(llamadas.length, 2);
  assert.ok(e.boton('Sí, analizar'));
  await e.boton('Sí, analizar').onclick();
  const resultado = await pendiente;
  assert.equal(resultado.job.id, 8);
  assert.equal(llamadas[2].get('interpretacion_revision'), '2');
  assert.equal(llamadas[2].get('archivos'), 'original');
  assert.equal(e.body.children.length, 0);
});
test('modificar conserva lo propuesto hasta confirmar, y envía solamente las correcciones', async () => {
  const e = entorno(), llamadas = [];
  const pendiente = e.window.prepararYConfirmarInforme(new FormData(), async f => {
    llamadas.push(f);
    return f.get('interpretacion_accion') ? { informe_id: 7, job: { id: 8 } } : propuesta();
  });
  await pausa();
  e.boton('No, modificar').onclick();
  assert.equal(llamadas.length, 1);
  const selects = e.body.querySelectorAll('select');
  selects[2].value = 'pagos';
  await e.boton('Confirmar cambios y analizar').onclick();
  await pendiente;
  assert.deepEqual(JSON.parse(llamadas[1].get('interpretacion_correcciones')), { cuadro: { tipo: 'pagos' } });
});
test('fallo al releer conserva el diálogo y las acciones; los textos se insertan sin interpretar HTML', async () => {
  const e = entorno();
  const pendiente = e.window.prepararYConfirmarInforme(new FormData(), async f => {
    if (f.get('interpretacion_accion')) throw new Error('Lectura interrumpida');
    return propuesta();
  });
  const rechazado = assert.rejects(pendiente, /pendiente de confirmación/);
  await pausa();
  await e.boton('Reanalizar con más detalle').onclick(); await pausa();
  assert.ok(e.body.querySelectorAll('p').some(p => p.textContent === 'Lectura interrumpida'));
  assert.ok(e.body.querySelectorAll('p').some(p => p.textContent === '<img src=x>'));
  assert.equal(e.body.querySelectorAll('img').length, 0);
  assert.ok(e.body.querySelectorAll('button').every(b => !b.disabled));
  e.boton('Volver sin analizar').onclick();
  await rechazado;
});

test('una lectura en cola se consulta hasta tener propuesta y nunca se confirma por terminar', async () => {
  let consultas = 0, confirmaciones = 0;
  const e = entorno(async () => ({ ok: true, json: async () => ++consultas === 1 ? { informe_id: 7, estado: 'interpretando' } : propuesta() }));
  const pendiente = e.window.prepararYConfirmarInforme(new FormData(), async form => {
    if (!form.get('interpretacion_accion')) return { informe_id: 7, estado: 'interpretando', job: { id: 9 } };
    confirmaciones++;
    return { informe_id: 7, job: { id: 10 } };
  });
  for (let i = 0; i < 5; i++) await pausa();
  assert.equal(consultas, 2);
  assert.equal(confirmaciones, 0);
  await e.boton('Sí, analizar').onclick();
  await pendiente;
  assert.equal(confirmaciones, 1);
});

test('muestra por qué una lectora quedó inválida sin ejecutar HTML', async () => {
  const e = entorno();
  const p = propuesta();
  p.interpretacion.cuadros[0].lecturas_validas = 1;
  p.interpretacion.cuadros[0].estado_lectoras = {
    deepseek: { error: 'Esquema inválido: referencias inexistentes <img src=x>', reintento_esquema: true },
  };
  const pendiente = e.window.prepararYConfirmarInforme(new FormData(), async () => p);
  const rechazado = assert.rejects(pendiente, /pendiente de confirmación/);
  await pausa();
  assert.ok(e.body.querySelectorAll('p').some(x => x.textContent.includes('referencias inexistentes')));
  assert.equal(e.body.querySelectorAll('img').length, 0);
  e.boton('Volver sin analizar').onclick();
  await rechazado;
});
