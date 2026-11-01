/* Ubicaciones registradas por el control: no infiere filas de Excel desde registros normalizados. */
(() => {
  const el = id => document.getElementById(id), dialog = el('origen-dialog');
  let token = 0, informe, hallazgo, actual = null;
  const nodo = (tag, texto) => { const n = document.createElement(tag); n.textContent = texto; return n; };
  const texto = valor => valor == null ? 'Vacío registrado' : typeof valor === 'object' ? JSON.stringify(valor, null, 2) : String(valor);
  const vigente = t => t === token && dialog.open && state.detalleId === informe;
  function mostrar(data) {
    const box = el('origen-contenido'), e = data.evidencia;
    box.append(nodo('p', data.descripcion), nodo('p', data.aviso));
    const ubicacion = document.createElement('dl');
    for (const [label, value] of [
      ['Archivo', e.archivo_origen ?? e.archivo], ['Hoja', e.hoja],
      ['Cuadro o bloque', e.bloque_excel], ['Celda o rango', e.celda || (e.ubicaciones_excel || []).join('; ')],
      ['Página PDF', e.pagina_pdf], ['Tabla PDF', e.tabla_pdf],
    ]) {
      ubicacion.append(nodo('dt', label), nodo('dd', value == null || value === '' ? 'No registrada' : texto(value)));
    }
    box.append(ubicacion);
    for (const [key, label] of [
      ['indicador','Indicador'], ['periodo','Período'], ['regla','Control aplicado'],
      ['total_declarado','Total declarado'], ['total_reconstruido','Total reconstruido'],
      ['valor_observado','Valor observado'], ['valor_anterior','Valor anterior'],
      ['valor_posterior','Valor posterior'], ['diferencia_absoluta','Diferencia absoluta'],
      ['diferencia_porcentual','Diferencia porcentual'], ['accion_revision','Qué revisar'],
      ['ubicaciones_excel','Ubicaciones registradas'], ['celdas_participantes','Celdas comparadas'],
      ['componentes','Componentes de la comparación'], ['evidencia_comparativa','Evidencia comparativa'],
    ]) {
      if (!Object.prototype.hasOwnProperty.call(e, key)) continue;
      box.append(nodo('h3', label));
      const value = e[key];
      if (Array.isArray(value)) {
        const list = document.createElement('ul');
        value.forEach(item => list.append(nodo('li', texto(item)))); box.append(list);
      } else box.append(nodo('p', texto(value)));
    }
    const details = document.createElement('details'); details.append(nodo('summary','Ver toda la evidencia registrada'));
    const pre = nodo('pre', JSON.stringify(e, null, 2)); pre.style.whiteSpace = 'pre-wrap'; details.append(pre); box.append(details);
  }
  async function cargar() {
    const t = ++token; actual = null;
    el('origen-contenido').replaceChildren(); el('origen-estado').textContent = 'Cargando evidencia…';
    el('origen-descargar').disabled = true; el('origen-reintentar').hidden = true;
    try {
      const data = await apiFetch(`/informes/${informe}/hallazgos/${hallazgo}/evidencia`);
      if (!vigente(t)) return;
      actual = data; mostrar(data); el('origen-estado').textContent = `Informe ${informe} · Observación ${hallazgo}`;
      el('origen-descargar').disabled = false;
    } catch (e) {
      if (!vigente(t)) return;
      el('origen-estado').textContent = 'No se pudo consultar la evidencia. ' + e.message;
      el('origen-reintentar').hidden = false;
    }
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-origen-hallazgo]');
    if (!button || !state.detalleId) return;
    informe = state.detalleId; hallazgo = Number(button.dataset.origenHallazgo);
    if (!Number.isSafeInteger(hallazgo) || hallazgo < 1) return;
    dialog.showModal(); cargar();
  });
  el('origen-cerrar').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { token++; actual = null; });
  el('origen-reintentar').onclick = cargar;
  el('origen-descargar').onclick = () => {
    if (!actual || !vigente(token)) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(actual, null, 2)], {type:'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `evidencia-${informe}-${hallazgo}.json`;
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
})();
