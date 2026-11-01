const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const snippet = source.slice(source.indexOf('function textoLecturaRespuesta('), source.indexOf('function renderHallazgos('));
const ctx = { escapeHtmlUnaVez: (s) => String(s ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;') };
vm.createContext(ctx);
vm.runInContext(snippet, ctx);
const render = ctx.renderLecturaCuadro;
const base = { modo: 'activo', preguntas: [], sin_leer: [], resumen: { estado: 'completada', tramos: 1, tramos_con_lectura: 1, relaciones_acordadas: 0 } };

test('la lectura sin preguntas sigue visible y no certifica el cuadro', () => {
  assert.equal(render(null), '');
  const html = render(base);
  assert.match(html, /Lectura recibida/);
  assert.match(html, /No hubo relaciones acordadas/);
  assert.match(html, /no certifica/);
});
test('una caída de los modelos muestra lectura no completada', () => {
  const html = render({ ...base, resumen: { ...base.resumen, estado: 'no_completada', tramos_con_lectura: 0, lecturas_fallidas: 3 } });
  assert.match(html, /Lectura no completada/);
  assert.match(html, /3 lecturas de modelos no se completaron/);
  assert.doesNotMatch(html, /Lectura recibida/);
});
test('la pregunta identifica archivo y hoja y escapa el contenido', () => {
  const html = render({ ...base, puede_confirmar: true, preguntas: [{ id: 'abc', archivo: '<a.xlsx>', hoja: 'Sur', fundamento: '<script>', relacion: 'B15 = B3+B4', respuesta: true }] });
  assert.match(html, /&lt;a.xlsx>/);
  assert.match(html, /hoja Sur/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /aria-pressed="true"/);
});
test('la versión antigua avisa y no permite confirmar', () => {
  const html = render({ ...base, requiere_reanalisis: true, puede_confirmar: false, preguntas: [{ id: 'abc', hoja: 'H', relacion: 'x' }] });
  assert.match(html, /Volvé a analizar/);
  assert.doesNotMatch(html, /<button/);
});
test('los recortes también identifican el archivo', () => {
  assert.match(render({ ...base, sin_leer: [{ archivo: 'b.xlsx', hoja: 'Norte', motivo: 'hoja oculta' }] }), /b.xlsx · hoja Norte/);
});
test('una falla interna del lector se distingue de una caída de proveedores', () => {
  const html = render({ ...base, fallo: { etapa: 'analizar', motivo: 'No se pudo completar <lector>' }, resumen: { ...base.resumen, estado: 'no_completada' } });
  assert.match(html, /Lectura no completada/);
  assert.match(html, /No se pudo completar &lt;lector>/);
  assert.doesNotMatch(html, /No hubo suficientes respuestas/);
});
test('el límite de cinco no oculta el total de diferencias ni su relación', () => {
  const html = render({ ...base, resumen: { ...base.resumen, relaciones_controladas: 1, diferencias_total: 140, diferencias_mostradas: 5, diferencias_no_mostradas: 135, limites_de_muestra: [{ archivo: '<a.xlsx>', hoja: 'H', relacion: 'C = A+B', total: 140, mostradas: 5 }] } });
  assert.match(html, /5 de 140 diferencias/);
  assert.match(html, /135 adicionales/);
  assert.match(html, /&lt;a.xlsx>/);
  assert.match(html, /no garantiza que se hayan identificado y controlado todos los totales/);
});
test('los bloques anchos muestran coordenadas originales y escapan los rótulos', () => {
  const html = render({ ...base, hojas: [{ archivo: '<original.xlsx>', hoja: 'Ventas', columnas: ['CM', 'CO'], filas: [1, 115] }] });
  assert.match(html, /Ver hojas y bloques leídos/);
  assert.match(html, /columnas CM a CO · filas 1 a 115/);
  assert.match(html, /&lt;original.xlsx>/);
  assert.doesNotMatch(html, /<original.xlsx>/);
});
test('guardar bloquea envíos repetidos y vuelve a habilitar tras un error', async () => {
  let llamadas = 0, finalizar;
  const respuesta = { textContent: '' };
  const botones = ['si', 'no'].map((valor) => ({ disabled: false, dataset: { lectorConfirma: valor, pregunta: 'abc' }, classList: { toggle() {} }, setAttribute() {} }));
  const item = { querySelectorAll: () => botones, querySelector: () => respuesta };
  botones.forEach((b) => { b.closest = () => item; });
  ctx.state = { detalleId: 12 };
  ctx.toast = () => {};
  ctx.apiFetch = () => { llamadas++; return new Promise((resolve, reject) => { finalizar = reject; }); };
  const pending = ctx.confirmarLectura({ currentTarget: botones[0] });
  assert.equal(botones[0].disabled, true);
  await ctx.confirmarLectura({ currentTarget: botones[0] });
  assert.equal(llamadas, 1);
  finalizar(new Error('sin conexión'));
  await pending;
  assert.ok(botones.every((b) => !b.disabled));
  assert.equal(respuesta.textContent, '');
});
