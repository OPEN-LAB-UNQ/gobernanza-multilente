/* Sugerencias identificadas desde las cuentas existentes. Sin llamadas a IA. */
(() => {
  const dialog = document.createElement('dialog');
  dialog.className = 'sugerencias-dialog';
  dialog.setAttribute('aria-labelledby', 'sug-titulo');
  dialog.innerHTML = `<form id="sug-form">
    <h2 id="sug-titulo">Sugerencias para mejorar esta pantalla</h2>
    <p id="sug-pantalla"></p>
    <p id="sug-identidad" class="hint"></p>
    <label for="sug-texto">¿Qué cambiarías para que sea más clara o fácil de usar?</label>
    <textarea id="sug-texto" rows="7" maxlength="5000" required placeholder="Contanos qué te costó entender o qué te gustaría mejorar. Podés incluir varias sugerencias."></textarea>
    <p class="hint">Hasta 5000 caracteres. Evitá incluir contraseñas o datos sensibles.</p>
    <p id="sug-estado" role="status" aria-live="polite"></p>
    <div class="actions-row"><button type="submit" class="btn btn-primary" id="sug-enviar">Enviar sugerencias</button><button type="button" class="btn btn-secondary" id="sug-cerrar">Cerrar</button></div>
  </form>`;
  document.body.append(dialog);
  const $ = id => document.getElementById(id);
  const drafts = new Map();
  let pantalla = '', sending = false, completed = false;
  function draft() {
    if (!drafts.has(pantalla)) drafts.set(pantalla, {text: '', token: crypto.randomUUID()});
    return drafts.get(pantalla);
  }
  function close() { if (!sending) dialog.close(); }
  $('sug-cerrar').onclick = close;
  dialog.addEventListener('cancel', event => { if (sending) event.preventDefault(); });
  $('sug-texto').addEventListener('input', () => { if (!completed) draft().text = $('sug-texto').value; });
  function abrir(view) {
    if (!state.currentUser) { alert('Tu sesión todavía no está disponible. Volvé a ingresar e intentá nuevamente.'); return; }
    pantalla = view.id.replace('view-', '');
    const title = view.querySelector('.view-title, h2')?.textContent.trim() || pantalla;
    completed = false;
    $('sug-form').reset();
    $('sug-texto').disabled = false;
    $('sug-enviar').hidden = false;
    $('sug-enviar').disabled = false;
    $('sug-pantalla').textContent = 'Pantalla: ' + title;
    $('sug-identidad').textContent = `Se enviará con el nombre de tu cuenta: ${state.currentUser.nombre}. El equipo docente podrá leerla. No es anónima.`;
    $('sug-texto').value = draft().text;
    $('sug-estado').textContent = '';
    dialog.showModal();
    $('sug-texto').focus();
  }
  $('sug-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (sending || completed) return;
    const text = $('sug-texto').value.trim();
    if (!text) { $('sug-estado').textContent = 'Escribí una sugerencia antes de enviar.'; return; }
    const current = draft(); current.text = text;
    sending = true;
    $('sug-enviar').disabled = true; $('sug-cerrar').disabled = true; $('sug-texto').disabled = true;
    $('sug-estado').textContent = 'Guardando tu sugerencia…';
    try {
      await apiFetch('/sugerencias', {method: 'POST', body: JSON.stringify({pantalla, texto: text, solicitud_id: current.token})});
      completed = true; drafts.delete(pantalla);
      $('sug-estado').textContent = 'Tu sugerencia quedó guardada. El equipo docente podrá leerla con tu nombre. Podés corregirla desde “Mis sugerencias enviadas”. ¡Gracias!';
      $('sug-enviar').hidden = true;
      $('sug-cerrar').focus();
    } catch (error) {
      $('sug-estado').textContent = 'No pudimos confirmar el envío. Tu texto sigue acá; podés reintentar. ' + error.message;
      $('sug-texto').disabled = false;
    } finally {
      sending = false; $('sug-enviar').disabled = false; $('sug-cerrar').disabled = false;
    }
  });

  const inbox = document.createElement('dialog');
  inbox.className = 'sugerencias-dialog sugerencias-inbox';
  inbox.setAttribute('aria-labelledby', 'sug-lista-titulo');
  inbox.innerHTML = `<h2 id="sug-lista-titulo">Sugerencias recibidas</h2>
    <div class="sugerencias-filtros"><label>Pantalla<select id="sug-filtro-pantalla"><option value="">Todas las pantallas</option></select></label>
    <label>Persona<select id="sug-filtro-persona"><option value="">Todas las personas</option></select></label></div>
    <div class="actions-row"><button type="button" class="btn btn-primary" id="sug-descargar">Descargar sugerencias (CSV)</button><button type="button" class="btn btn-secondary" id="sug-lista-cerrar">Cerrar</button></div>
    <p class="hint">La descarga incluye todas las sugerencias que coinciden con los filtros.</p>
    <p id="sug-lista-estado" role="status" aria-live="polite"></p><div id="sug-items"></div>
    <div class="actions-row"><button class="btn btn-secondary" id="sug-anterior">Anterior</button><button class="btn btn-secondary" id="sug-siguiente">Siguiente</button></div>`;
  document.body.append(inbox);
  let offset = 0, requestVersion = 0;
  const query = () => {
    const params = new URLSearchParams();
    if ($('sug-filtro-pantalla').value) params.set('pantalla', $('sug-filtro-pantalla').value);
    if ($('sug-filtro-persona').value) params.set('usuario_id', $('sug-filtro-persona').value);
    return params;
  };
  function options(select, entries) {
    const selected = select.value;
    while (select.options.length > 1) select.remove(1);
    entries.forEach(([value, text]) => select.add(new Option(text, value)));
    select.value = selected;
  }
  async function cargar() {
    const version = ++requestVersion, params = query();
    params.set('offset', offset); params.set('limit', 50);
    $('sug-lista-estado').textContent = 'Cargando sugerencias…';
    $('sug-items').replaceChildren();
    $('sug-anterior').disabled = true; $('sug-siguiente').disabled = true;
    try {
      const data = await apiFetch('/sugerencias?' + params);
      if (version !== requestVersion) return;
      options($('sug-filtro-pantalla'), Object.entries(data.pantallas));
      options($('sug-filtro-persona'), data.personas.map(p => [p.id, p.nombre]));
      $('sug-lista-estado').textContent = data.total ? `${data.total} sugerencias · Mostrando ${offset + 1} a ${offset + data.items.length}` : 'Todavía no hay sugerencias para estos filtros.';
      data.items.forEach(item => {
        const article = document.createElement('article'); article.className = 'sugerencia-item';
        const heading = document.createElement('h3'); heading.textContent = `${item.pantalla_nombre} · ${item.nombre}`;
        const date = document.createElement('p'); date.className = 'hint'; date.textContent = new Date(item.creado_en).toLocaleString('es-AR');
        const text = document.createElement('p'); text.className = 'sugerencia-texto'; text.textContent = item.texto;
        article.append(heading, date, text); $('sug-items').append(article);
      });
      $('sug-anterior').disabled = offset === 0; $('sug-siguiente').disabled = offset + data.items.length >= data.total;
    } catch (error) {
      if (version === requestVersion) $('sug-lista-estado').textContent = 'No pudimos cargar las sugerencias. ' + error.message;
    }
  }
  $('sug-lista-cerrar').onclick = () => inbox.close();
  for (const id of ['sug-filtro-pantalla', 'sug-filtro-persona']) $(id).onchange = () => { offset = 0; cargar(); };
  $('sug-anterior').onclick = () => { offset = Math.max(0, offset - 50); cargar(); };
  $('sug-siguiente').onclick = () => { offset += 50; cargar(); };
  $('sug-descargar').onclick = async () => {
    $('sug-descargar').disabled = true;
    try {
      const res = await fetch('/api/sugerencias/exportar?' + query());
      if (!res.ok || !(res.headers.get('content-type') || '').includes('text/csv')) throw new Error('Revisá tu sesión y volvé a intentar.');
      const url = URL.createObjectURL(await res.blob()), link = document.createElement('a');
      link.href = url; link.download = 'sugerencias-gobernanza.csv'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { $('sug-lista-estado').textContent = 'No pudimos descargar. ' + error.message; }
    finally { $('sug-descargar').disabled = false; }
  };
  const propias = document.createElement('dialog');
  propias.className = 'sugerencias-dialog';
  propias.setAttribute('aria-labelledby', 'sug-propias-titulo');
  propias.innerHTML = `<h2 id="sug-propias-titulo">Mis sugerencias enviadas</h2>
    <p>Maxi puede consultar tus sugerencias con el nombre de tu cuenta. Podés corregirlas aquí; se conserva un registro de los cambios.</p>
    <button type="button" class="btn btn-secondary" id="sug-propias-cerrar">Cerrar</button>
    <p id="sug-propias-estado" role="status"></p><div id="sug-propias-items"></div>
    <button type="button" class="btn btn-secondary" id="sug-propias-anterior">Anterior</button>
    <button type="button" class="btn btn-secondary" id="sug-propias-siguiente">Siguiente</button>`;
  document.body.append(propias);
  let propiasOffset = 0, propiasVersion = 0, editando = false;
  const cambiosPropios = new Set();
  const puedeSalir = () => !editando && (!cambiosPropios.size || window.confirm('Tenés correcciones sin guardar. ¿Querés descartarlas?'));
  $('sug-propias-cerrar').onclick = () => { if (puedeSalir()) propias.close(); };
  propias.addEventListener('cancel', e => { if (!puedeSalir()) e.preventDefault(); });
  async function cargarPropias() {
    const version = ++propiasVersion; cambiosPropios.clear();
    $('sug-propias-estado').textContent = 'Cargando tus sugerencias…';
    $('sug-propias-items').replaceChildren();
    $('sug-propias-anterior').disabled = true; $('sug-propias-siguiente').disabled = true;
    try {
      const data = await apiFetch('/sugerencias/mias?offset=' + propiasOffset);
      if (version !== propiasVersion) return;
      $('sug-propias-estado').textContent = data.total ? `${data.total} sugerencias enviadas · Mostrando ${propiasOffset + 1} a ${propiasOffset + data.items.length}` : 'Todavía no enviaste sugerencias.';
      data.items.forEach(item => {
        const article = document.createElement('article'); article.className = 'sugerencia-item';
        const heading = document.createElement('h3'); heading.textContent = item.pantalla_nombre;
        const date = document.createElement('p'); date.textContent = 'Enviada: ' + new Date(item.creado_en).toLocaleString('es-AR');
        const input = document.createElement('textarea'); input.value = item.texto; input.maxLength = 5000; input.rows = 5; input.style.width = '100%'; input.setAttribute('aria-label', 'Corregir sugerencia sobre ' + item.pantalla_nombre);
        input.oninput = () => { if (input.value !== item.texto) cambiosPropios.add(item.id); else cambiosPropios.delete(item.id); };
        const status = document.createElement('p'); status.setAttribute('role', 'status');
        const save = document.createElement('button'); save.type = 'button'; save.className = 'btn btn-primary'; save.textContent = 'Guardar corrección';
        save.onclick = async () => {
          if (editando) return;
          const texto = input.value.trim();
          if (!texto) { status.textContent = 'Escribí una sugerencia antes de guardar.'; return; }
          editando = true; input.disabled = true; save.disabled = true; status.textContent = 'Guardando corrección…';
          $('sug-propias-anterior').disabled = true; $('sug-propias-siguiente').disabled = true;
          try {
            const updated = await apiFetch('/sugerencias/' + item.id, {method:'PATCH', body:JSON.stringify({texto, texto_anterior:item.texto})});
            item.texto = updated.texto; input.value = updated.texto; cambiosPropios.delete(item.id);
            status.textContent = 'Corrección guardada. Maxi verá esta versión.';
          } catch (e) { status.textContent = 'No se guardó la corrección. Tu texto sigue acá. ' + e.message; }
          finally { editando = false; input.disabled = false; save.disabled = false;
            $('sug-propias-anterior').disabled = propiasOffset === 0; $('sug-propias-siguiente').disabled = propiasOffset + data.items.length >= data.total; }
        };
        article.append(heading,date,input,save,status); $('sug-propias-items').append(article);
      });
      $('sug-propias-anterior').disabled = propiasOffset === 0; $('sug-propias-siguiente').disabled = propiasOffset + data.items.length >= data.total;
    } catch (e) { if (version === propiasVersion) $('sug-propias-estado').textContent = 'No pudimos cargar tus sugerencias. ' + e.message; }
  }
  $('sug-propias-anterior').onclick = () => { if (puedeSalir()) { propiasOffset = Math.max(0, propiasOffset - 50); cargarPropias(); } };
  $('sug-propias-siguiente').onclick = () => { if (puedeSalir()) { propiasOffset += 50; cargarPropias(); } };
  const adminButtons = [];
  document.querySelectorAll('main .view').forEach(view => {
    const bar = document.createElement('div'); bar.className = 'sugerencias-bar';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'btn sugerencias-abrir';
    button.textContent = 'Sugerencias para mejorar esta pantalla'; button.onclick = () => abrir(view);
    const admin = document.createElement('button'); admin.type = 'button'; admin.className = 'btn btn-secondary';
    admin.textContent = 'Ver sugerencias recibidas'; admin.hidden = true;
    admin.onclick = () => { offset = 0; inbox.showModal(); cargar(); };
    const mine = document.createElement('button'); mine.type = 'button'; mine.className = 'btn btn-secondary'; mine.textContent = 'Mis sugerencias enviadas';
    mine.onclick = () => { propiasOffset = 0; propias.showModal(); cargarPropias(); };
    adminButtons.push(admin); bar.append(button, mine, admin); view.prepend(bar);
  });
  function syncUser() { adminButtons.forEach(button => { button.hidden = state.currentUser?.rol !== 'admin'; }); }
  document.addEventListener('gobernanza:usuario', syncUser); syncUser();
})();
