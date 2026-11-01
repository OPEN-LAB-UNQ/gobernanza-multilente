/* Consulta de la representación saneada; nunca presenta estos registros como el original. */
(() => {
  const el = id => document.getElementById(id);
  const dialog = el('datos-dialog');
  let informe = null, offset = 0, query = '', generation = 0;
  const vigente = token => token === generation && dialog.open && state.detalleId === informe;
  const node = (tag, value) => { const n = document.createElement(tag); n.textContent = value; return n; };
  async function cargar() {
    const token = ++generation;
    el('datos-estado').textContent = 'Cargando datos…';
    el('datos-tabla').replaceChildren();
    for (const id of ['datos-anterior','datos-siguiente','datos-exportar']) el(id).disabled = true;
    try {
      const data = await apiFetch(`/informes/${informe}/datos-analizados?offset=${offset}&q=${encodeURIComponent(query)}`);
      if (!vigente(token)) return;
      el('datos-estado').textContent = `${data.aviso} ${data.total} registros guardados; ${data.coincidencias} coinciden con la búsqueda. Mostrando ${data.items.length ? offset + 1 : 0}–${offset + data.items.length}.`;
      el('datos-fuentes').textContent = 'Fuentes: ' + (data.fuentes.join(' · ') || 'nombre original no registrado');
      const table = document.createElement('table'), head = document.createElement('tr');
      for (const c of ['Registro procesado', ...data.columnas]) head.append(node('th', c));
      const thead = document.createElement('thead'); thead.append(head); table.append(thead);
      const body = document.createElement('tbody');
      for (const item of data.items) {
        const row = document.createElement('tr'); row.append(node('td', item.registro));
        for (const c of data.columnas) {
          const value = item.valores[c];
          row.append(node('td', value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)));
        }
        body.append(row);
      }
      table.append(body); el('datos-tabla').append(table);
      el('datos-anterior').disabled = offset === 0;
      el('datos-siguiente').disabled = offset + 50 >= data.coincidencias;
      el('datos-exportar').disabled = false;
    } catch (e) {
      if (vigente(token)) el('datos-estado').textContent = 'No se pudieron consultar los datos. Podés volver a buscar para reintentar. ' + e.message;
    }
  }
  el('consultar-datos').addEventListener('click', () => {
    informe = state.detalleId; if (!informe) return;
    offset = 0; query = ''; el('datos-query').value = ''; el('datos-fuentes').textContent = '';
    dialog.showModal(); cargar();
  });
  el('datos-buscar').addEventListener('submit', e => { e.preventDefault(); offset = 0; query = el('datos-query').value; cargar(); });
  el('datos-anterior').onclick = () => { offset = Math.max(0, offset - 50); cargar(); };
  el('datos-siguiente').onclick = () => { offset += 50; cargar(); };
  el('datos-cerrar').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { generation++; });
  el('datos-exportar').onclick = async () => {
    const token = generation; el('datos-exportar').disabled = true;
    try {
      const data = await apiFetch(`/informes/${informe}/datos-analizados?descargar=true`);
      if (!vigente(token)) return;
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
      const a = document.createElement('a'); a.href = url; a.download = `datos-analizados-${informe}.json`;
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      if (vigente(token)) el('datos-estado').textContent = 'No se pudo descargar. ' + e.message;
    } finally { if (vigente(token)) el('datos-exportar').disabled = false; }
  };
})();
