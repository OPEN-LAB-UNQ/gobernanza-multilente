// Demo pública: script externo porque la CSP del sitio (script-src 'self') bloquea scripts inline.
const $ = (id) => document.getElementById(id);
let casos = [];
function mostrar(caso) {
  if (!caso) return;
  $('titulo').textContent = caso.titulo;
  $('tema').textContent = caso.tema;
  for (const [lado, datos] of [['sin', caso.sin_senal], ['con', caso.con_senal]]) {
    const base = `/api/ejemplos/publicos/${caso.orden}/${lado}`;
    $(`${lado}-nombre`).textContent = datos.nombre;
    $(`${lado}-descripcion`).textContent = datos.descripcion;
    $(`${lado}-pdf`).href = `${base}.pdf`;
    $(`${lado}-xlsx`).href = `${base}.xlsx`;
  }
  $('zip').href = `/api/ejemplos/publicos/${caso.orden}/zip`;
  $('reportes').hidden = false;
  $('acciones').hidden = false;
}
fetch('/api/ejemplos/publicos', { cache: 'no-store' }).then((r) => {
  if (!r.ok) throw new Error('No se pudo cargar el catálogo público.');
  return r.json();
}).then((data) => {
  casos = data.casos || [];
  if (!casos.length) throw new Error('Todavía no hay casos públicos disponibles.');
  const select = $('caso');
  select.replaceChildren(...casos.map((caso) => {
    const opt = document.createElement('option');
    opt.value = caso.orden;
    opt.textContent = `${caso.titulo} · ${caso.tema}`;
    return opt;
  }));
  select.disabled = false;
  select.addEventListener('change', () => mostrar(casos.find((caso) => String(caso.orden) === select.value)));
  mostrar(casos[0]);
}).catch((error) => { $('tema').textContent = error.message; $('tema').classList.add('error'); });
