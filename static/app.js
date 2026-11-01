const API = "/api";
const MAX_ARCHIVOS = 4;
const samplePairRuns = new Map();
let samplePairBusy = false;
const state = { areas: [], informes: [], detalleId: null, detalle: null, archivos: [], sampleDocs: [], aprendizaje: null, reporteSeleccion: new Set(), currentUser: null, detallePollTimer: null, proyectoIA: null, proyectosIASupervision: [], proyectoCasos: [], proyectoCasosFiltro: "", proyectoIASeleccionado: null, proyectoIADirty: false, proyectoIALastSavedAt: null, primeraVueltaCerrada: false, segundaVuelta: null, segundaVueltaSeleccionado: null, segundaVueltaEnviando: false };


const NAV_ITEMS = [
  { view: "inicio", label: "Inicio", module: "entrada", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9.5 10 3l7 6.5"/><path d="M5 8.5V17h10V8.5"/><path d="M8 17v-5h4v5"/></svg>' },
  { view: "analizar", label: "Analizar", module: "gobernanza", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13V3"/><path d="M6.5 6.5 10 3l3.5 3.5"/><path d="M3.5 13v2.5A1.5 1.5 0 0 0 5 17h10a1.5 1.5 0 0 0 1.5-1.5V13"/></svg>' },
  { view: "informes", label: "Informes", module: "gobernanza", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7.25"/><path d="M10 6v4.2l3 1.8"/></svg>' },
  { view: "validacion", label: "Validación", module: "gobernanza", seccion: "acerca", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10.5 8.2 14.5 16 5.5"/><path d="M5 4h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/></svg>' },
  { view: "aprendizaje", label: "Calibración del sistema", module: "gobernanza", seccion: "acerca", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16 6.5A6.5 6.5 0 0 0 5 5.2M4 4v3h3"/><path d="M4 13.5A6.5 6.5 0 0 0 15 14.8M16 16v-3h-3"/></svg>' },
  { view: "marco", label: "Marco", module: "gobernanza", seccion: "acerca", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3.5h7l3 3V16.5H5z"/><path d="M12 3.5V6.5H15"/><path d="M7.2 9.5h5.6M7.2 12h5.6M7.2 14.5h3.5"/></svg>' },
  { view: "actividad", label: "Actividad", module: "gobernanza", adminOnly: true, icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 16V9"/><path d="M10 16V4"/><path d="M16 16v-6"/><path d="M3 16.5h14"/></svg>' },
  { view: "proyecto-ia", label: "Mi proyecto", module: "proyecto", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 16.5h12"/><path d="M5.5 13.5 14.2 4.8a1.6 1.6 0 0 1 2.2 2.2l-8.7 8.7-3.2.8.8-3z"/><path d="M12.8 6.2l2 2"/></svg>' },
  { view: "segunda-vuelta", label: "Actividad de votación", module: "conexiones", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h12v12H4z"/><path d="m7 10 2 2 4-5"/></svg>' },
  { view: "casos", label: "Casos de mis compañeros", module: "conexiones", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5h12"/><path d="M4 10h12"/><path d="M4 14.5h12"/><circle cx="4" cy="5.5" r="1"/><circle cx="4" cy="10" r="1"/><circle cx="4" cy="14.5" r="1"/></svg>' },
  { view: "conexiones", label: "Mapa de conexiones", module: "conexiones", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 6.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/><path d="M15 11.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/><path d="M6.7 5.6 13.3 8.4"/><path d="M5 17.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/><path d="M6.8 14.6 13.2 10.4"/></svg>' },
  { view: "sintesis", label: "Tres síntesis", module: "conexiones", icon: '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 6.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/><path d="M15 11.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/><path d="M6.7 5.6 13.3 8.4"/><path d="M5 17.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/><path d="M6.8 14.6 13.2 10.4"/></svg>' },
];

const NAV_GROUPS = [
  { key: "entrada", label: "Entrada" },
  { key: "gobernanza", label: "Gobernanza Multilente" },
  { key: "proyecto", label: "Gobernanza Incubadora" },
  { key: "conexiones", label: "Gobernanza Conexiones" },
];

function renderNav() {
  const contenedor = document.getElementById("main-nav");
  const template = document.getElementById("nav-item-template");
  if (!contenedor || !template) return;
  contenedor.textContent = "";
  NAV_GROUPS.forEach((group) => {
    // En modo básico, lo de «Acerca del sistema» (validación, calibración, marco) no se lista.
    const basico = document.body?.classList?.contains("modo-basico");
    const items = NAV_ITEMS.filter((item) => item.module === group.key && (!item.adminOnly || state.currentUser?.rol === "admin")
      && !(basico && item.seccion === "acerca"));
    if (!items.length) return;
    const groupEl = document.createElement("div");
    groupEl.className = `nav-group nav-group-${group.key}`;
    const label = document.createElement("span");
    label.className = "nav-group-label";
    label.textContent = group.label;
    groupEl.appendChild(label);
    // Lo que es para docentes y diseñadores (calibración, validación, marco) va al final del
    // grupo, separado bajo «Acerca del sistema»: el alumno ve primero lo que usa.
    const principales = items.filter((item) => !item.seccion);
    const acerca = items.filter((item) => item.seccion === "acerca");
    [...principales, ...acerca].forEach((item, i) => {
      if (acerca.length && i === principales.length) {
        const sep = document.createElement("span");
        sep.className = "nav-subgrupo-label";
        sep.setAttribute("role", "separator");
        sep.textContent = "Acerca del sistema";
        groupEl.appendChild(sep);
      }
      const button = template.content.firstElementChild.cloneNode(true);
      button.dataset.view = item.view;
      button.dataset.module = item.module;
      button.querySelector(".icon").innerHTML = item.icon;
      button.querySelector(".nav-label").textContent = item.view === "segunda-vuelta" ? (state.rotuloVotacion || item.label) : item.label;
      button.addEventListener("click", () => mostrarVista(item.view));
      button.classList.toggle("active", document.getElementById(`view-${item.view}`)?.classList.contains("active") || false);
      groupEl.appendChild(button);
    });
    contenedor.appendChild(groupEl);
  });
  centrarPestanaActiva(false);
}

// En celular la barra de pestañas se desplaza de costado: la activa se centra para que
// no quede fuera de vista. Solo mueve la barra, nunca la página.
function centrarPestanaActiva(suave = true) {
  const barra = document.getElementById("main-nav");
  const activa = barra?.querySelector(".nav-btn.active");
  if (!barra || !activa || barra.scrollWidth <= barra.clientWidth) return;
  const b = barra.getBoundingClientRect();
  const a = activa.getBoundingClientRect();
  barra.scrollBy({ left: a.left + a.width / 2 - (b.left + b.width / 2), behavior: suave ? "smooth" : "auto" });
}

renderNav();
cargarDocumentosPrueba();

// ---------- utilidades ----------

// OJO: esto es una referencia de tarifa por modelo, NO un presupuesto de
// "este analisis". Los checkboxes se muestran antes de que el sistema sepa
// cuantas señales va a encontrar el archivo (eso recien se calcula cuando
// corre la cola, services/analisis.py::ejecutar_analisis) -- ni la cantidad
// de filas ayuda a estimarlo, porque el costo depende de cuantos hallazgos
// entran al prompt de interpretacion, no de cuantas filas tiene el archivo.
// El numero de abajo es el costo de 1 llamada de interpretacion con una
// carga tipica (2-3 hallazgos, medido en la propia app): sirve para comparar
// que modelo sale mas caro entre si (esa proporcion no cambia con el
// archivo, porque el costo escala linealmente con el prompt en los 4
// proveedores), no para saber cuanto va a costar el analisis puntual.
// Tarifas publicas por 1M tokens de cada proveedor, medidas a ENERO 2026 --
// revisar si cambiaron las tarifas del proveedor o el modelo en .env (ver
// seccion "Por que la triangulacion es barata" en README.md). Llama corre
// contra un endpoint propio (OLLAMA_BASE_URL): el costo depende de ese
// hosting, no hay tarifa publica para estimar. Renderix corre por endpoint
// OpenAI-compatible propio: se muestra como costo variable/local.
const COSTO_ESTIMADO_MODELO = {
  claude: 0.007,
  gpt: 0.001,
  gemini: 0.001,
  renderix: null,
  deepseek: 0.0004,
  llama: null,
};

function fmtCostoModelo(valor) {
  if (valor === null || valor === undefined) return "variable, según tu proveedor";
  if (valor < 0.001) return "< $0.001 ref.";
  return `~$${valor.toFixed(3)} ref.`;
}

function initCostosEstimados() {
  document.querySelectorAll(".modelo-costo").forEach((el) => {
    const modelo = el.dataset.modelo;
    el.textContent = `(${fmtCostoModelo(COSTO_ESTIMADO_MODELO[modelo])})`;
  });
  [
    { selector: ".modelo-check-rapido", totalId: "costo-total-rapido" },
    { selector: ".modelo-check", totalId: "costo-total-detalle" },
  ].forEach(({ selector, totalId }) => {
    const totalEl = document.getElementById(totalId);
    if (!totalEl) return;
    const actualizar = () => {
      const marcados = Array.from(document.querySelectorAll(`${selector}:checked`)).map((el) => el.value);
      if (!marcados.length) {
        totalEl.textContent = "";
        return;
      }
      let suma = 0;
      const variables = [];
      marcados.forEach((m) => {
        const c = COSTO_ESTIMADO_MODELO[m];
        if (c === null || c === undefined) variables.push(NOMBRE_MODELO_PROGRESO[m] || m);
        else suma += c;
      });
      const partes = [`Costo de referencia con los modelos elegidos: ~$${suma.toFixed(3)} por una carga típica de señales`];
      if (variables.length) partes.push(`+ ${variables.join(" + ")} (variable/local)`);
      partes.push("— el costo real depende de cuántas señales encuentre este archivo, y eso recién se sabe al terminar el análisis.");
      totalEl.textContent = partes.join(" ");
    };
    document.querySelectorAll(selector).forEach((el) => el.addEventListener("change", actualizar));
    actualizar();
  });
}
initCostosEstimados();

async function cargarEstadoModelos() {
  const proveedores = { gpt: "openai", claude: "anthropic", gemini: "gemini", deepseek: "deepseek", renderix: "renderix", llama: "llama" };
  try {
    const estado = await apiFetch("/modelos/status");
    document.querySelectorAll(".modelo-check, .modelo-check-rapido").forEach((input) => {
      const info = estado[proveedores[input.value]];
      if (!info) return;
      input.disabled = !info.habilitada;
      if (input.disabled) input.checked = false;
      const etiqueta = input.closest("label");
      let aviso = etiqueta.querySelector(".modelo-estado");
      if (!aviso) {
        aviso = document.createElement("small");
        aviso.className = "modelo-estado";
        etiqueta.appendChild(aviso);
      }
      aviso.textContent = input.disabled ? ` — ${info.motivo || "No disponible"}` : "";
      input.dispatchEvent(new Event("change"));
    });
  } catch (_) {
    toast("No se pudo consultar el estado de los proveedores de IA.", true);
  }
}



async function apiFetch(path, options = {}) {
  const resp = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let detalle = resp.statusText;
    try { detalle = (await resp.json()).detail || detalle; } catch (_) {}
    // Validación de FastAPI/pydantic: lista de {loc, msg}; sin esto el aviso quedaba vacío.
    if (Array.isArray(detalle)) detalle = detalle.map((d) => d?.msg).filter(Boolean).join(" · ") || "Los datos enviados no son válidos.";
    if (typeof detalle === "object") detalle = [detalle.mensaje, ...(detalle.motivos || [])].filter(Boolean).join(" · ");
    const error = new Error(detalle);
    error.status = resp.status;
    throw error;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

async function apiFetchForm(path, formData) {
  const resp = await fetch(API + path, { method: "POST", body: formData });
  if (!resp.ok) {
    let detalle = resp.statusText;
    try { detalle = (await resp.json()).detail || detalle; } catch (_) {}
    // Un detalle estructurado (p. ej. {codigo: "requiere_revision_lectura", mensaje, ...}) se
    // muestra por su mensaje y queda disponible para quien necesite el código.
    const error = new Error(typeof detalle === "object" && detalle ? (detalle.mensaje || JSON.stringify(detalle)) : detalle);
    if (typeof detalle === "object") error.detalle = detalle;
    throw error;
  }
  return resp.json();
}

async function apiFetchDownload(path, payload) {
  const resp = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    let detalle = resp.statusText;
    try { detalle = (await resp.json()).detail || detalle; } catch (_) {}
    throw new Error(detalle);
  }
  const disposition = resp.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return { blob: await resp.blob(), filename: match ? match[1] : "reporte-hallazgos.pdf" };
}

function toast(msg, isError = false) {
  if (isError && window.mostrarErrorPersistente) { window.mostrarErrorPersistente(msg); return; }
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function fmtFecha(iso) {
  if (!iso) return "-";
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  return d.toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
  const mapa = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, (c) => mapa[c]);
}

// Escapa recursivamente todo string dentro de un objeto/array, dejando
// numeros, booleanos y null intactos (no los toca String(), no rompe
// comparaciones ni conteos que dependan de que sigan siendo numero).
//
// Hace falta porque la descripcion, la pregunta institucional y la
// evidencia de un hallazgo casi siempre citan texto tomado literal del
// archivo que subio el usuario -- nombres de columna, encabezados, valores
// de celda -- y varios de los ~30 puntos donde ese texto se inyecta en el
// DOM lo hacian via innerHTML sin escapar. Un alumno que nombrara una
// columna con HTML/JS iba a poder ejecutar script en la pantalla de
// cualquiera que abriera ese informe (XSS almacenado). Escapar una sola vez
// aca, apenas llega la respuesta, es mas confiable que perseguir cada sitio
// de render por separado -- ya se nos escapo uno (el "periodo" de la tabla
// de historial) haciendolo caso por caso.
function escapeDeep(valor) {
  if (typeof valor === "string") return escapeHtml(valor);
  if (Array.isArray(valor)) return valor.map(escapeDeep);
  if (valor && typeof valor === "object") {
    const out = {};
    for (const k of Object.keys(valor)) out[k] = escapeDeep(valor[k]);
    return out;
  }
  return valor;
}

function areaNombre(id) {
  const a = state.areas.find((x) => x.id === id);
  return a ? `${a.nombre} (${a.codigo})` : `#${id}`;
}

function badgeSeveridad(sev) {
  const cls = { alta: "badge-alta", media: "badge-media", baja: "badge-baja" }[sev] || "badge-neutral";
  return `<span class="badge ${cls}">${sev}</span>`;
}

// ---------- navegación ----------

function normalizarVista(nombre) {
  if (nombre === "roles" || nombre === "habilidades") return "marco";
  if (nombre === "rizoma") return "conexiones";
  return nombre;
}

function rutaVista(nombre) {
  return {
    inicio: "#/inicio",
    analizar: "#/analizar",
    informes: "#/informes",
    "proyecto-ia": "#/proyecto-ia",
    roles: "#/marco",
    habilidades: "#/marco",
    guia: "#/guia",
    marco: "#/marco",
    validacion: "#/validacion",
    aprendizaje: "#/aprendizaje",
    actividad: "#/actividad",
    detalle: state.detalleId ? `#/informe/${state.detalleId}` : "#/informes",
    casos: "#/casos",
    "segunda-vuelta": "#/segunda-vuelta",
    rizoma: "#/conexiones",
    conexiones: "#/conexiones",
    sintesis: "#/sintesis",
  }[nombre] || "#/inicio";
}

function actualizarUrlVista(nombre) {
  const ruta = rutaVista(nombre);
  if (window.location.hash !== ruta) {
    history.pushState(null, "", ruta);
  }
}

function moduloVista(nombre) {
  const item = NAV_ITEMS.find((nav) => nav.view === nombre);
  return item?.module || "entrada";
}

// Un solo lugar decide el plural en la pantalla, como services/plural.py en el servidor.
// La forma abreviada con la s entre paréntesis hace dudar de todo lo demás.
function contar(cantidad, singular, plural) {
  const n = Number(cantidad || 0);
  const muchos = plural !== undefined ? plural : /[lrndz]$/.test(singular) ? `${singular}es` : `${singular}s`;
  return `${n} ${n === 1 ? singular : muchos}`;
}

// Algunos textos ya llegan escapados (escapeDeep y, a veces, también desde el servidor).
// Para no mostrar «&amp;#39;» se decodifican a texto plano las entidades que produce
// escapeHtml y recién después se escapan una sola vez: la salida nunca lleva HTML crudo.
const ENTIDADES_BASICAS = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", "#x27": "'", apos: "'" };
function desescaparHtml(value) {
  let texto = String(value ?? "");
  for (let i = 0; i < 3; i++) {
    const previo = texto;
    texto = texto.replace(/&(amp|lt|gt|quot|#39|#x27|apos);/g, (_, e) => ENTIDADES_BASICAS[e]);
    if (texto === previo) break;
  }
  return texto;
}

function escapeHtmlUnaVez(value) {
  return escapeHtml(desescaparHtml(value));
}

// Sintesis visual por recorrido: el mapa y lo que aporta cada instancia se dibujan siempre;
// el "donde estoy" se marca solo con lo que el servidor puede verificar, y nunca se supone.
const RECORRIDOS = {
  multilente: {
    titulo: "Recorrido 1",
    sintesis: "Traés un archivo y volvés con señales para verificar, no con conclusiones.",
    pasos: [
      { clave: "cargar", rotulo: "Elegís el archivo o un caso de prueba", aporte: "Podés practicar sin datos sensibles." },
      { clave: "analizar", rotulo: "Analizás", aporte: "Seis lentes y una capa conciliadora revisan lo mismo con criterios distintos." },
      { clave: "leer", rotulo: "Leés el informe y su cobertura", aporte: "Sabés qué se revisó y, sobre todo, qué quedó afuera." },
      { clave: "verificar", rotulo: "Verificás en el archivo", aporte: "Lo que el sistema marca es una observación; la afirmación la hacés vos.", fuera: true },
    ],
  },
  incubadora: {
    titulo: "Recorrido 2",
    sintesis: "Sale una propuesta que se puede defender: primero el problema, después la herramienta.",
    pasos: [
      { clave: "problema", rotulo: "Nombrás el problema", aporte: "Queda escrito qué pasa hoy y a quién afecta." },
      { clave: "conversar", rotulo: "Conversás para precisarlo", aporte: "Lo que aportás queda registrado y sigue siendo tuyo." },
      { clave: "propuesta", rotulo: "Probás si la propuesta se sostiene", aporte: "Ves cuáles de los diez criterios ya tienen evidencia y cuál falta." },
      { clave: "entregar", rotulo: "Entregás", aporte: "La entrega queda registrada con fecha; mejorarla después es opcional." },
      { clave: "devolucion", rotulo: "Recibís la devolución docente", aporte: "La revisión es humana: el sistema no aprueba proyectos." },
    ],
  },
  conexiones: {
    titulo: "Recorrido 3",
    sintesis: "Tu proyecto se mira al lado de los otros: por temas en común, no por personas.",
    pasos: [
      { clave: "proyecto", rotulo: "Tu proyecto con título, área y situación", aporte: "Con eso entra al mapa; la conversación privada no se publica." },
      { clave: "mapa", rotulo: "Aparece en el mapa", aporte: "Ves qué temas comparte con otros proyectos." },
      { clave: "comparar", rotulo: "Comparás con los proyectos vinculados", aporte: "Aparecen datos y riesgos que conviene discutir juntos.", fuera: true },
    ],
  },
  monitoreo: {
    titulo: "Recorrido 4",
    sintesis: "Acompaña una implementación real y convierte la operación en aprendizaje.",
    pasos: [
      { clave: "cartera", rotulo: "Tu proyecto queda en cartera", aporte: "Disponible, sin obligación de implementarlo." },
      { clave: "elegido", rotulo: "Un proyecto pasa a implementación", aporte: "Hoy es el de modificaciones presupuestarias.", fuera: true, nota: "Lo decide la conducción del curso: no requiere acción tuya." },
      { clave: "seguimiento", rotulo: "Se registran avances, riesgos y decisiones", aporte: "Lo aprendido queda como aprendizaje institucional, no como evaluación de personas.", fuera: true, nota: "Lo registra el equipo del proyecto ganador." },
    ],
  },
};

function estadosRuta(pasos, hechos) {
  const listos = new Set(hechos || []);
  const estados = pasos.map((p) => (listos.has(p.clave) ? "hecho" : "pendiente"));
  const siguiente = estados.indexOf("pendiente");
  if (siguiente >= 0 && listos.size) estados[siguiente] = "actual";
  if (siguiente === 0 && !listos.size) estados[0] = "actual";
  return estados;
}

function mapaRuta(estados, titulo) {
  // Nodos en HTML y no en SVG: un circulo estirado por el ancho de la tarjeta se ve como un error.
  const partes = [];
  estados.forEach((estado, i) => {
    if (i) {
      const hecho = estados[i - 1] === "hecho" && estado !== "pendiente";
      partes.push(`<span class="ruta-tramo${hecho ? " ruta-tramo-hecho" : ""}"></span>`);
    }
    partes.push(`<span class="ruta-nodo ruta-nodo-${estado}"></span>`);
  });
  return `<div class="ruta-mapa" role="img" aria-label="${escapeHtml(titulo)}">${partes.join("")}</div>`;
}

function renderRuta(el, clave, estado) {
  const config = RECORRIDOS[clave];
  if (!config) return;
  const datos = (estado || {})[clave] || null;
  const estados = estadosRuta(config.pasos, datos ? datos.hechos : []);
  // En Monitoreo, fuera del proyecto ganador no hay un «paso siguiente» que le toque al participante.
  if (clave === "monitoreo" && !(datos && datos.ganador)) estados.forEach((e, i) => { if (e === "actual") estados[i] = "pendiente"; });
  const hechos = estados.filter((e) => e === "hecho").length;
  const registrables = config.pasos.filter((p) => !p.fuera).length;
  const completo = datos && registrables > 0 && config.pasos.every((p, i) => p.fuera || estados[i] === "hecho");
  let resumen = datos
    ? `${hechos} de ${config.pasos.length} pasos con registro. ${datos.detalle || ""}`.trim()
    : `${config.pasos.length} pasos. Tu avance se marca cuando haya registro propio.`;
  if (completo && hechos < config.pasos.length) resumen = `Completaste lo que se registra en el sistema. ${datos.detalle || ""}`.trim();
  if (clave === "monitoreo" && !(datos && datos.ganador)) resumen = "No requiere acción de tu parte: el Monitoreo está activo solo para el proyecto ganador. Tu proyecto queda en cartera.";
  el.innerHTML = `
    <p class="ruta-sintesis">${escapeHtml(config.sintesis)}</p>
    ${mapaRuta(estados, `${config.titulo}: ${resumen}`)}
    <p class="ruta-estado">${escapeHtml(resumen)}</p>
    <details class="plegable ruta-detalle"><summary>Ver los ${config.pasos.length} pasos</summary>
    <ol class="ruta-pasos">${config.pasos.map((p, i) => `
      <li class="ruta-paso ruta-paso-${estados[i]}"><span class="ruta-paso-rotulo">${escapeHtml(p.rotulo)}</span><span class="ruta-paso-aporte">${escapeHtml(p.aporte)}</span>${p.fuera ? `<span class="ruta-paso-nota">${escapeHtml(p.nota || "Lo hacés vos, fuera del sistema: no hay que marcarlo ni cerrarlo acá.")}</span>` : ""}</li>`).join("")}</ol>
    </details>`;
  if (clave === "monitoreo") {
    // Fuera del proyecto ganador no hay nada que seguir: el botón llevaba a la Incubadora y confundía.
    const boton = el.closest?.("article")?.querySelector('[data-nav-target="proyecto-ia"]');
    if (boton) boton.hidden = !(datos && datos.ganador);
  }
}

let estadoRecorridos = null;

function renderRecorridos(forzar = false) {
  const contenedores = document.querySelectorAll("[data-ruta]");
  if (!contenedores.length) return;
  contenedores.forEach((el) => renderRuta(el, el.dataset.ruta, estadoRecorridos));
  if (estadoRecorridos && !forzar) return;
  apiFetch("/proyectos-ia/mi-recorrido")
    .then((estado) => {
      estadoRecorridos = estado;
      contenedores.forEach((el) => renderRuta(el, el.dataset.ruta, estado));
    })
    .catch(() => {});
}

function mostrarVista(nombre, actualizarUrl = true) {
  nombre = normalizarVista(nombre);
  document.body.dataset.module = moduloVista(nombre);
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById("view-" + nombre).classList.add("active");
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === nombre));
  centrarPestanaActiva();
  if (actualizarUrl) actualizarUrlVista(nombre);
  if (nombre === "inicio") renderRecorridos();
  if (nombre === "informes") cargarInformes();
  if (nombre === "aprendizaje") cargarAprendizaje();
  if (nombre === "actividad") cargarActividad();
  if (nombre === "proyecto-ia") cargarProyectoIA();
  if (nombre === "casos") cargarCasosProyectos();
  if (nombre === "segunda-vuelta") cargarSegundaVuelta();
  if (nombre === "conexiones") cargarRizomaCasos();
}

async function navegarPorUrl() {
  const hash = window.location.hash || "#/inicio";
  const informeMatch = hash.match(/^#\/informe\/(\d+)$/);
  if (informeMatch) {
    await abrirDetalle(Number(informeMatch[1]), false);
    return;
  }
  // Enlace del aviso por correo de una consulta: abre el proyecto en la vista docente (sólo admin).
  const proyectoMatch = hash.match(/^#\/proyecto-ia\/(\d+)$/);
  if (proyectoMatch) {
    mostrarVista("proyecto-ia", false);
    if (state.currentUser?.rol === "admin") {
      configurarEspacioIncubadora("docente");
      await cargarProyectoIADetalle(Number(proyectoMatch[1]));
    }
    return;
  }
  const vistaMatch = hash.match(/^#\/(inicio|analizar|informes|roles|habilidades|guia|marco|validacion|aprendizaje|actividad|proyecto-ia|casos|segunda-vuelta|rizoma|conexiones|sintesis)$/);
  mostrarVista(vistaMatch ? vistaMatch[1] : "inicio", false);
}

document.querySelectorAll("[data-nav-target]").forEach((el) => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    mostrarVista(el.dataset.navTarget);
  });
});

// Modo básico (por defecto) o avanzado: lo avanzado se oculta, no se borra. La elección se recuerda en este navegador.
const MODO_CLAVE = "gobernanza-modo";
function aplicarModo(avanzado) {
  document.body.classList.toggle("modo-basico", !avanzado);
  const check = document.getElementById("modo-avanzado");
  if (check) check.checked = avanzado;
}
let modoGuardado = null;
try { modoGuardado = localStorage.getItem(MODO_CLAVE); } catch (e) { modoGuardado = null; }
aplicarModo(modoGuardado === "avanzado");
document.getElementById("modo-avanzado")?.addEventListener("change", (e) => {
  try { localStorage.setItem(MODO_CLAVE, e.target.checked ? "avanzado" : "basico"); } catch (err) { /* sólo esta sesión */ }
  aplicarModo(e.target.checked);
  renderNav();
});

document.querySelectorAll("[data-scroll-target]").forEach((el) => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById(el.dataset.scrollTarget)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

window.addEventListener("hashchange", navegarPorUrl);

document.querySelector(".skip-link")?.addEventListener("click", (e) => {
  e.preventDefault();
  const main = document.getElementById("contenido");
  main?.focus({ preventScroll: true });
  main?.scrollIntoView({ block: "start" });
});



async function cargarUsuario() {
  try {
    state.currentUser = await apiFetch("/me");
    const el = document.getElementById("usuario-actual");
    if (el && state.currentUser) {
      el.textContent = `${state.currentUser.nombre || state.currentUser.email} · ${state.currentUser.rol}`;
    }
    const enMenu = document.getElementById("usuario-actual-menu");
    if (enMenu && state.currentUser) enMenu.textContent = `Sesión iniciada: ${state.currentUser.nombre || state.currentUser.email} · ${state.currentUser.rol}`;
    renderNav();
    document.dispatchEvent(new Event("gobernanza:usuario"));
    cargarRotuloVotacion();
    sincronizarCorreoNotificaciones();
    actualizarBotonesPares();
  } catch (_) {
    state.currentUser = null;
  }
}

async function cargarAreas() {
  try {
    state.areas = await apiFetch("/areas");
  } catch (e) {
    // silencioso: solo se usa para mostrar el nombre de la unidad en el historial
  }
}


// ---------- aprendizaje ----------

function renderInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[\[([^\]]+)\]\]/g, '<span class="wiki-link">$1</span>');
}

function renderMarkdownNota(markdown) {
  const lineas = String(markdown || "").split(/\r?\n/);
  const html = [];
  let listaAbierta = null;

  function cerrarLista() {
    if (listaAbierta) {
      html.push(`</${listaAbierta}>`);
      listaAbierta = null;
    }
  }

  function abrirLista(tipo) {
    if (listaAbierta !== tipo) {
      cerrarLista();
      html.push(`<${tipo}>`);
      listaAbierta = tipo;
    }
  }

  let codigo = null;
  lineas.forEach((linea) => {
    const limpia = linea.trim();
    if (limpia.startsWith("```")) {
      cerrarLista();
      if (codigo === null) codigo = [];
      else { html.push(`<pre class="nota-codigo">${escapeHtml(codigo.join("\n"))}</pre>`); codigo = null; }
      return;
    }
    if (codigo !== null) { codigo.push(linea); return; }
    if (!limpia) {
      cerrarLista();
      return;
    }
    if (limpia === "---") {
      cerrarLista();
      html.push('<hr />');
      return;
    }
    const heading = limpia.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      cerrarLista();
      const nivel = Math.min(heading[1].length, 4);
      html.push(`<h${nivel}>${renderInlineMarkdown(heading[2])}</h${nivel}>`);
      return;
    }
    const bullet = limpia.match(/^-\s+(.+)$/);
    if (bullet) {
      abrirLista("ul");
      html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      return;
    }
    const numbered = limpia.match(/^\d+\.\s+(.+)$/);
    if (numbered) {
      abrirLista("ol");
      html.push(`<li>${renderInlineMarkdown(numbered[1])}</li>`);
      return;
    }
    cerrarLista();
    html.push(`<p>${renderInlineMarkdown(limpia)}</p>`);
  });

  cerrarLista();
  return html.join("");
}

function extraerSeccionesAprendizaje(markdown) {
  return String(markdown || "").split(/\r?\n/)
    .map((linea) => linea.trim().match(/^##\s+(.+)$/))
    .filter(Boolean)
    .map((m) => m[1].replace(/^[0-9]+\.\s*/, ""));
}

function renderIndiceAprendizaje(markdown) {
  const el = document.getElementById("aprendizaje-indice");
  if (!el) return;
  const secciones = extraerSeccionesAprendizaje(markdown).slice(0, 12);
  if (!secciones.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `
    <div class="aprendizaje-indice-title">Índice operativo</div>
    <div class="aprendizaje-indice-list">
      ${secciones.map((s, i) => `<button type="button" class="aprendizaje-chip" data-seccion="${i + 1}">${renderInlineMarkdown(s)}</button>`).join("")}
    </div>`;
}

function renderResumenAprendizaje(markdown) {
  const el = document.getElementById("aprendizaje-quick");
  if (!el) return;
  const texto = String(markdown || "");
  const lentes = ["Conciliador", "Ajedrecista", "Cronista", "Orquesta", "Radiologo", "Radiólogo", "Rizoma", "Matematico", "Matemático"];
  const lentesPresentes = new Set(lentes
    .filter((l) => new RegExp(`(^|\\n)###\\s+${l}`, "i").test(texto))
    .map((l) => l.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "")));
  const reglas = (texto.match(/^[-*]\s+/gm) || []).length;
  // Ítems de la sección «Pendientes vivos», hasta la sección siguiente.
  const bloquePendientes = texto.split(/^##\s+/m).find((s) => /^[0-9.\s]*Pendientes vivos/i.test(s));
  const pendientes = bloquePendientes ? (bloquePendientes.match(/^\s*[-*]\s+/gm) || []).length : "s/d";
  const items = [
    [lentesPresentes.size || 0, "lentes con criterio"],
    [reglas, "reglas y límites"],
    [pendientes, "pendientes vivos"],
  ];
  el.innerHTML = items.map(([valor, label]) => `
    <div class="aprendizaje-stat">
      <strong>${escapeHtml(valor)}</strong>
      <span>${escapeHtml(label)}</span>
    </div>`).join("");
}

function renderCarrilesAprendizaje(data) {
  const multilente = document.getElementById("learning-lane-multilente-stats");
  const proyecto = document.getElementById("learning-lane-proyecto-stats");
  const metricas = data.metricas || {};
  const proyectoIA = data.proyecto_ia || {};
  if (multilente) {
    const estados = metricas.por_estado || {};
    multilente.innerHTML = [
      [metricas.total_eventos || 0, "eventos curados"],
      [estados.implementado || 0, "implementados"],
      [estados.propuesto || 0, "propuestos"],
    ].map(([valor, label]) => `<div><strong>${escapeHtml(valor)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  }
  if (proyecto) {
    const brechas = proyectoIA.brechas || {};
    proyecto.innerHTML = [
      [proyectoIA.total_proyectos || 0, "proyectos activos"],
      [proyectoIA.con_chat_ia || 0, "con chat IA"],
      [brechas.problema_como_herramienta || 0, "a reformular"],
      [brechas.sin_indicador || 0, "sin indicador claro"],
    ].map(([valor, label]) => `<div><strong>${escapeHtml(valor)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  }
}

function renderAprendizaje(data) {
  const el = document.getElementById("aprendizaje-contenido");
  const metaEl = document.getElementById("aprendizaje-meta");
  if (!el) return;
  const markdown = data.markdown || "";
  if (metaEl) {
    metaEl.textContent = `${data.fuente || "APRENDIZAJES.md"} · nota viva · actualizado ${fmtFecha(data.actualizado)}`;
  }
  renderResumenAprendizaje(markdown, data.metricas || {});
  renderCarrilesAprendizaje(data);
  renderIndiceAprendizaje(markdown);
  if (!markdown.trim()) {
    el.innerHTML = `<p class="empty-state">Todavía no hay criterios de calibración registrados.</p>`;
    return;
  }
  el.innerHTML = renderMarkdownNota(markdown);
  plegarSeccionesAprendizaje(el);
}

// Cada sección «##» de la memoria queda plegada; el índice las abre y lleva hasta ellas.
function plegarSeccionesAprendizaje(el) {
  const nodos = Array.from(el.childNodes);
  let actual = null;
  let n = 0;
  nodos.forEach((nodo) => {
    if (nodo.nodeName === "H2") {
      n += 1;
      actual = document.createElement("details");
      actual.className = "accordion-card aprendizaje-seccion";
      actual.id = `aprendizaje-seccion-${n}`;
      const resumen = document.createElement("summary");
      resumen.innerHTML = `<span>${nodo.innerHTML}</span>`;
      actual.appendChild(resumen);
      el.insertBefore(actual, nodo);
      nodo.remove();
      return;
    }
    if (actual) actual.appendChild(nodo);
  });
  document.querySelectorAll("#aprendizaje-indice [data-seccion]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const destino = document.getElementById(`aprendizaje-seccion-${chip.dataset.seccion}`);
      if (!destino) return;
      destino.open = true;
      destino.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

async function cargarAprendizaje() {
  const el = document.getElementById("aprendizaje-contenido");
  const metaEl = document.getElementById("aprendizaje-meta");
  if (!el) return;
  if (metaEl) metaEl.textContent = "Cargando APRENDIZAJES.md…";
  el.innerHTML = `<p class="hint">Leyendo criterios de calibración…</p>`;
  try {
    const data = await apiFetch("/aprendizaje");
    state.aprendizaje = data;
    renderAprendizaje(data);
  } catch (err) {
    if (metaEl) metaEl.textContent = "No se pudo cargar la memoria de calibración.";
    el.innerHTML = `<p class="empty-state">No se pudo cargar Calibración del sistema: ${escapeHtml(err.message)}</p>`;
  }
}

// ---------- analizar (flujo simple) ----------

const dropzone = document.getElementById("dropzone");
const inputArchivos = document.getElementById("input-archivos");
// Dos revisiones: la rápida (sólo cuentas, sin IA) es la principal; la profunda interpreta con IA y pide confirmar.
const btnRevisionRapida = document.getElementById("btn-revision-rapida");
const btnRevisionProfunda = document.getElementById("btn-revision-profunda");
const botonesRevision = [btnRevisionRapida, btnRevisionProfunda];
const btnDetectarFormulas = document.getElementById("btn-detectar-formulas");
const optDominio = document.getElementById("opt-dominio");
const optAmbito = document.getElementById("opt-ambito");
const optModoUsoMultilente = document.getElementById("opt-modo-uso-multilente");
const inputOrientacionAnalisis = document.getElementById("input-orientacion-analisis");
const optFormulasExcel = document.getElementById("opt-formulas-excel");
const optPatronesCalculo = document.getElementById("opt-patrones-calculo");
const optMetodoCalculo = document.getElementById("opt-metodo-calculo");
const optAlcanceSeries = document.getElementById("opt-alcance-series");
const optAvisoCorreo = document.getElementById("opt-aviso-correo");
const inputCorreoNotificacion = document.getElementById("input-correo-notificacion");
const optGuardarCorreo = document.getElementById("opt-guardar-correo");

function sincronizarCorreoNotificaciones() {
  if (!inputCorreoNotificacion || !optAvisoCorreo) return;
  const guardado = state.currentUser?.email_notificaciones || "";
  inputCorreoNotificacion.value = guardado;
  optAvisoCorreo.checked = Boolean(guardado);
  inputCorreoNotificacion.disabled = !optAvisoCorreo.checked;
  if (optGuardarCorreo) optGuardarCorreo.checked = true;
}

function emailNotificacionActual() {
  if (!optAvisoCorreo?.checked) return "";
  return String(inputCorreoNotificacion?.value || "").trim();
}

if (optAvisoCorreo) {
  optAvisoCorreo.addEventListener("change", () => {
    if (!inputCorreoNotificacion) return;
    inputCorreoNotificacion.disabled = !optAvisoCorreo.checked;
    if (optAvisoCorreo.checked) inputCorreoNotificacion.focus();
  });
}

dropzone.addEventListener("click", () => {
  if (!puedeOperarInformes()) {
    toast("Tu rol es de solo lectura: podés consultar informes, pero no cargar archivos.", true);
    return;
  }
  inputArchivos.click();
});
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); if (puedeOperarInformes()) dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (!puedeOperarInformes()) {
    toast("Tu rol es de solo lectura: podés consultar informes, pero no cargar archivos.", true);
    return;
  }
  agregarArchivos(e.dataTransfer.files);
});
inputArchivos.addEventListener("change", () => {
  agregarArchivos(inputArchivos.files);
  inputArchivos.value = "";
});

// Multilente analiza directo sólo Excel y CSV. Los PDF y las imágenes pasan antes por la
// revisión de lectura (/api/ocr): se avisa antes de enviar y se ofrece llevar el archivo allá.
const EXT_CARGA_DIRECTA = /\.(csv|xlsx|xls)$/i;
const EXT_REVISION_LECTURA = /\.(pdf|jpe?g|png|gif|bmp|tiff?|webp|heic|heif)$/i;
const REVISION_DB = "gobernanza-revision-lectura";
state.revisionLectura = [];

function guardarParaRevision(file) {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") { reject(new Error("sin almacenamiento local")); return; }
    const req = indexedDB.open(REVISION_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore("archivos");
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const tx = req.result.transaction("archivos", "readwrite");
      tx.objectStore("archivos").put({ archivo: file, nombre: file.name, tipo: file.type }, "pendiente");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    };
  });
}

async function abrirRevisionLectura(file) {
  try {
    if (file) await guardarParaRevision(file);
    window.location.href = "/api/ocr?desde=analizar";
  } catch (_) {
    // Sin almacenamiento local la herramienta pide elegir el archivo de nuevo.
    window.location.href = "/api/ocr";
  }
}

function renderAvisoRevisionLectura() {
  const el = document.getElementById("aviso-revision-lectura");
  if (!el) return;
  const lista = state.revisionLectura;
  el.hidden = !lista.length;
  if (!lista.length) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="aviso-stack">${lista.map((f, i) => `
    <div class="aviso-revision-item">
      <p><strong>«${escapeHtml(f.name)}» primero hay que leerlo y revisarlo.</strong> Los PDF y las imágenes no se analizan directo: en la revisión de lectura ves el original al lado de la tabla leída, corregís lo necesario y confirmás. Recién ahí se analiza.</p>
      <div class="actions-row">
        <button type="button" class="btn btn-primary" data-revisar-idx="${i}">Leer y revisar este archivo</button>
        <button type="button" class="btn btn-secondary" data-descartar-idx="${i}">Quitar</button>
      </div>
    </div>`).join("")}</div>`;
  el.querySelectorAll("[data-revisar-idx]").forEach((btn) => btn.addEventListener("click", () => abrirRevisionLectura(state.revisionLectura[Number(btn.dataset.revisarIdx)])));
  el.querySelectorAll("[data-descartar-idx]").forEach((btn) => btn.addEventListener("click", () => {
    state.revisionLectura.splice(Number(btn.dataset.descartarIdx), 1);
    renderAvisoRevisionLectura();
  }));
}

function agregarArchivos(fileList) {
  if (!puedeOperarInformes()) {
    toast("Tu rol es de solo lectura: podés consultar informes, pero no cargar archivos.", true);
    return;
  }
  for (const f of fileList) {
    if (EXT_REVISION_LECTURA.test(f.name)) {
      if (!state.revisionLectura.some((x) => x.name === f.name && x.size === f.size)) state.revisionLectura.push(f);
      continue;
    }
    if (state.archivos.length >= MAX_ARCHIVOS) {
      toast(`Máximo ${MAX_ARCHIVOS} archivos`, true);
      break;
    }
    if (!EXT_CARGA_DIRECTA.test(f.name)) {
      toast(`"${f.name}" no es Excel ni CSV. Multilente analiza Excel y CSV; los PDF y las imágenes pasan antes por la revisión de lectura.`, true);
      continue;
    }
    state.archivos.push(f);
  }
  renderAvisoRevisionLectura();
  renderListaArchivos();
}

function quitarArchivo(idx) {
  state.archivos.splice(idx, 1);
  renderListaArchivos();
}

async function cargarDocumentosPrueba() {
  const el = document.getElementById("sample-docs-list");
  if (!el) return;
  try {
    state.sampleDocs = await fetch("/samples/manifest.json", { cache: "no-store" }).then((r) => {
      if (!r.ok) throw new Error("no se pudo leer el manifiesto");
      return r.json();
    });
    renderDocumentosPrueba();
  } catch (e) {
    el.innerHTML = `<p class="empty-state">No se pudieron cargar los documentos de prueba.</p>`;
  }
}

function renderDocumentosPrueba() {
  const el = document.getElementById("sample-docs-list");
  if (!el) return;
  const docsConIdx = state.sampleDocs
    .map((doc, idx) => ({ doc, idx }))
    .sort((a, b) => (a.doc.orden || 0) - (b.doc.orden || 0));

  function card(item, tipo) {
    if (!item) return `<div class="sample-doc sample-empty">Sin documento cargado para este lado.</div>`;
    const { doc, idx } = item;
    const ok = tipo === "ok";
    return `
      <article class="sample-doc ${ok ? "sample-ok" : "sample-bad"}">
        <div>
          <span class="sample-pill ${ok ? "ok" : "bad"}">${ok ? "Sin señal esperada" : "Con señal esperada"}</span>
          <strong>${escapeHtml(doc.nombre)}</strong>
          <p>${escapeHtml(doc.descripcion)}</p>
        </div>
        <div class="sample-actions">
          <a class="btn btn-secondary btn-mini" href="${escapeHtml(doc.archivo)}" download>Descargar</a>
          <button type="button" class="btn btn-primary btn-mini" data-sample-idx="${idx}">Usar</button>
        </div>
      </article>
    `;
  }

  const casos = [];
  docsConIdx.forEach((item) => {
    const clave = item.doc.caso || `Caso ${item.doc.orden || casos.length + 1}`;
    let grupo = casos.find((c) => c.clave === clave);
    if (!grupo) {
      grupo = { clave, orden: item.doc.orden, tema: item.doc.tema || "", ok: null, error: null };
      casos.push(grupo);
    }
    if (item.doc.columna === "bueno" || item.doc.estado === "correcto") grupo.ok = item;
    if (item.doc.columna === "malo" || item.doc.estado === "incorrecto") grupo.error = item;
  });

  el.innerHTML = casos.map((grupo) => `
    <section class="sample-case-block">
      <div class="sample-case-head">
        <h4>${escapeHtml(grupo.clave)}</h4>
        <p>${escapeHtml(grupo.tema)}</p>
      </div>
      <div class="sample-compare-grid">
        ${card(grupo.ok, "ok")}
        ${card(grupo.error, "error")}
      </div>
      <div class="sample-run-actions">
        <button type="button" class="btn btn-primary" data-sample-pair="${Number(grupo.orden)}">Ejecutar ambos y descargar ZIP</button>
        <button type="button" class="btn btn-secondary btn-mini" data-sample-pair-new="${Number(grupo.orden)}" hidden>Ejecutar nuevamente</button>
        <span class="field-help">2 originales + 2 reportes PDF · análisis real con los modelos seleccionados</span>
      </div>
      <p class="sample-run-status" id="sample-pair-status-${Number(grupo.orden)}" role="status" aria-live="polite">Los informes quedan en el historial. Este recorrido no envía avisos por correo.</p>
    </section>
  `).join("");
  el.querySelectorAll("[data-sample-idx]").forEach((btn) => {
    btn.addEventListener("click", () => usarDocumentoPrueba(Number(btn.dataset.sampleIdx)));
  });
  el.querySelectorAll("[data-sample-pair]").forEach((btn) => {
    btn.addEventListener("click", () => ejecutarParEjemplos(Number(btn.dataset.samplePair)));
  });
  el.querySelectorAll("[data-sample-pair-new]").forEach((btn) => {
    btn.addEventListener("click", () => ejecutarParEjemplos(Number(btn.dataset.samplePairNew), true));
  });
  const buenos = casos.filter((c) => c.ok).length;
  const malos = casos.filter((c) => c.error).length;
  document.getElementById("sample-docs-summary").textContent = `${casos.length} temas de prueba. Un botón ejecuta los dos archivos de cada tema y descarga los originales y sus dos reportes PDF en un ZIP.`;
  document.getElementById("sample-count-ok").textContent = `${buenos} sin señal esperada`;
  document.getElementById("sample-count-bad").textContent = `${malos} con señal esperada`;
  actualizarBotonesPares();
}

// ---------- pares de ejemplos: flujo real sin espera visual artificial ----------
function actualizarBotonesPares() {
  document.querySelectorAll("[data-sample-pair]").forEach((btn) => {
    const run = samplePairRuns.get(Number(btn.dataset.samplePair));
    btn.disabled = samplePairBusy || !puedeOperarInformes() || Boolean(run?.failed);
    btn.textContent = run?.ready ? "Descargar ZIP otra vez" : run?.items?.length ? "Continuar y descargar ZIP" : "Ejecutar ambos y descargar ZIP";
  });
  document.querySelectorAll("[data-sample-pair-new]").forEach((btn) => {
    const run = samplePairRuns.get(Number(btn.dataset.samplePairNew));
    btn.hidden = !run?.ready && !run?.failed;
    btn.disabled = samplePairBusy || !puedeOperarInformes();
  });
  samplePairRuns.forEach((run, orden) => mostrarEstadoPar(orden, run.message, run.error));
}

function mostrarEstadoPar(orden, mensaje, error = false) {
  const run = samplePairRuns.get(orden);
  if (run) { run.message = mensaje; run.error = error; }
  const el = document.getElementById(`sample-pair-status-${orden}`);
  if (!el) return;
  el.classList.toggle("error", Boolean(error));
  const enlaces = (run?.items || []).map((item, idx) => `<a href="#/informe/${Number(item.informe_id)}">Ver informe ${idx + 1}</a>`).join(" · ");
  el.innerHTML = `${escapeHtml(mensaje || "Preparando los ejemplos…")}${enlaces ? `<br>${enlaces}` : ""}`;
}

async function ejecutarParEjemplos(orden, nueva = false) {
  if (samplePairBusy) return;
  if (!puedeOperarInformes()) {
    toast("Este botón requiere rol admin o analista.", true);
    return;
  }
  const docs = ["bueno", "malo"].map((lado) => state.sampleDocs.find((d) => d.orden === orden && d.columna === lado));
  if (docs.some((d) => !d)) { toast("No está completo este par de ejemplos.", true); return; }
  let run = nueva ? null : samplePairRuns.get(orden);
  if (!run) {
    const modelos = Array.from(document.querySelectorAll(".modelo-check-rapido:checked")).map((el) => el.value);
    if (!modelos.length) { toast("Elegí al menos un modelo en las opciones de análisis.", true); return; }
    run = { items: [], modelos, modo: optModoUsoMultilente?.value || "informe_en_construccion", ready: false, failed: false };
    samplePairRuns.set(orden, run);
  }
  samplePairBusy = true;
  actualizarBotonesPares();
  try {
    for (let i = run.items.length; i < docs.length; i += 1) {
      mostrarEstadoPar(orden, `Cargando ejemplo ${i + 1} de 2: ${docs[i].nombre}…`);
      const resp = await fetch(docs[i].archivo, { cache: "no-store" });
      if (!resp.ok) throw new Error("No se pudo descargar el original del catálogo.");
      const form = new FormData();
      form.append("archivos", await resp.blob(), docs[i].archivo.split("/").pop());
      Object.entries(docs[i].opciones || {}).forEach(([k, v]) => form.append(k, String(v)));
      form.append("modo_uso_multilente", run.modo);
      form.append("notificar", "false");
      // Un ejemplo del catálogo es siempre una prueba: no cuenta para las mediciones.
      form.append("es_prueba", "true");
      // Los ejemplos muestran el recorrido completo, con la interpretación y la confirmación.
      form.append("modo_revision", "profunda");
      run.modelos.forEach((m) => form.append("modelos", m));
      const creado = await window.prepararYConfirmarInforme(form, (f) => apiFetchForm("/analisis-rapido", f));
      run.items.push({ informe_id: creado.informe_id, job_id: creado.job.id });
    }
    const limite = Date.now() + 15 * 60 * 1000;
    while (!run.ready) {
      const trabajos = await Promise.all(run.items.map((item) => apiFetch(`/jobs/${item.job_id}`)));
      const fallido = trabajos.findIndex((j) => j.estado === "error");
      if (fallido >= 0) {
        run.failed = true;
        throw new Error(`El análisis ${fallido + 1} terminó con error. Revisá ese informe antes de volver a ejecutar; no se descarga un ZIP incompleto.`);
      }
      run.ready = trabajos.every((j) => j.estado === "finalizado");
      if (run.ready) break;
      const detalle = trabajos.map((j, i) => `Ejemplo ${i + 1}: ${{ pendiente: "en cola", procesando: "analizando", finalizado: "terminado" }[j.estado] || "consultando estado"}`).join(" · ");
      mostrarEstadoPar(orden, `${detalle}. Podés seguir viendo esta pantalla mientras termina.`);
      if (Date.now() >= limite) throw new Error("Los análisis siguen guardados. Tocá «Continuar y descargar ZIP» para volver a consultar su avance sin crear otros.");
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    mostrarEstadoPar(orden, "Ambos análisis terminaron. Preparando los cuatro archivos…");
    const { blob, filename } = await apiFetchDownload(`/ejemplos/${orden}/zip`, {
      sin_senal: run.items[0].informe_id, con_senal: run.items[1].informe_id,
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    mostrarEstadoPar(orden, "ZIP listo: dos originales y sus dos reportes PDF. Si no comenzó la descarga, tocá «Descargar ZIP otra vez». «Señal esperada» describe el ejemplo; el reporte muestra el resultado real.");
    toast("ZIP preparado con los cuatro archivos.");
  } catch (e) {
    mostrarEstadoPar(orden, e.message + " Los informes ya creados se conservan en el historial.", true);
    toast("No se pudo completar la descarga: " + e.message, true);
  } finally {
    samplePairBusy = false;
    actualizarBotonesPares();
  }
}
// ---------- fin de pares de ejemplos ----------

async function usarDocumentoPrueba(idx) {
  if (!puedeOperarInformes()) {
    toast("Tu rol es de solo lectura: podés descargar ejemplos, pero no usarlos para generar informes.", true);
    return;
  }
  const doc = state.sampleDocs[idx];
  if (!doc) return;
  if (state.archivos.length >= MAX_ARCHIVOS) {
    toast(`Máximo ${MAX_ARCHIVOS} archivos`, true);
    return;
  }
  try {
    const resp = await fetch(doc.archivo, { cache: "no-store" });
    if (!resp.ok) throw new Error("no se pudo descargar el archivo");
    const blob = await resp.blob();
    const nombre = doc.archivo.split("/").pop() || "documento-prueba.xlsx";
    const file = new File([blob], nombre, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    state.archivos.push(file);
    const opts = doc.opciones || {};
    if (optDominio && opts.dominio) optDominio.value = opts.dominio;
    if (optAmbito) optAmbito.value = opts.ambito || "publico";
    if (optFormulasExcel) optFormulasExcel.checked = Boolean(opts.revisar_formulas_excel);
    if (optPatronesCalculo) optPatronesCalculo.checked = Boolean(opts.inferir_patrones_calculo);
    if (optMetodoCalculo) optMetodoCalculo.checked = Boolean(opts.revisar_metodo_calculo);
    if (optAlcanceSeries && opts.alcance_series) optAlcanceSeries.value = opts.alcance_series;
    renderListaArchivos();
    toast(`Documento agregado: ${doc.nombre}`);
  } catch (e) {
    toast("No se pudo cargar el documento de prueba: " + e.message, true);
  }
}


function renderListaArchivos() {
  const el = document.getElementById("lista-archivos");
  if (!puedeOperarInformes()) {
    el.innerHTML = `<p class="empty-state">Tu rol es de solo lectura: podés consultar informes y descargar reportes, pero no generar nuevos análisis.</p>`;
    botonesRevision.forEach((b) => { b.disabled = true; });
    if (btnDetectarFormulas) btnDetectarFormulas.disabled = true;
    return;
  }
  if (!state.archivos.length) {
    el.innerHTML = "";
    botonesRevision.forEach((b) => { b.disabled = true; });
    if (btnDetectarFormulas) btnDetectarFormulas.disabled = true;
    return;
  }
  el.innerHTML = `<div class="archivo-lista">${state.archivos
    .map((f, i) => `
      <div class="archivo-item">
        <span class="archivo-nombre">${f.name}</span>
        <span class="archivo-size">${(f.size / 1024).toFixed(0)} KB</span>
        <button type="button" class="archivo-quitar" data-idx="${i}" aria-label="Quitar">✕</button>
      </div>`)
    .join("")}</div>`;
  el.querySelectorAll(".archivo-quitar").forEach((btn) => {
    btn.addEventListener("click", () => quitarArchivo(Number(btn.dataset.idx)));
  });
  botonesRevision.forEach((b) => { b.disabled = false; });
  if (btnDetectarFormulas) btnDetectarFormulas.disabled = !state.archivos.some((f) => /\.(xlsx|xls)$/i.test(f.name));
}

// Envía la carga en el modo pedido. La rápida no tiene interpretación que confirmar: entra directo en cola y
// sus archivos quedan en esta pestaña para pasar a la profunda. Devuelve el informe creado, o null si falló.
async function enviarRevision(formData, modo) {
  formData.set("modo_revision", modo);
  const rapida = modo === "rapida";
  document.querySelector("#view-analizar .card").style.display = "none";
  document.getElementById("cargando-rapida").hidden = !rapida;
  document.getElementById("cargando-profunda").hidden = rapida;
  document.getElementById("analizar-cargando").style.display = "block";
  botonesRevision.forEach((b) => { b.disabled = true; });
  if (btnDetectarFormulas) btnDetectarFormulas.disabled = true;
  try {
    const resultado = rapida
      ? await apiFetchForm("/analisis-rapido", formData)
      : await window.prepararYConfirmarInforme(formData, (f) => apiFetchForm("/analisis-rapido", f));
    if (rapida) window.RevisionModo.guardar(resultado.informe_id, formData);
    return resultado;
  } finally {
    document.querySelector("#view-analizar .card").style.display = "block";
    document.getElementById("analizar-cargando").style.display = "none";
  }
}

async function pasarARevisionProfunda() {
  const aviso = document.getElementById("pasar-profunda-aviso");
  const form = window.RevisionModo.paraProfunda(state.detalleId);
  if (!form) {
    aviso.textContent = "Los archivos de esta revisión ya no están en esta pestaña (por ejemplo, porque se recargó la página). Elegilos de nuevo en «Analizar» y pedí la revisión profunda.";
    return;
  }
  aviso.textContent = "";
  mostrarVista("analizar");
  try {
    const resultado = await enviarRevision(form, "profunda");
    toast("Informe en cola de análisis");
    await cargarAreas();
    abrirDetalle(resultado.informe_id);
  } catch (err) {
    if (err.cancelada) toast(err.message);
    else toast("No se pudo pasar a la revisión profunda: " + err.message, true);
  } finally {
    renderListaArchivos();
  }
}

async function ejecutarAnalisisRapido(extra = {}) {
  if (!puedeOperarInformes()) {
    toast("Tu rol es de solo lectura: no puede generar nuevos análisis.", true);
    return;
  }
  if (!state.archivos.length) return;
  const formData = new FormData();
  state.archivos.forEach((f) => formData.append("archivos", f));
  const anteriorId = document.getElementById("informe-anterior-id")?.value;
  const contextoValidez = document.getElementById("contexto-validacion")?.value.trim();
  if (anteriorId) {
    if (!Number.isInteger(Number(anteriorId)) || Number(anteriorId) < 1) { toast("Indicá un ID de informe anterior válido.", true); return; }
    formData.append("informe_anterior_id", anteriorId);
  }
  if (contextoValidez) {
    try { JSON.parse(contextoValidez); } catch { toast("No se pudo leer el formato de las condiciones de los datos. Abrí “Ver un ejemplo y cómo escribirlo” y revisá las comillas, llaves y corchetes.", true); return; }
    formData.append("contexto_validacion", contextoValidez);
  }
  const dominioElegido = optDominio?.value || "auto";
  if (dominioElegido !== "auto") formData.append("dominio", dominioElegido);
  formData.append("ambito", optAmbito?.value || "publico");
  formData.append("revisar_formulas_excel", extra.revisarFormulasExcel || optFormulasExcel.checked ? "true" : "false");
  formData.append("inferir_patrones_calculo", optPatronesCalculo.checked ? "true" : "false");
  // Archivos de esta carga que se derivaron a la revisión de lectura: el informe los declara.
  if (state.revisionLectura?.length) formData.append("derivados_revision", state.revisionLectura.map((f) => f.name).join(String.fromCharCode(10)));
  formData.append("revisar_metodo_calculo", optMetodoCalculo.checked ? "true" : "false");
  formData.append("alcance_series", optAlcanceSeries?.value || "todas");
 formData.append("modo_uso_multilente", optModoUsoMultilente?.value || "informe_en_construccion");
  const orientacionAnalisis = String(inputOrientacionAnalisis?.value || "").trim();
  if (orientacionAnalisis) formData.append("orientacion_analisis", orientacionAnalisis);
  const correoNotificacion = emailNotificacionActual();
  if (optAvisoCorreo?.checked && !correoNotificacion) {
    toast("Indicá un correo para recibir el aviso o desactivá la notificación", true);
    inputCorreoNotificacion?.focus();
    return;
  }
  if (correoNotificacion) {
    formData.append("notify_email", correoNotificacion);
    formData.append("guardar_notify_email", optGuardarCorreo?.checked ? "true" : "false");
  }
  const modelosElegidosRapido = Array.from(document.querySelectorAll(".modelo-check-rapido:checked")).map((el) => el.value);
  const iaAutomatica = document.getElementById("ia-automatica")?.checked ?? true;
  if (!iaAutomatica && modelosElegidosRapido.length === 0) {
    toast("Elegí al menos un modelo para triangular", true);
    return;
  }
  if (!iaAutomatica) modelosElegidosRapido.forEach((m) => formData.append("modelos", m));
  // «Es una prueba (no cuenta para las mediciones)»: queda con el informe y la medición lo excluye.
  const optEsPrueba = document.getElementById("opt-es-prueba");
  formData.append("es_prueba", optEsPrueba?.checked ? "true" : "false");

  try {
    const resultado = await enviarRevision(formData, extra.modo || "rapida");
    state.archivos = [];
    if (optEsPrueba) optEsPrueba.checked = false;
    document.getElementById("informe-anterior-id").value = "";
    document.getElementById("contexto-validacion").value = "";
    if (inputOrientacionAnalisis) inputOrientacionAnalisis.value = "";
    renderListaArchivos();
    if (correoNotificacion && optGuardarCorreo?.checked && state.currentUser) state.currentUser.email_notificaciones = correoNotificacion;
    toast(correoNotificacion ? "Informe en cola. Te avisará por correo al finalizar." : "Informe en cola de análisis");
    await cargarAreas();
    abrirDetalle(resultado.informe_id);
  } catch (err) {
    if (err.detalle?.codigo === "requiere_revision_lectura") {
      const nombres = new Set(err.detalle.archivos || []);
      state.revisionLectura.push(...state.archivos.filter((f) => nombres.has(f.name)));
      // Los que quedaron afuera se declaran en el informe de los demás archivos.
      state.archivos = state.archivos.filter((f) => !nombres.has(f.name));
      renderAvisoRevisionLectura();
    }
    if (err.cancelada) toast(err.message);  // la persona canceló la lectura: no es un error
    else toast("No se pudo analizar: " + err.message, true);
  } finally {
    renderListaArchivos();
  }
}

document.getElementById("btn-descargar-reporte-global")?.addEventListener("click", descargarReporteSeleccionado);
document.querySelectorAll("[data-reporte-formato]").forEach((btn) => btn.addEventListener("click", descargarReporteSeleccionado));
btnRevisionRapida.addEventListener("click", () => ejecutarAnalisisRapido({ modo: "rapida" }));
btnRevisionProfunda.addEventListener("click", () => ejecutarAnalisisRapido({ modo: "profunda" }));
document.getElementById("btn-pasar-profunda")?.addEventListener("click", pasarARevisionProfunda);
if (btnDetectarFormulas) {
  btnDetectarFormulas.addEventListener("click", () => {
    optFormulasExcel.checked = true;
    ejecutarAnalisisRapido({ revisarFormulasExcel: true });
  });
}

// ---------- informes (historial) ----------

async function cargarInformes() {
  if (!state.areas.length) await cargarAreas();
  try {
    state.informes = await apiFetch("/informes");
    renderTablaInformes();
  } catch (e) {
    toast("No se pudieron cargar los informes: " + e.message, true);
  }
}

function badgeEstadoInforme(i) {
  if (i.analysis_status === "pendiente") return `<span class="badge badge-neutral">en cola</span>`;
  if (i.analysis_status === "procesando") return `<span class="badge badge-media">analizando</span>`;
  if (i.analysis_status === "error") return `<span class="badge badge-critico">error</span>`;
  if (!i.analysis_status && i.interpretacion_estado === "interpretando") return `<span class="badge badge-neutral">interpretando</span>`;
  if (!i.analysis_status && i.interpretacion_estado === "pendiente_confirmacion") return `<span class="badge badge-neutral">pendiente de confirmación</span>`;
  if (Number.isInteger(i.n_casos)) return `<span class="badge ${i.n_casos ? "badge-media" : "badge-ok"}">${i.n_casos} caso${i.n_casos === 1 ? "" : "s"} para revisar</span>`;
  if (!i.n_hallazgos) return `<span class="badge badge-ok">sin señales</span>`;
  return `${badgeSeveridad(i.severidad_max)}<span class="hallazgos-count">${i.n_hallazgos} hallazgo${i.n_hallazgos === 1 ? "" : "s"}</span>`;
}

// Mediciones: el informe marcado como prueba no cuenta; el cierre sin responder queda a la vista como pendiente.
function badgesMedicion(i) {
  return (i.es_prueba ? ` <span class="badge badge-neutral" title="No cuenta para las mediciones">prueba</span>` : "")
    + (i.cierre_pendiente ? ` <span class="badge badge-media" title="Abrilo y respondé al final: ¿corregiste algo del informe antes de entregarlo?">cierre pendiente</span>` : "");
}

function badgeDecision(i) {
  if (!i.decision_tomada) {
    return i.n_hallazgos ? `<span class="badge badge-neutral">pendiente</span>` : `<span class="hint">—</span>`;
  }
  const etiquetas = { escalar_formalmente: "escalado", sin_escalamiento: "sin escalamiento", cerrar: "cerrado" };
  const crudo = String(i.tipo_decision || "");
  const legible = etiquetas[crudo] || etiquetas[crudo.toLowerCase()] || crudo.toLowerCase().replace(/_/g, " ");
  return `<span class="badge badge-neutral">${escapeHtml(legible)}</span>`;
}

function renderTablaInformes() {
  const el = document.getElementById("tabla-informes");
  if (!state.informes.length) {
    el.innerHTML = `<div class="empty-state">Todavía no analizaste ningún informe.</div>`;
    return;
  }
  const mostrarBorrado = puedeBorrarInformes();
  el.innerHTML = `
    <table>
      <thead><tr><th>Período</th><th>Revisión</th><th>Dominio</th><th>Resultado</th><th>Decisión</th><th>Usuario</th><th>Cargado</th><th>Acciones</th></tr></thead>
      <tbody>
        ${state.informes.map((i) => `
          <tr data-id="${i.id}">
            <td>${escapeHtml(i.periodo)}<div class="hint">${escapeHtml((i.archivos_origen || []).join(" · "))}</div></td>
            <td>${escapeHtml(globalThis.window?.RevisionModo?.nombre(i) || "Revisión profunda")}</td>
            <td>${escapeHtml(i.dominio)}</td>
            <td class="col-resultado">${badgeEstadoInforme(i)}${badgesMedicion(i)}</td>
            <td>${badgeDecision(i)}</td>
            <td>${escapeHtml(i.creado_por || '-')}</td>
            <td>${fmtFecha(i.creado_en)}</td>
            <td><div class="informe-acciones"><button type="button" class="btn btn-secondary btn-mini informe-ver-btn" data-ver-id="${i.id}">Ver informe</button>${mostrarBorrado ? `<button type="button" class="btn btn-secondary btn-mini informe-delete-btn" data-delete-id="${i.id}">Borrar</button>` : ""}</div></td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  el.querySelectorAll("tbody tr").forEach((tr) => {
    tr.addEventListener("click", () => abrirDetalle(Number(tr.dataset.id)));
  });
  el.querySelectorAll("[data-ver-id]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      abrirDetalle(Number(btn.dataset.verId));
    });
  });
  el.querySelectorAll("[data-delete-id]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      borrarInforme(Number(btn.dataset.deleteId));
    });
  });
}

async function borrarInforme(id) {
  const informe = state.informes.find((item) => item.id === id);
  const etiqueta = informe ? `${informe.periodo} · ${informe.dominio}` : `#${id}`;
  if (!window.confirm(`¿Borrar el informe ${etiqueta}? Esta acción elimina sus hallazgos, análisis, decisión y reportes asociados.`)) return;
  try {
    await apiFetch(`/informes/${id}`, { method: "DELETE" });
    toast("Informe borrado");
    if (state.detalleId === id) state.detalleId = null;
    await cargarInformes();
  } catch (e) {
    toast("No se pudo borrar el informe: " + e.message, true);
  }
}


// ---------- actividad admin ----------

function actividadMetricTile(valor, label) {
  return `<div class="summary-tile"><div class="num">${escapeHtml(valor)}</div><div class="lbl">${escapeHtml(label)}</div></div>`;
}

function renderActividad(data) {
  const m = data.metricas || {};
  const resumen = data.resumen_operativo || {};
  const cola = `${resumen.jobs_pendientes ?? 0} pendientes · ${resumen.jobs_procesando ?? 0} procesando · ${resumen.jobs_error ?? 0} con error`;
  document.getElementById("actividad-resumen").innerHTML = [
    actividadMetricTile(m.usuarios_total ?? 0, "usuarios"),
    actividadMetricTile(m.analistas ?? 0, "analistas"),
    actividadMetricTile(resumen.usuarios_con_informes ?? 0, "usuarios con cargas"),
    actividadMetricTile(resumen.usuarios_con_proyecto_ia ?? m.usuarios_con_proyecto_ia ?? 0, "Gobernanza Incubadora"),
    actividadMetricTile(m.informes_total ?? 0, "informes"),
    actividadMetricTile(m.informes_24h ?? 0, "informes 24h"),
    actividadMetricTile(m.hallazgos_total ?? 0, "hallazgos"),
    actividadMetricTile(m.decisiones_total ?? 0, "decisiones"),
    actividadMetricTile(m.aprendizajes_total ?? 0, "aprendizajes"),
  ].join("");

  document.getElementById("actividad-operativa").innerHTML = `
    <div><span>Última carga</span><strong>${fmtFecha(resumen.ultima_carga)}</strong></div>
    <div><span>Última decisión</span><strong>${fmtFecha(resumen.ultima_decision)}</strong></div>
    <div><span>Usuarios con cargas 24h</span><strong>${resumen.usuarios_con_informes_24h ?? 0}</strong></div>
    <div><span>Cola de análisis</span><strong>${escapeHtml(cola)}</strong></div>
  `;

  renderReportePedagogicoActividad(data);
  renderProgresoProyectosIA(data);

  const modelos = Object.entries(data.modelos_usados || {}).sort((a, b) => b[1] - a[1]);
  document.getElementById("actividad-modelos").innerHTML = modelos.length
    ? modelos.map(([modelo, total]) => `<span class="activity-pill">${escapeHtml(modelo)} · ${total}</span>`).join("")
    : `<span class="hint">Todavía no hay modelos registrados en jobs.</span>`;

  document.getElementById("actividad-usuarios").innerHTML = `
    <table>
      <thead><tr><th>Usuario</th><th>Rol</th><th>Informes</th><th>Hallazgos</th><th>Decisiones</th><th>Último informe</th></tr></thead>
      <tbody>
        ${(data.usuarios || []).map((u) => `
          <tr>
            <td>${escapeHtml(u.email || "-")}</td>
            <td>${escapeHtml(u.rol || "-")}</td>
            <td>${u.informes || 0}</td>
            <td>${u.hallazgos || 0}</td>
            <td>${u.decisiones || 0}</td>
            <td>${fmtFecha(u.ultimo_informe)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  document.getElementById("actividad-informes").innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Usuario</th><th>Dominio</th><th>Hallazgos</th><th>Decisión</th><th>Cargado</th></tr></thead>
      <tbody>
        ${(data.ultimos_informes || []).map((i) => `
          <tr data-id="${i.id}">
            <td>#${i.id}</td>
            <td>${escapeHtml(i.creado_por || "-")}</td>
            <td>${escapeHtml(i.dominio || "-")}</td>
            <td>${i.hallazgos || 0}</td>
            <td>${i.decision ? '<span class="badge badge-ok">sí</span>' : '<span class="badge badge-neutral">pendiente</span>'}</td>
            <td>${fmtFecha(i.creado_en)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  document.querySelectorAll("#actividad-informes tbody tr").forEach((tr) => {
    tr.addEventListener("click", () => abrirDetalle(Number(tr.dataset.id)));
  });
}

function renderMetricasCertificaciones(data) {
  const el = document.getElementById("actividad-certificaciones");
  if (!el) return;
  const micro = data?.micro || {};
  const macro = data?.macro || {};
  const observaciones = data?.meso?.observaciones_recurrentes || [];
  const faltantes = data?.meso?.faltantes_recurrentes || [];
  const protocolos = macro.protocolos || [];
  el.innerHTML = `
    <div class="cert-analytics-micro">
      ${actividadMetricTile(micro.evaluaciones || 0, "evaluaciones")}
      ${actividadMetricTile(micro.reevaluaciones || 0, "con reevaluación")}
      ${actividadMetricTile(micro.evidencias || 0, "evidencias")}
      ${actividadMetricTile(micro.sellos_vigentes || 0, "sellos vigentes")}
    </div>
    <div class="cert-analytics-grid">
      <section>
        <h4>Nivel meso · patrones de controles</h4>
        ${observaciones.length ? observaciones.map((item) => `<div class="learning-event-row"><span>${escapeHtml(item.codigo)} · ${escapeHtml(item.nombre)}</span><strong>${contar(item.observado, "observada")}</strong></div>`).join("") : '<p class="hint">Todavía no hay observaciones recurrentes.</p>'}
        ${faltantes.length ? `<h5>Información no evaluable</h5>${faltantes.map((item) => `<div class="learning-event-row"><span>${escapeHtml(item.codigo)} · ${escapeHtml(item.nombre)}</span><strong>${item.no_evaluable}</strong></div>`).join("")}` : ""}
      </section>
      <section>
        <h4>Nivel macro · preparación institucional</h4>
        ${protocolos.length ? protocolos.map((item) => `<article class="cert-protocol-row"><div><strong>${escapeHtml(item.protocolo)}</strong><span>${escapeHtml(item.nombre)}</span></div><small>${item.evaluaciones} evaluaciones · ${item.con_observaciones} con observaciones · ${item.sellos_vigentes} sellos vigentes</small></article>`).join("") : '<p class="hint">Los protocolos están listos; todavía no comenzaron evaluaciones reales.</p>'}
        <p class="cert-analytics-reading">${escapeHtml(macro.lectura || "")}</p>
      </section>
    </div>`;
}


function activityActionLabel(action) {
  const labels = {
    analisis_rapido_encolado: "Análisis iniciado",
    analisis_solicitado: "Análisis solicitado",
    reporte_estructurado_generado: "Reporte generado",
    reporte_descargado: "Reporte descargado",
    decision_humana_registrada: "Decisión humana",
    informe_borrado: "Informe borrado",
    proyecto_creado: "Proyecto creado",
    proyecto_actualizado: "Proyecto actualizado",
    chat_ia_intercambio: "Diálogo con IA",
    consulta_docente_enviada: "Consulta docente",
    intervencion_docente_enviada: "Intervención docente",
    retroalimentacion_guardada: "Retroalimentación",
    aprendizaje_curado: "Aprendizaje curado",
    evaluacion_piloto_registrada: "Evaluación del piloto",
    cierre_informe_registrado: "Pregunta de cierre del informe",
  };
  return labels[action] || action.replaceAll("_", " ");
}

function activityModuleLabel(module) {
  const labels = {
    multilente: "Gobernanza Multilente",
    incubadora: "Gobernanza Incubadora",
    aprendizaje: "Aprendizaje",
    sistema: "Sistema",
  };
  return labels[module] || module;
}

function pluralizeEs(total, singular, plural) {
  return Number(total) === 1 ? singular : plural;
}

function renderReportePedagogicoActividad(data) {
  const target = document.getElementById("actividad-reporte-pedagogico");
  if (!target) return;
  const m = data.metricas || {};
  const resumen = data.resumen_operativo || {};
  const eventos = data.eventos_actividad || {};
  const eventosPorModulo = eventos.por_modulo || {};
  const eventosPorAccion = eventos.por_accion || {};
  const recientes = eventos.recientes || [];
  const proyectos = data.progreso_proyectos_ia || [];

  const usuariosConCargas = resumen.usuarios_con_informes ?? 0;
  const informes = m.informes_total ?? 0;
  const hallazgos = m.hallazgos_total ?? 0;
  const registrosDecision = m.decisiones_total ?? 0;
  const aprendizajes = m.aprendizajes_total ?? 0;
  const jobsError = resumen.jobs_error ?? m.jobs_error ?? 0;
  const eventos24h = eventos.ultimas_24h ?? m.eventos_actividad_24h ?? 0;
  const chatsIA = m.mensajes_chat_ia_proyecto_ia ?? 0;
  const respuestasIA = m.respuestas_ia_proyecto_ia ?? 0;
  const consultasDocente = m.consultas_docente_total ?? 0;
  const proyectosSegundaVuelta = m.proyectos_necesitan_segunda_vuelta ?? 0;
  const proyectosEntregados = m.proyectos_ia_entregados ?? 0;
  const evaluacionesPiloto = m.evaluaciones_piloto_total ?? 0;
  const evaluacionesUtiles = m.evaluaciones_piloto_utiles ?? 0;
  const falsosPositivos = m.evaluaciones_piloto_falsos_positivos ?? 0;
  const omisiones = m.evaluaciones_piloto_omisiones ?? 0;
  const proyectosActivos = proyectos.filter((p) => (p.mensajes_chat_ia || 0) > 0 || (p.consultas_docente || 0) > 0 || p.contexto).length;

  const estabilidad = jobsError === 0
    ? "La plataforma está operando sin errores de análisis registrados."
    : `Hay ${jobsError} ${pluralizeEs(jobsError, "análisis con error", "análisis con error")} que conviene revisar antes de sacar conclusiones.`;
  const estadoAprendizaje = aprendizajes > 0
    ? `Hay ${aprendizajes} ${pluralizeEs(aprendizajes, "aprendizaje curado", "aprendizajes curados")} para convertir uso en criterio.`
    : "Todavía falta cerrar aprendizajes curados: la evidencia existe, pero necesita selección docente.";
  const lectura24h = eventos24h > 0
    ? `En las últimas 24 horas quedaron ${eventos24h} ${pluralizeEs(eventos24h, "registro", "registros")} de uso trazable.`
    : "No hay eventos nuevos en las últimas 24 horas.";
  const foco = proyectosSegundaVuelta > 0
    ? `${proyectosSegundaVuelta} ${pluralizeEs(proyectosSegundaVuelta, "proyecto necesita", "proyectos necesitan")} segunda vuelta sobre formulación del problema.`
    : "Los proyectos activos no muestran alertas fuertes de segunda vuelta en este corte.";

  const accionesClave = Object.entries(eventosPorAccion)
    .filter(([, total]) => Number(total) > 0)
    .slice(0, 8);
  const modulos = Object.entries(eventosPorModulo)
    .filter(([, total]) => Number(total) > 0)
    .sort((a, b) => b[1] - a[1]);
  const eventosRecientes = recientes.slice(0, 8);

  const proyectosParaMirar = proyectos
    .filter((p) => p.diagnostico?.necesita_segunda_vuelta || (p.consultas_docente || 0) > 0 || (p.mensajes_chat_ia || 0) >= 3)
    .slice(0, 5);

  target.innerHTML = `
    <div class="pedagogical-thesis">
      <strong>Lectura docente</strong>
      <p>La evidencia más valiosa aparece cuando el estudiante no copia la salida de la IA: la prueba, la corrige, pide contexto y vuelve más claro el problema que quiere resolver.</p>
    </div>

    <div class="pedagogical-metrics pedagogical-metrics-wide">
      <div><strong>${usuariosConCargas}</strong><span>usuarios con cargas en Multilente</span></div>
      <div><strong>${proyectosActivos}</strong><span>proyectos activos en Incubadora</span></div>
      <div><strong>${chatsIA}</strong><span>mensajes de estudiantes a la IA</span></div>
      <div><strong>${consultasDocente}</strong><span>interacciones con el docente</span></div>
      <div><strong>${eventos24h}</strong><span>eventos trazables 24h</span></div>
      <div><strong>${evaluacionesPiloto}</strong><span>evaluaciones humanas del piloto</span></div>
    </div>

    <div class="learning-signal-grid">
      <div class="learning-signal">
        <span>Multilente</span>
        <strong>${informes} informes · ${hallazgos} señales</strong>
        <p>Sirve para mostrar cómo distintas lentes ordenan una revisión sin reemplazar el criterio humano.</p>
      </div>
      <div class="learning-signal">
        <span>Incubadora</span>
        <strong>${chatsIA} mensajes · ${respuestasIA} respuestas IA</strong>
        <p>Permite observar cómo cada estudiante transforma una necesidad difusa en un proyecto formulable.</p>
      </div>
      <div class="learning-signal">
        <span>Decisión humana</span>
        <strong>${registrosDecision} registros · ${proyectosEntregados} entregas</strong>
        <p>Marca dónde hay apropiación: decisión, entrega, consulta o corrección explícita.</p>
      </div>
      <div class="learning-signal">
        <span>Aprendizaje</span>
        <strong>${aprendizajes} criterios curados</strong>
        <p>Convierte casos puntuales en reglas reutilizables para mejorar el ecosistema.</p>
      </div>
      <div class="learning-signal">
        <span>Validación del piloto</span>
        <strong>${evaluacionesUtiles} útiles · ${falsosPositivos} falsos positivos · ${omisiones} omisiones</strong>
        <p>Separa el funcionamiento técnico de la utilidad confirmada por una persona.</p>
      </div>
    </div>

    <table class="pedagogical-table">
      <thead>
        <tr><th>Pregunta docente</th><th>Evidencia disponible</th><th>Uso posible</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>¿Están usando el sistema?</td>
          <td>${lectura24h}</td>
          <td>Medir participación real sin depender solo del foro o de percepciones.</td>
        </tr>
        <tr>
          <td>¿La IA ayuda a pensar?</td>
          <td>${contar(chatsIA, "mensaje")} de estudiantes y ${contar(respuestasIA, "respuesta")} de IA en proyectos.</td>
          <td>Reconstruir el proceso: problema inicial, preguntas, ajuste y decisión propia.</td>
        </tr>
        <tr>
          <td>¿Dónde intervenir?</td>
          <td>${escapeHtml(foco)}</td>
          <td>Elegir comentarios docentes breves, personalizados y no invasivos.</td>
        </tr>
        <tr>
          <td>¿Qué aprendió Gobernanza?</td>
          <td>${escapeHtml(estadoAprendizaje)}</td>
          <td>Separar bitácora automática de aprendizaje institucional aprobado.</td>
        </tr>
        <tr>
          <td>¿El análisis fue útil?</td>
          <td>${evaluacionesPiloto} evaluación(es): ${evaluacionesUtiles} útiles, ${falsosPositivos} falsos positivos y ${omisiones} omisiones.</td>
          <td>Medir el piloto con validación humana y no solamente con pruebas técnicas.</td>
        </tr>
      </tbody>
    </table>

    <div class="learning-dashboard">
      <div>
        <h4>Eventos por módulo</h4>
        ${modulos.length ? modulos.map(([modulo, total]) => `
          <div class="learning-event-row">
            <span>${escapeHtml(activityModuleLabel(modulo))}</span>
            <strong>${total}</strong>
          </div>
        `).join("") : "<p class='hint'>Sin eventos registrados todavía.</p>"}
      </div>
      <div>
        <h4>Acciones más frecuentes</h4>
        ${accionesClave.length ? accionesClave.map(([accion, total]) => `
          <div class="learning-event-row">
            <span>${escapeHtml(activityActionLabel(accion))}</span>
            <strong>${total}</strong>
          </div>
        `).join("") : "<p class='hint'>Sin acciones registradas todavía.</p>"}
      </div>
    </div>

    ${proyectosParaMirar.length ? `
      <div class="learning-watchlist">
        <h4>Casos que conviene mirar</h4>
        ${proyectosParaMirar.map((p) => `
          <div class="learning-watch-item">
            <strong>${escapeHtml(p.nombre && p.nombre !== p.email ? p.nombre : p.email || "Participante")}</strong>
            <span>${escapeHtml(p.etapa || "Sin etapa")} · ${p.mensajes_chat_ia || 0} mensajes · ${p.interacciones_docente || 0} intervenciones</span>
          </div>
        `).join("")}
      </div>
    ` : ""}

    ${eventosRecientes.length ? `
      <div class="learning-recent">
        <h4>Últimos rastros útiles</h4>
        ${eventosRecientes.map((evento) => `
          <div class="learning-recent-item">
            <span>${escapeHtml(activityActionLabel(evento.accion || ""))}</span>
            <strong>${escapeHtml(evento.resumen || activityModuleLabel(evento.modulo || "actividad"))}</strong>
            <em>${fmtFecha(evento.creado_en)}</em>
          </div>
        `).join("")}
      </div>
    ` : ""}

    <div class="pedagogical-callout">
      <strong>Lectura para el informe final</strong>
      <span>${escapeHtml(estabilidad)} El material más potente para mostrar no es solo el resultado final, sino la secuencia de ajustes: qué preguntó el estudiante, qué devolvió la IA, qué corrigió y qué decisión sostuvo.</span>
    </div>
  `;
}

async function cargarAdminUsuarios() {
  const el = document.getElementById("admin-usuarios");
  if (!el || state.currentUser?.rol !== "admin") return;
  try {
    const usuarios = await apiFetch("/usuarios");
    el.innerHTML = `<table>
      <thead><tr><th>Usuario</th><th>Rol</th><th>Grupo</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody>${usuarios.map((u) => `
        <tr>
          <td>${escapeHtml(u.email)}</td>
          <td>${escapeHtml(u.rol)}</td>
          <td>${escapeHtml(u.grupo || "por defecto")}</td>
          <td>${u.activo ? "activo" : "<strong>desactivado</strong>"}</td>
          <td>${u.id === state.currentUser?.id ? "<span class=\"hint\">vos</span>" : `
            <button type="button" class="btn btn-secondary btn-mini" data-usuario-estado="${u.id}" data-activo="${u.activo ? "0" : "1"}">${u.activo ? "Desactivar" : "Activar"}</button>
            ${u.activo ? `<button type="button" class="btn btn-secondary btn-mini" data-usuario-sesiones="${u.id}">Cerrar sesiones</button>` : ""}`}
          </td>
        </tr>`).join("")}</tbody></table>`;
    el.querySelectorAll("[data-usuario-estado]").forEach((btn) => btn.addEventListener("click", async () => {
      const activar = btn.dataset.activo === "1";
      const email = btn.closest("tr").querySelector("td").textContent;
      if (!confirm(activar ? `¿Activar a ${email}?` : `¿Desactivar a ${email}? Pierde el acceso y se cierran sus sesiones. No se borra nada de lo que cargó.`)) return;
      try {
        await apiFetch(`/usuarios/${btn.dataset.usuarioEstado}`, { method: "PATCH", body: JSON.stringify({ activo: activar }) });
        toast(activar ? "Usuario activado." : "Usuario desactivado y sus sesiones cerradas.");
        cargarAdminUsuarios();
      } catch (e) { toast("No se pudo cambiar el estado: " + e.message, true); }
    }));
    el.querySelectorAll("[data-usuario-sesiones]").forEach((btn) => btn.addEventListener("click", async () => {
      const email = btn.closest("tr").querySelector("td").textContent;
      if (!confirm(`¿Cerrar todas las sesiones de ${email}? Va a tener que volver a ingresar.`)) return;
      try {
        await apiFetch(`/usuarios/${btn.dataset.usuarioSesiones}/cerrar-sesiones`, { method: "POST" });
        toast("Sesiones cerradas.");
      } catch (e) { toast("No se pudieron cerrar las sesiones: " + e.message, true); }
    }));
  } catch (e) {
    el.innerHTML = `<div class="empty-state">No se pudo cargar la lista de usuarios: ${escapeHtml(e.message)}</div>`;
  }
}

document.getElementById("form-cambio-password")?.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const actual = document.getElementById("password-actual");
  const nueva = document.getElementById("password-nueva");
  try {
    await apiFetch("/me/password", { method: "POST", body: JSON.stringify({ actual: actual.value, nueva: nueva.value }) });
    actual.value = ""; nueva.value = "";
    toast("Contraseña cambiada. Se cerraron tus otras sesiones.");
  } catch (e) { toast("No se pudo cambiar la contraseña: " + e.message, true); }
});

document.getElementById("btn-cerrar-sesiones")?.addEventListener("click", async () => {
  if (!confirm("¿Cerrar la sesión en todos tus dispositivos, incluido este?")) return;
  try {
    await apiFetch("/me/cerrar-sesiones", { method: "POST" });
  } finally {
    window.location.href = "/login";
  }
});

async function cargarActividad() {
  const resumen = document.getElementById("actividad-resumen");
  if (!resumen) return;
  if (state.currentUser?.rol !== "admin") {
    resumen.innerHTML = `<div class="empty-state">Esta vista está disponible solo para admin.</div>`;
    return;
  }
  resumen.innerHTML = `<div class="empty-state">Cargando actividad…</div>`;
  cargarAdminUsuarios();
  try {
    const [data, certificaciones] = await Promise.all([
      apiFetch("/actividad"),
      apiFetch("/certificaciones/metricas"),
    ]);
    renderActividad(data);
    renderMetricasCertificaciones(certificaciones);
  } catch (e) {
    resumen.innerHTML = `<div class="empty-state">No se pudo cargar actividad: ${escapeHtml(e.message)}</div>`;
  }
}

function actividadBoolBadge(ok, textoOk, textoNo) {
  return ok
    ? "<span class='badge badge-ok'>" + escapeHtml(textoOk) + "</span>"
    : "<span class='badge badge-neutral'>" + escapeHtml(textoNo) + "</span>";
}

function renderProgresoProyectosIA(data) {
  const el = document.getElementById('actividad-proyectos-ia');
  if (!el) return;
  const proyectos = data.progreso_proyectos_ia || [];
  if (!proyectos.length) {
    el.innerHTML = "<div class='empty-state'>Todavía no hay Gobernanza Incubadora iniciados por estudiantes.</div>";
    return;
  }
  el.innerHTML = "<table class='activity-project-table'>"
    + "<thead><tr><th>Participante</th><th>Etapa</th><th>Claridad</th><th>Chat IA</th><th>Docente</th><th>Entrega</th><th>Última actividad</th></tr></thead>"
    + "<tbody>"
    + proyectos.map((p) => {
      const nombre = p.nombre && p.nombre !== p.email ? p.nombre + ' · ' + p.email : p.email || 'Participante';
      const diag = p.diagnostico || {};
      const claridad = diag.necesita_segunda_vuelta
        ? "<span class='badge badge-warn'>segunda vuelta</span>"
        : "<span class='badge badge-ok'>" + escapeHtml(diag.estado_claridad || "encaminado") + "</span>";
      return "<tr>"
        + "<td>" + escapeHtml(nombre) + "</td>"
        + "<td><span class='activity-step-pill'>" + escapeHtml(p.etapa || 'Sin iniciar') + "</span></td>"
        + "<td>" + claridad + "</td>"
        + "<td>" + (p.mensajes_chat_ia || 0) + " / " + (p.mensajes_ia || 0) + "</td>"
        + "<td>" + (p.interacciones_docente || p.consultas_docente || 0) + "</td>"
        + "<td>" + actividadBoolBadge(Boolean(p.entrega), p.revisado ? 'revisado' : 'cargada', 'pendiente') + "</td>"
        + "<td>" + fmtFecha(p.ultimo_movimiento) + "</td>"
        + "</tr>";
    }).join('')
    + "</tbody></table>";
}

function renderProjectSkillChart(habilidades, options = {}) {
  const ejes = Array.isArray(habilidades?.ejes) ? habilidades.ejes : [];
  if (!ejes.length) return "";
  const compact = Boolean(options.compact);
  const todoCompleto = ejes.every((eje) => Number(eje.puntaje || 0) >= 5);
  const prioridad = !todoCompleto && Array.isArray(habilidades.prioridad) ? habilidades.prioridad.join(" y ") : "";
  return `
    <div class="project-skill-chart ${compact ? "compact" : ""}">
      <div class="project-skill-chart-head">
        <strong>${compact ? "Orientación automática" : "Orientación automática del proyecto"}</strong>
        <span>Índice orientativo ${escapeHtml(String(habilidades.promedio || "-"))}/5</span>
      </div>
      <p class="hint">Estimación por reglas de detección de términos. No es una calificación docente ni acredita la calidad del proyecto.</p>
      <div class="project-skill-bars">
        ${ejes.map((eje) => {
          const puntaje = Math.max(1, Math.min(5, Number(eje.puntaje || 1)));
          const faltantes = Array.isArray(eje.faltantes) ? eje.faltantes.slice(0, 2).join(", ") : "";
          return `
            <div class="project-skill-row ${puntaje >= 4 ? "strong" : puntaje >= 3 ? "medium" : "weak"}">
              <div class="project-skill-label">
                <strong>${escapeHtml(eje.nombre || eje.clave || "Eje")}</strong>
                <span>${puntaje}/5</span>
              </div>
              <div class="project-skill-track" aria-label="${escapeHtml((eje.nombre || "Eje") + ": " + puntaje + " de 5")}">
                <span style="width:${puntaje * 20}%"></span>
              </div>
              ${compact || !faltantes ? "" : `<small>Falta: ${escapeHtml(faltantes)}</small>`}
            </div>`;
        }).join("")}
      </div>
      ${compact ? "" : `<p>${prioridad ? "Aspectos que la herramienta sugiere revisar: " + escapeHtml(prioridad) + "." : "Orientación disponible para acompañar la revisión."}</p>`}
    </div>`;
}

function renderProyectoProgreso(data) {
  const el = document.getElementById('proyecto-progreso');
  if (!el) return;
  const mensajes = data.mensajes || [];
  const contexto = Boolean(data.titulo || data.organismo_area || data.situacion);
  const chatIA = mensajes.some((m) => m.remitente === 'participante');
  const entrega = Boolean(data.entrega_final) || data.estado === 'entregado' || data.estado === 'revisado';
  const revisado = data.estado === 'revisado' || Boolean((data.retro_docente || '').trim());
  const pasos = [
    ['Contexto', contexto],
    ['Chat IA', chatIA],
    ['Entrega', entrega],
    ['Revisión docente', revisado],
  ];
  const completados = pasos.filter((paso) => paso[1]).length;
  const paso = proximoPasoProyecto(data);
  // Una sola indicación a la vista: qué hacer ahora. El avance por etapas queda plegado.
  el.innerHTML = `<div class="proximo-paso">
      <div><span class="proximo-paso-kicker">Tu próximo paso</span><strong>${escapeHtml(paso.titulo)}</strong><p>${escapeHtml(paso.texto)}</p></div>
      <button type="button" class="btn btn-primary" data-proximo-paso="${escapeHtml(paso.destino)}"${paso.visto ? ` data-visto="${escapeHtml(paso.visto)}"` : ""}>${escapeHtml(paso.boton)}</button>
    </div>`
    + (entrega ? "" : "<p class='hint proximo-paso-tiempo'>Como referencia, en la cohorte de septiembre de 2026 la mitad de quienes entregaron trabajó entre 50 minutos y 2 horas y media en total, repartidas en 3 a 8 sesiones. No hace falta hacerlo de una vez: todo queda guardado.</p>")
    + "<details class='interior-details'><summary>Ver el avance por etapas (" + completados + " de " + pasos.length + ")</summary>"
    + "<div class='project-progress-head'><strong>Avance del recorrido</strong><span>" + completados + ' de ' + pasos.length + " etapas</span></div>"
    + "<div class='project-progress-steps'>"
    + pasos.map((paso, index) => "<div class='project-progress-step " + (paso[1] ? 'done' : '') + "'><span>" + (index + 1) + "</span><strong>" + escapeHtml(paso[0]) + "</strong></div>").join('')
    + "</div>"
    + "<p class='hint'>La consulta docente es opcional. Las orientaciones automáticas no cambian el estado de la entrega ni exigen rehacerla; cualquier corrección requerida debe surgir de la revisión docente.</p>"
    + "</details>"
    + '<details class="interior-details"><summary>Ver orientación automática del proyecto</summary>'
    + renderProjectSkillChart(data.diagnostico?.habilidades) + '</details>';
}

// Qué le conviene hacer ahora al participante, con un solo destino dentro de la Incubadora.
function proximoPasoProyecto(data = {}) {
  const mensajes = data.mensajes || [];
  const acompanamiento = data.acompanamiento || {};
  const contexto = Boolean(data.titulo || data.organismo_area || data.situacion);
  const conversa = mensajes.some((m) => m.remitente === "participante");
  const entregado = ["entregado", "revisado"].includes(data.estado);
  const canal = mensajes.filter((m) => ["consulta_docente", "docente"].includes(m.remitente));
  const ultimoCanal = canal[canal.length - 1];
  const ultimoPropio = [...mensajes].reverse().find((m) => m.remitente === "participante");
  // Una respuesta deja de ser «nueva» cuando se abre desde acá (se recuerda en este navegador).
  let vista = 0;
  try { vista = Number(localStorage.getItem(`docente-visto-${data.id}`) || 0); } catch { vista = 0; }
  const respuestaNueva = ultimoCanal?.remitente === "docente" && Number(ultimoCanal.id || 0) > vista
    && (!ultimoPropio || new Date(ultimoCanal.creado_en) > new Date(ultimoPropio.creado_en));
  if (respuestaNueva && data.estado !== "revisado") {
    return { titulo: "Tenés una respuesta del docente", texto: "Leela en el chat con el docente antes de seguir.", boton: "Leer la respuesta", destino: "proyecto-docente-chat", visto: `${data.id}:${ultimoCanal.id}` };
  }
  if (data.estado === "revisado" || (data.retro_docente || "").trim()) {
    return { titulo: "Recibiste la devolución docente", texto: respuestaNueva ? "Tu entrega está revisada y además tenés un mensaje en el chat con el docente. Mejorarla después es opcional." : "Tu entrega está revisada. Mejorarla después es opcional.", boton: "Ver mi devolución", destino: "proyecto-retro" };
  }
  if (entregado) {
    return { titulo: "Tu entrega está registrada", texto: "Queda esperar la devolución docente. Si querés, podés seguir mejorándola: es opcional.", boton: "Ver mi entrega", destino: "proyecto-entrega" };
  }
  if (!contexto) {
    return { titulo: "Contá tu caso", texto: "Escribí un título, tu área y la situación que querés mejorar, y guardalo.", boton: "Escribir mi caso", destino: "proyecto-titulo" };
  }
  if (!conversa) {
    return { titulo: "Conversá con el asistente", texto: "Contale el problema con tus palabras: te va a ayudar a precisarlo.", boton: "Ir al asistente", destino: "proyecto-mensaje" };
  }
  if (acompanamiento.listo_para_entregar || acompanamiento.listo_para_borrador) {
    return { titulo: "Armá el borrador y entregalo", texto: "Pedile al asistente «Generar borrador», revisalo, pegalo en la entrega final y marcala como entregada.", boton: "Ir a la entrega", destino: "proyecto-entrega" };
  }
  const falta = (acompanamiento.necesarios || [])[0]?.titulo;
  return { titulo: "Seguí con el asistente", texto: falta ? `Lo próximo a precisar: ${falta}.` : "Seguí precisando la propuesta con el asistente.", boton: "Ir al asistente", destino: "proyecto-mensaje" };
}

document.addEventListener("click", (event) => {
  const boton = event.target.closest("[data-proximo-paso]");
  if (!boton) return;
  const id = boton.dataset.proximoPaso;
  if (boton.dataset.visto) {
    const [proyecto, mensaje] = boton.dataset.visto.split(":");
    try { localStorage.setItem(`docente-visto-${proyecto}`, mensaje); } catch { /* sin almacenamiento: el aviso vuelve a aparecer */ }
    if (state.proyectoIA) setTimeout(() => renderProyectoProgreso(state.proyectoIA), 1200);
  }
  window.mostrarPasoIncubadoraPara?.(id);
  const destino = document.getElementById(id);
  if (!destino) return;
  destino.scrollIntoView({ behavior: "smooth", block: "center" });
  if (destino.matches("input, textarea")) destino.focus({ preventScroll: true });
});


function textoProyectoActual() {
  const campos = proyectoCamposActuales();
  return [campos.titulo, campos.organismo_area, campos.situacion, campos.entrega_final].join(" ").toLowerCase();
}

function tieneAlgunaPalabra(texto, palabras) {
  return palabras.some((palabra) => texto.includes(palabra));
}

function criteriosClaridadProyecto(data = {}) {
  const campos = proyectoCamposActuales();
  const texto = textoProyectoActual();
  return [
    {
      titulo: "Situación actual",
      ok: Boolean((campos.situacion || data.situacion || "").trim().length > 35),
      ayuda: "Qué pasa hoy y en qué proceso ocurre.",
    },
    {
      titulo: "A quién afecta",
      ok: tieneAlgunaPalabra(texto, ["usuario", "ciudadano", "área", "area", "equipo", "persona", "agente", "trabajador", "oficina", "programa"]),
      ayuda: "Personas, áreas o destinatarios alcanzados.",
    },
    {
      titulo: "Evidencia",
      ok: tieneAlgunaPalabra(texto, ["demora", "error", "reclamo", "duplic", "trazabilidad", "pendiente", "tiempo", "volumen", "riesgo", "criterio", "datos"]),
      ayuda: "Qué indicio muestra que el problema existe.",
    },
    {
      titulo: "Mejora esperada",
      ok: tieneAlgunaPalabra(texto, ["mejor", "reduc", "orden", "prioriz", "agiliz", "calidad", "seguimiento", "control", "claridad"]),
      ayuda: "Qué debería cambiar si el proyecto funciona.",
    },
    {
      titulo: "Indicador",
      ok: tieneAlgunaPalabra(texto, ["indicador", "medir", "tiempo", "cantidad", "porcentaje", "tasa", "plazo", "frecuencia", "antes", "después", "despues"]),
      ayuda: "Cómo comprobarías la mejora.",
    },
  ];
}

function renderProyectoClaridad(data = {}) {
  const el = document.getElementById("proyecto-claridad-checklist");
  if (!el) return;
  const checkpoint = data.checkpoint || data.ficha_implementacion?.checkpoint;
  const criterios = Array.isArray(checkpoint?.criterios) && checkpoint.criterios.length
    ? checkpoint.criterios
    : criteriosClaridadProyecto(data);
  const resumen = checkpoint
    ? `<div class="project-checkpoint-summary ${checkpoint.madurez || ""}">
        <strong>${escapeHtml(String(checkpoint.completos || 0))}/${escapeHtml(String(checkpoint.total || criterios.length))} temas marcados</strong>
        <span>Las coincidencias de texto orientan la revisión; no confirman que el criterio esté resuelto ni que los datos estén disponibles. Los cierres que decidís vos se identifican aparte.</span>
        <span>${escapeHtml(checkpoint.lectura || "Convertí la conversación en una propuesta defendible antes de entregar.")}</span>
      </div>`
    : "";
  const plantilla = checkpoint && !data.acompanamiento?.listo_para_entregar && (!data.acompanamiento || data.acompanamiento.necesarios?.length > 0) && Number(checkpoint.completos || 0) < Number(checkpoint.total || 10)
    ? `<div class="project-second-pass">
        <strong>Segunda vuelta sugerida</strong>
        <span>${escapeHtml(checkpoint.proximo_foco || "Completá la propuesta firme antes de entregar.")}</span>
        <button type="button" class="btn btn-secondary btn-mini" data-segunda-vuelta>Usar plantilla</button>
      </div>`
    : "";
  el.innerHTML = resumen + criterios.map((item) => `
    <div class="project-clarity-item ${item.cierre_manual ? "ready" : item.ok ? "detected" : "pending"}">
      <strong>${item.cierre_manual ? "Cerrado por vos: " : item.ok ? "Texto para revisar: " : item.pospuesto ? "Para después: " : item.esencial === false ? "Opcional: " : "Por precisar: "}${escapeHtml(item.titulo)}</strong>
      <span>${escapeHtml(item.ayuda || "")}</span>
      ${item.evidencia ? `<em>${escapeHtml(item.evidencia)}</em>` : ""}
      ${!item.clave ? "" : `<button type="button" class="btn btn-secondary btn-mini" data-criterio-clave="${escapeHtml(item.clave)}" data-criterio-accion="${item.pospuesto || item.cierre_manual ? "reabrir" : "cerrar"}" title="Se guarda al tocar; podés reabrirlo cuando quieras.">
        ${item.pospuesto ? "Retomar este punto" : item.cierre_manual ? "Reabrir este punto" : "Ya lo respondí"}
      </button>`}
      ${!item.cierre_manual && !item.pospuesto && item.clave ? `<button type="button" class="btn btn-secondary btn-mini" data-criterio-clave="${escapeHtml(item.clave)}" data-criterio-accion="posponer">Lo definiré después</button>` : ""}
    </div>
  `).join("") + plantilla;
  el.querySelector("[data-segunda-vuelta]")?.addEventListener("click", () => {
    const input = document.getElementById("proyecto-mensaje");
    if (!input) return;
    input.value = promptSegundaVueltaProyecto(data);
    input.focus();
  });
  el.querySelectorAll("[data-criterio-clave]").forEach((btn) => {
    btn.addEventListener("click", () => cambiarEstadoCriterio(btn.dataset.criterioClave, btn.dataset.criterioAccion));
  });
}

async function cambiarEstadoCriterio(clave, accion) {
  if (!clave || !accion) return;
  try {
    const data = await apiFetch(`/proyectos-ia/mio/criterios/${encodeURIComponent(clave)}/${encodeURIComponent(accion)}`, { method: "POST" });
    renderProyectoIA(data);
    toast(accion === "posponer" ? "Pendiente guardado para después; no se marcó como resuelto" : accion === "cerrar" ? "Punto cerrado por tu decisión" : "Punto reabierto para seguir trabajándolo");
  } catch (e) {
    toast("No se pudo actualizar el punto: " + e.message, true);
  }
}

function renderProyectoEscucha(data = {}) {
  const el = document.getElementById("proyecto-escucha-estado");
  if (!el) return;
  const acompanamiento = data.acompanamiento || {};
  const completos = Array.isArray(acompanamiento.completos) ? acompanamiento.completos : [];
  const necesarios = Array.isArray(acompanamiento.necesarios) ? acompanamiento.necesarios : [];
  el.className = "project-listening-status " + (acompanamiento.listo_para_borrador ? "ready" : "");
  el.innerHTML = `
    <strong>${acompanamiento.entrega_registrada ? "Entrega registrada" : acompanamiento.listo_para_entregar ? "Ya podés entregar para revisión docente" : acompanamiento.listo_para_borrador ? "Listo para armar el borrador" : "El asistente conserva tu avance"}</strong>
    <span>${escapeHtml(acompanamiento.mensaje_cierre || "Lo que completes no debería volver a preguntarse.")}</span>
    ${necesarios.length ? `<small><b>Falta para cerrar:</b> ${escapeHtml(necesarios.slice(0, 2).map((item) => item.titulo).join(", "))}.</small>` : ""}
    ${completos.length || acompanamiento.pospuestos?.length || acompanamiento.opcional?.length ? `<details class="plegable"><summary>Qué ya incorporó el asistente</summary>
    ${completos.length ? `<small><b>Ya incorporado:</b> ${escapeHtml(completos.join(", "))}.</small>` : ""}
    ${acompanamiento.pospuestos?.length ? `<small><b>Para después (siguen pendientes):</b> ${escapeHtml(acompanamiento.pospuestos.map(p => p.titulo).join(", "))}.</small>` : ""}
    ${acompanamiento.opcional?.length ? `<small><b>Opcional, no bloquea la entrega:</b> ${escapeHtml(acompanamiento.opcional.join(", "))}.</small>` : ""}
    </details>` : ""}`;
}

function usarControlProyecto(control) {
  const prompts = {
    entendido: "Decime brevemente qué entendiste de todo lo que ya aporté. Separá lo que quedó completo, lo necesario para cerrar y las mejoras opcionales. No agregues preguntas nuevas.",
    faltantes: "Mostrame solamente qué falta para cerrar mi propuesta. Diferenciá lo necesario de lo opcional y no vuelvas a preguntarme puntos ya respondidos.",
    siguiente: "Siguiente paso. Avancemos únicamente con el pendiente necesario de mayor importancia, sin volver sobre lo que ya quedó completo. Haceme como máximo una pregunta.",
    borrador: "Generá un borrador con toda la información que ya aporté. No inventes datos. Al final separá los faltantes realmente necesarios de las mejoras opcionales.",
    trabado: "HELP: siento que estoy trabado o dando vueltas. No me hagas más preguntas ahora. Resumí qué entendiste, qué ya quedó resuelto y ofreceme dos caminos concretos para continuar.",
  };
  const mensaje = prompts[control];
  if (mensaje) enviarMensajeProyectoIA(mensaje);
}


function promptSegundaVueltaProyecto(data = {}) {
  const campos = proyectoCamposActuales();
  const checkpoint = data.checkpoint || data.ficha_implementacion?.checkpoint || {};
  return [
    "Quiero hacer una segunda vuelta de mi proyecto de IA para convertirlo en una propuesta firme.",
    "",
    "No resuelvas el trabajo por mí. Ayudame a completar lo que falta y a dejarlo implementable.",
    "",
    "Mi proyecto actual:",
    "Título: " + (campos.titulo || "Sin definir"),
    "Área: " + (campos.organismo_area || "Sin definir"),
    "Situación: " + (campos.situacion || "Sin definir"),
    "Entrega/borrador: " + (campos.entrega_final || "Sin definir"),
    "",
    "Foco principal sugerido por el sistema: " + (checkpoint.proximo_foco || "Completar problema, datos, flujo, supervisión, riesgos, indicador y próximo paso."),
    "",
    "Devolveme una versión en 8 líneas: 1) problema; 2) usuarios/área; 3) evidencia; 4) datos; 5) flujo; 6) rol de IA; 7) supervisión/riesgos; 8) indicador y próximo paso implementable. Después marcá qué todavía debería decidir yo."
  ].join("\n");
}

function promptPruebaClaridadProyecto() {
  return [
    "Revisá la propuesta guardada completa y la conversación contra estos diez criterios: problema, usuarios, evidencia, datos, flujo, rol de IA, supervisión, riesgos, indicador y próximo paso.",
    "Para cada criterio indicá qué está sustentado en lo aportado y qué falta precisar, citando el contenido del proyecto. No inventes información ni des por cumplido un criterio por mencionarlo.",
    "El contador de la pantalla es orientativo y no equivale a esta revisión. Si no hay cambios suficientes, explicá por qué y señalá un próximo paso concreto.",
  ].join("\n");
}

async function probarClaridadProblema() {
  const button = document.getElementById("btn-probar-claridad");
  const status = document.getElementById("proyecto-prueba-estado");
  if (enviandoMensajeProyectoIA || button?.disabled) {
    if (status) status.textContent = "Esperá a que termine la respuesta actual para revisar la propuesta.";
    return;
  }
  if (button) button.disabled = true;
  const respuesta = document.getElementById("proyecto-prueba-respuesta");
  if (respuesta) { respuesta.hidden = true; respuesta.textContent = ""; }
  if (status) status.textContent = "Guardando la propuesta antes de revisar los diez criterios…";
  const antes = state.proyectoIA?.checkpoint?.completos;
  try {
    const entrega = document.getElementById("proyecto-entrega")?.value.trim() || "";
    if (largoTexto(entrega) > MAX_ENTREGA_CHARS) {
      if (status) status.textContent = "La propuesta supera el máximo de caracteres. Acortala antes de revisarla.";
      return;
    }
    const guardado = await guardarProyectoIA({entrega_final: entrega});
    if (!guardado) {
      if (status) status.textContent = "No se pudo guardar. La revisión no se inició; tu texto sigue disponible para reintentar.";
      return;
    }
    if (status) status.textContent = "Revisando los diez criterios con IA. La respuesta aparecerá aquí y quedará en la conversación…";
    const data = await enviarMensajeProyectoIA(promptPruebaClaridadProyecto());
    if (!data) {
      if (status) status.textContent = "No se pudo completar la revisión. La propuesta está guardada; podés volver a intentarlo.";
      return;
    }
    const ultimaRespuesta = [...(data.mensajes || [])].reverse().find(m => m.remitente === "ia");
    if (respuesta && ultimaRespuesta) {
      respuesta.textContent = "Respuesta de IA · requiere tu revisión\n\n" + ultimaRespuesta.contenido;
      respuesta.hidden = false;
    }
    const despues = data.checkpoint?.completos;
    if (status) status.textContent = "Revisión recibida. " +
      (antes != null && despues === antes ? `El contador sigue en ${despues}: leer la revisión no implica completar automáticamente los criterios. Revisá qué falta precisar.` : "Consultá lo que está sustentado y lo que falta precisar antes de entregar.");
  } finally {
    if (button) button.disabled = false;
  }
}


// ---------- detalle / análisis / decisión ----------


function renderJobEnProgreso(d) {
  const pendiente = document.getElementById("detalle-pendiente");
  const resultado = document.getElementById("detalle-resultado");
  const accionesDetalle = document.getElementById("detalle-actions");
  const panelProgreso = document.getElementById("analizar-progreso");
  const log = document.getElementById("progreso-log");
  const falta = document.getElementById("progreso-falta");
  const job = d.job;
  pendiente.style.display = "none";
  resultado.style.display = "none";
  panelProgreso.style.display = "block";
  falta.style.display = "none";
  const estado = job?.estado || "pendiente";
  renderTrazaJob(job, log, document.getElementById("progreso-etapas"));
  if (estado === "pendiente" || estado === "procesando") sondearJob(d.id, job?.id);
}

// Mientras se analiza se consulta sólo el estado del trabajo (unos KB): el informe completo, que en un libro de
// 172 cuadros pesa 8,5 MB, se pide una vez, al terminar. Un corte aislado no se avisa: se vuelve a consultar.
function sondearJob(informeId, jobId, fallas = 0) {
  if (state.detallePollTimer) clearTimeout(state.detallePollTimer);
  state.detallePollTimer = setTimeout(async () => {
    if (state.detalleId !== informeId) return;
    if (!jobId) {
      refrescarDetalle();
      return;
    }
    let job;
    try {
      job = await apiFetch(`/jobs/${jobId}`);
    } catch (e) {
      if (state.detalleId !== informeId) return;
      if (fallas < 2 && ![401, 403, 404].includes(e.status)) sondearJob(informeId, jobId, fallas + 1);
      else refrescarDetalle();
      return;
    }
    if (state.detalleId !== informeId) return;
    if (job.estado === "pendiente" || job.estado === "procesando") {
      renderTrazaJob(job, document.getElementById("progreso-log"), document.getElementById("progreso-etapas"));
      sondearJob(informeId, jobId);
    } else {
      refrescarDetalle();
    }
  }, 4500);
}


async function abrirDetalle(id, actualizarUrl = true) {
  state.detalleId = id;
  mostrarVista("detalle", actualizarUrl);
  await refrescarDetalle();
}

const MAX_REINTENTOS_DETALLE = 5; // con espera creciente: 4,5 s, 9 s, 13,5 s…

async function refrescarDetalle() {
  const requestedId = state.detalleId;
  if (!state.areas.length) await cargarAreas();
  let d;
  try {
    d = await apiFetch(`/informes/${requestedId}/detalle`);
    if (state.detalleId !== requestedId) return;
  } catch (e) {
    if (state.detalleId !== requestedId) return;
    if (state.detallePollTimer) clearTimeout(state.detallePollTimer);
    // Errores que no se arreglan reintentando: se avisa una vez y se deja de pedir el informe.
    const definitivo = {
      404: "Ese informe no existe o fue eliminado.",
      401: "Tu sesión venció: volvé a ingresar para ver el informe.",
      403: "No tenés permiso para ver ese informe.",
    }[e.status];
    if (definitivo) {
      state.detalleReintentos = 0;
      toast(definitivo, true);
      return;
    }
    state.detalleReintentos = (state.detalleReintentos || 0) + 1;
    if (state.detalleId && state.detalleReintentos <= MAX_REINTENTOS_DETALLE) {
      state.detallePollTimer = setTimeout(() => {
        if (state.detalleId === requestedId) refrescarDetalle();
      }, 4500 * state.detalleReintentos);
      // Un corte aislado se reintenta en silencio; si se repite, se avisa.
      if (state.detalleReintentos > 1) toast("No se pudo actualizar el informe. Reintentando…", true);
      return;
    }
    state.detalleReintentos = 0;
    toast("No se pudo cargar el informe: " + e.message + ". Probá recargar la página.", true);
    return;
  }
  state.detalleReintentos = 0;
  // Todo lo que puede citar texto literal del archivo cargado (columnas,
  // celdas, periodos) se escapa antes de que cualquier render lo toque.
  d.hallazgos = escapeDeep(d.hallazgos || []);
  d.coincidencias = escapeDeep(d.coincidencias || []);
  d.divergencias = escapeDeep(d.divergencias || []);
  d.hallazgos_singulares = escapeDeep(d.hallazgos_singulares || []);
  d.convergencia_multilente = escapeDeep(d.convergencia_multilente || []);
  if (d.devolucion) d.devolucion = escapeDeep(d.devolucion);
  if (d.saneamiento) d.saneamiento = escapeDeep(d.saneamiento);

  document.getElementById("detalle-titulo").textContent = `${areaNombre(d.area_id)} — ${d.periodo}`;
  const modos = globalThis.window?.RevisionModo;
  const nombreRevision = modos ? modos.nombre(d.saneamiento) : "";
  document.getElementById("detalle-subtitulo").textContent =
    `${nombreRevision ? nombreRevision + " · " : ""}Dominio: ${d.dominio} · ${contar(d.n_filas, "registro")} · Cargado ${fmtFecha(d.creado_en)}`;
  const modoProgreso = document.getElementById("progreso-modo-revision");
  if (modoProgreso && nombreRevision) modoProgreso.textContent = ` · ${nombreRevision.toUpperCase()}`;
  // Al final del informe de una revisión rápida terminada, el paso a la profunda con los mismos archivos.
  const pasarProfunda = modos && document.getElementById("pasar-profunda");
  if (pasarProfunda) {
    pasarProfunda.hidden = !(d.devolucion && modos.modo(d.saneamiento) === "rapida" && puedeOperarInformes());
    document.getElementById("pasar-profunda-aviso").textContent = "";
  }

  const avisoEl = document.getElementById("saneamiento-aviso");
  const excluidas = d.saneamiento?.columnas_excluidas || [];
  const avisos = [];
  const lecturaRevisada = d.saneamiento?.lectura_revisada;
  if (lecturaRevisada?.archivo_original) {
    // Ya escapado por escapeDeep: la tabla vino de la revisión de lectura de un PDF o imagen.
    avisos.push(`<div class="lectura-revisada"><strong>Tabla leída de ${lecturaRevisada.archivo_original} y revisada por una persona antes de analizar.</strong> ${lecturaRevisada.origen === "revision_ocr" ? "Se leyó con OCR local" : "Se leyó del texto del PDF"}, se comparó con el original y se confirmó en la revisión de lectura; se analizó el CSV «${lecturaRevisada.archivo_revisado || ""}».</div>`);
  }
  if (excluidas.length) {
    avisos.push(`<div><strong>Columnas excluidas al cargar.</strong> Se omitieron columnas que parecen identificar actores o documentos individuales: ${excluidas.join(", ")}. El sistema solo procesa información agregada.</div>`);
  }
  const contextoNormalizacion = descripcionNormalizacionSeries(d.saneamiento?.normalizacion_series || {});
  if (contextoNormalizacion) {
    avisos.push(`<div><strong>Lectura de series.</strong> ${contextoNormalizacion}</div>`);
  }
  const contextoPdf = descripcionPdf(d.saneamiento?.pdf || {});
  if (contextoPdf) {
    avisos.push(`<div><strong>Lectura de PDF.</strong> ${contextoPdf}</div>`);
  }
  const orientacionAnalisis = d.saneamiento?.orientacion_analisis || d.saneamiento?.opciones_tecnicas?.orientacion_analisis || "";
  if (orientacionAnalisis) {
    const controles = d.saneamiento?.controles_solicitados?.controles || [];
    const alcance = controles.length
      ? `Se activaron ${contar(controles.length, "control específico", "controles específicos")}, además del barrido abierto de las lentes.`
      : "Se usó para priorizar y explicar señales; no se reconoció un control determinístico específico para esa redacción.";
    avisos.push(`<div><strong>Pregunta declarada.</strong> ${orientacionAnalisis}<br><small>${alcance}</small></div>`);
  }
  const lectura = renderLecturaCuadro(d.saneamiento?.mapa_lectura);
  if (lectura) avisos.push(lectura);
  const previa = d.saneamiento?.interpretacion_previa;
  if (previa && modos?.modo(d.saneamiento) === "rapida") {
    // La rápida no tiene interpretación con IA que mostrar: sólo cuentas, con lo que declaraste al cargar.
    avisos.push(`<div><strong>Revisión rápida: sin interpretación con IA.</strong> Se hicieron las cuentas en ${contar((previa.cuadros || []).length, "cuadro")}; las reglas de presupuesto corren sólo si declaraste ese tipo de informe.</div>`);
  } else if (previa) {
    const cuadros = (previa.cuadros || []).map((u) => {
      const i = u.confirmada || u.propuesta || {};
      const habilitados = Object.entries(u.plan || {}).filter(([k, v]) => v && ["ajedrecista", "cronista", "orquesta", "radiologo", "rizoma", "matematico", "conciliador"].includes(k)).map(([k]) => k).join(", ");
      const c = u.cobertura || {};
      const banco = u.antecedentes_biblioteca || {};
      const roles = Object.entries(i.roles || {}).map(([col, rol]) => `<li>${escapeHtml(col)}: ${escapeHtml(String(rol).replaceAll("_", " "))}</li>`).join("");
      return `<li>${escapeHtml(u.archivo)} · ${escapeHtml(u.hoja || "Tabla")} · cuadro ${Number(u.bloque)}: ${escapeHtml(i.tipo)}; ${escapeHtml(i.institucion)}; régimen ${escapeHtml(i.regimen)}. ${habilitados ? "Selección: " + escapeHtml(habilitados) + ". Cada control conserva sus requisitos matemáticos." : "Controles semánticos pendientes."}<br><small>Origen: ${escapeHtml(String(u.origen || "propuesta pendiente").replaceAll("_", " "))}. Lectura ${escapeHtml(c.modo || "inicial")}: ${Number(c.filas_presentadas || 0)} de ${Number(c.filas_total || 0)} filas presentadas a los modelos; ${Number(c.notas_presentadas || 0)} de ${Number(c.notas_total || 0)} notas. ${c.parcial ? "Alcance parcial declarado." : ""} Antecedentes con cabeceras iguales: ${Number(banco.casos_similares) || 0}; orientación ${banco.orientacion_utilizada ? "presentada a los modelos" : "no aplicada"}.</small><details><summary>Significado de las columnas</summary><p>Organización temporal: ${escapeHtml(String(i.eje || "sin determinar").replaceAll("_", " "))}.</p><ul>${roles}</ul></details></li>`;
    }).join("");
    avisos.push(`<div><strong>Interpretación previa: ${previa.estado === "confirmada" ? "confirmada antes de controlar" : "pendiente de confirmación"}.</strong><ul>${cuadros}</ul></div>`);
  }
  if (avisos.length) {
    avisoEl.style.display = "block";
    // Con el resultado listo, cómo se leyó el archivo es detalle avanzado, salvo que el lector espere una respuesta.
    avisoEl.className = "aviso" + (d.devolucion && !avisos.join("").includes("data-lector-confirma") ? " solo-avanzado" : "");
    const pila = `<div class="aviso-stack">${avisos.join("")}</div>`;
    // Con el resultado listo, cómo se leyó el archivo queda plegado; si el lector espera una respuesta, abierto.
    avisoEl.innerHTML = d.devolucion
      ? `<details class="aviso-plegado"${pila.includes("data-lector-confirma") ? " open" : ""}><summary>Cómo se leyó el archivo</summary>${pila}</details>`
      : pila;
    avisoEl.querySelectorAll("[data-lector-confirma]").forEach((btn) => btn.addEventListener("click", confirmarLectura));
  } else {
    avisoEl.style.display = "none";
  }

  state.detalle = d;
  state.reporteSeleccion = new Set((d.hallazgos || []).map((h) => h.id));

  actualizarStepper(d);

  const pendiente = document.getElementById("detalle-pendiente");
  const resultado = document.getElementById("detalle-resultado");
  const accionesDetalle = document.getElementById("detalle-actions");

  if (state.detallePollTimer) {
    clearTimeout(state.detallePollTimer);
    state.detallePollTimer = null;
  }

  if (!d.devolucion && d.job && ["pendiente", "procesando", "error"].includes(d.job.estado)) {
    if (accionesDetalle) accionesDetalle.style.display = "none";
    renderJobEnProgreso(d);
    return;
  }


  document.getElementById("analizar-progreso").style.display = "none";
  if (!d.devolucion) {
    if (accionesDetalle) accionesDetalle.style.display = "none";
    pendiente.style.display = "block";
    resultado.style.display = "none";
    const btnAnalizarDetalle = document.getElementById("btn-analizar");
    const selectorModelos = document.querySelector("#detalle-pendiente .modelos-selector");
    const costoDetalle = document.getElementById("costo-total-detalle");
    let avisoLectura = document.getElementById("detalle-pendiente-lector");
    if (!avisoLectura) {
      avisoLectura = document.createElement("p");
      avisoLectura.id = "detalle-pendiente-lector";
      avisoLectura.className = "empty-state";
      pendiente.appendChild(avisoLectura);
    }
    const faltaInterpretacion = previa?.estado !== "confirmada";
    const datosEstructurados = d.saneamiento?.origen_interpretacion === "datos_estructurados";
    avisoLectura.textContent = esLector() ? "Tu rol es de solo lectura: podés ver informes ya procesados, pero no iniciar análisis." : datosEstructurados ? "Falta interpretar y confirmar qué contienen estos datos. El botón prepara ese paso antes de ejecutar controles." : "Falta confirmar qué contiene este informe. Volvé a la carga con los mismos archivos para preparar la interpretación. Los originales no se conservan en el servidor.";
    avisoLectura.style.display = esLector() || faltaInterpretacion ? "block" : "none";
    if (selectorModelos) selectorModelos.style.display = esLector() ? "none" : "";
    if (costoDetalle) costoDetalle.style.display = esLector() ? "none" : "";
    if (btnAnalizarDetalle) {
      btnAnalizarDetalle.style.display = esLector() || (faltaInterpretacion && !datosEstructurados) ? "none" : "";
      btnAnalizarDetalle.textContent = faltaInterpretacion ? "Interpretar y confirmar" : "Analizar informe";
    }
    return;
  }
  pendiente.style.display = "none";
  resultado.style.display = "block";
  if (accionesDetalle) accionesDetalle.style.display = "flex";
  const comprobante = document.getElementById("btn-descargar-comprobante");
  if (comprobante) comprobante.href = `/api/informes/${d.id}/informe-revision.pdf`;

  if (typeof renderResumenSimple === "function") renderResumenSimple(d);
  if (typeof renderCierreInforme === "function") renderCierreInforme(d);
  renderResumenTiles(d);
  renderLecturaEjecutiva(d);
  renderTrazabilidadAnalisis(d);
  renderGarantiasEjecucion(d);
  renderEvaluacionPiloto(d);
  renderCriterioRazonable(d);
  renderCoberturaLimites(d);
  renderInformeLentes(d.hallazgos, d.devolucion?.cobertura?.lentes || []);
  renderHallazgos(d.hallazgos, d.revision ? {...d.revision, informe_id:d.id} : null, d.devolucion?.cobertura?.comparacion_corridas);
  renderTriangulacion(d);
  renderPreguntaSugerida(d.hallazgos);
  renderComoLeerResultado();
  document.getElementById("devolucion-mensaje").textContent = String(d.devolucion.mensaje || "")
    .replaceAll("&#39;", "'").replaceAll("&quot;", '"').replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&amp;", "&");
  actualizarGuiaPrimeraVez();
}

const ETAPAS_ANALISIS = [
  ["carga", "Carga"],
  ["lectura", "Lectura"],
  ["controles", "Reglas"],
  ["exploracion", "Exploración"],
  ["contraste", "Contraste"],
  ["cobertura", "Alcance"],
  ["resultado", "Resultado"],
];

function renderTrazaJob(job, logEl, etapasEl) {
  if (!logEl) return;
  const eventos = Array.isArray(job?.progreso) ? job.progreso : [];
  const estadoJob = job?.estado || "pendiente";
  const estadoVivo = document.getElementById("progreso-estado-vivo");
  const conteoVivo = document.getElementById("progreso-conteo-vivo");
  const meter = document.getElementById("progreso-meter-bar");
  const etapasRegistradas = new Set(eventos.map((evento) => evento.etapa).filter(Boolean));
  const etapasCompletas = ETAPAS_ANALISIS.filter(([codigo]) => etapasRegistradas.has(codigo)).length;
  const ultimoEvento = eventos[eventos.length - 1] || null;
  const porcentaje = estadoJob === "finalizado" ? 100 : Math.min(94, Math.round((etapasCompletas / ETAPAS_ANALISIS.length) * 100));
  if (estadoVivo) {
    estadoVivo.textContent = estadoJob === "error"
      ? "El análisis necesita atención"
      : ultimoEvento?.mensaje || (estadoJob === "pendiente" ? "Esperando turno de análisis…" : "Preparando los controles…");
  }
  if (conteoVivo) {
    conteoVivo.textContent = estadoJob === "error"
      ? "La causa quedó registrada en la bitácora"
      : `${etapasCompletas} de ${ETAPAS_ANALISIS.length} etapas registradas · ${contar(eventos.length, "evento verificable", "eventos verificables")}`;
  }
  if (meter) meter.style.width = `${porcentaje}%`;
  if (!eventos.length) {
    const mensaje = estadoJob === "error"
      ? `El análisis terminó con error: ${job?.error || "sin detalle"}`
      : estadoJob === "procesando"
        ? "El análisis está en curso. Esperando el próximo evento verificable."
        : "El informe está en cola y conserva su lugar aunque cierres esta pantalla.";
    const clase = estadoJob === "error" ? "error" : "vacio";
    logEl.innerHTML = `<li class="${clase}"><span class="progreso-icono">${estadoJob === "error" ? "✕" : "○"}</span><span>${escapeHtml(mensaje)}</span></li>`;
  } else {
    logEl.innerHTML = eventos.map((evento) => {
      const clase = evento.estado === "error" ? "error" : evento.estado === "advertencia" ? "advertencia" : evento.estado === "informativo" ? "informativo" : "ok";
      const icono = evento.estado === "error" ? "✕" : evento.estado === "advertencia" ? "!" : evento.estado === "informativo" ? "–" : "✓";
      const detalle = evento.detalle ? `<small class="progreso-detalle">${escapeHtml(evento.detalle)}</small>` : "";
      return `<li class="${clase}"><span class="progreso-icono">${icono}</span><span><strong>${escapeHtml(evento.mensaje || evento.etapa || "Paso registrado")}</strong>${detalle}</span></li>`;
    }).join("");
  }
  if (etapasEl) {
    const completadas = new Set(eventos.map((evento) => evento.etapa));
    const ultima = eventos.length ? eventos[eventos.length - 1].etapa : null;
    etapasEl.innerHTML = ETAPAS_ANALISIS.map(([codigo, nombre]) => {
      const clase = codigo === ultima && estadoJob !== "finalizado" ? "activa" : completadas.has(codigo) ? "completa" : "pendiente";
      return `<span class="${clase}">${escapeHtml(nombre)}</span>`;
    }).join("");
  }
}

function renderTrazabilidadAnalisis(d) {
  const el = document.getElementById("trazabilidad-analisis");
  const versionEl = document.getElementById("trace-version");
  if (!el) return;
  const job = d.job || {};
  const eventos = Array.isArray(job.progreso) ? job.progreso : [];
  if (versionEl) versionEl.textContent = job.version_analisis ? `Versión ${job.version_analisis}` : "Análisis histórico";
  if (!eventos.length) {
    el.innerHTML = `<p class="hint">Este informe fue procesado antes de incorporar la bitácora persistente. La evidencia por hallazgo, la cobertura y la decisión humana siguen disponibles en los bloques siguientes.</p>`;
    return;
  }
  const metricas = job.metricas || {};
  el.innerHTML = `
    <div class="trace-metrics">
      <span><strong>${metricas.duracion_segundos ?? "—"}</strong><small>segundos</small></span>
      <span><strong>${metricas.lentes_ejecutadas ?? "—"}</strong><small>miradas ejecutadas</small></span>
      <span><strong>${metricas.modelos_respondieron ?? "—"}</strong><small>modelos que respondieron</small></span>
      <span><strong>${metricas.hallazgos ?? d.hallazgos.length}</strong><small>hallazgos</small></span>
    </div>
    <div class="trace-timeline">
      ${eventos.map((evento) => `
        <article class="trace-event trace-${escapeHtml(evento.estado || "completado")}">
          <span>${escapeHtml(String(evento.paso ?? ""))}</span>
          <div><strong>${escapeHtml(evento.mensaje || evento.etapa || "Paso registrado")}</strong>${evento.detalle ? `<p>${escapeHtml(evento.detalle)}</p>` : ""}</div>
        </article>`).join("")}
    </div>
    <p class="trace-note">Esta secuencia informa acciones y resultados verificables. No expone razonamientos internos ni reemplaza la revisión humana.</p>`;
}

// Lo no leído o no controlado va primero: la misma línea que encabeza el informe descargable.
function renderRegistroRevision(d) {
  const contenedor = document.getElementById("detalle-completo-cuerpo") || document.getElementById("detalle-resultado");
  if (!contenedor) return;
  let el = document.getElementById("registro-revision");
  if (!el) {
    el = document.createElement("div");
    el.id = "registro-revision";
    contenedor.insertBefore(el, contenedor.firstChild);
  }
  const reg = d.devolucion?.cobertura?.registro_revision;
  if (!reg || !reg.primera_linea) {
    el.innerHTML = "";
    el.style.display = "none";
    return;
  }
  el.style.display = "";
  const clase = reg.estado === "completo" ? "badge-ok" : reg.estado === "insuficiente" ? "badge-critico" : "badge-media";
  const pendientes = Array.isArray(reg.pendientes) ? reg.pendientes : [];
  el.innerHTML = `<div class="card registro-revision"><p><span class="badge ${clase}">${escapeHtml(String(reg.estado || "").toUpperCase())}</span> <strong>${escapeHtml(reg.primera_linea)}</strong></p>
    ${pendientes.length ? `<details><summary>Qué no se leyó o no se controló (${pendientes.length})</summary><ul>${pendientes.map(p => `<li>${escapeHtml(p.archivo ? p.archivo + ": " : "")}${escapeHtml(p.donde || "")} — ${escapeHtml(p.motivo || "")}</li>`).join("")}</ul></details>` : ""}
    ${Array.isArray(reg.avisos) && reg.avisos.length ? `<details><summary>Avisos de lectura (${reg.avisos.length})</summary><ul>${reg.avisos.map(a => `<li>${escapeHtml(a)}</li>`).join("")}</ul></details>` : ""}
    ${reg.cruces?.texto ? `<p>${escapeHtml(reg.cruces.texto)}</p>` : ""}
    ${reg.periodo?.texto ? `<p>${escapeHtml(reg.periodo.texto)}</p>` : ""}</div>`;
}

function textoEjes(x) {
  if (!x) return "";
  const imp = x.impacto || {};
  const impacto = imp.nivel === "no_determinado" ? `no determinado (${imp.detalle || ""})` : imp.nivel === "no_aplica" ? `no aplica (${imp.detalle || ""})` : `${imp.nivel} (${imp.detalle || ""})`;
  return `Rareza: ${x.rareza?.nivel || "-"} (${x.rareza?.detalle || ""}). Impacto: ${impacto}. Evidencia: ${(x.evidencia?.nivel || "-").replaceAll("_", " ")} (${x.evidencia?.detalle || ""}).${x.motivo_tope ? " Prioridad limitada a media: " + x.motivo_tope + "." : ""}`;
}

function renderGarantiasEjecucion(d) {
  const el = document.getElementById("garantias-ejecucion");
  if (!el) return;
  const cobertura = d.devolucion?.cobertura || {};
  const m = cobertura.manifiesto;
  const faltantes = (cobertura.lentes || []).filter(c => ["no_evaluable", "no_aplicable"].includes(c.estado));
  el.innerHTML = `<details class="card"><summary>Alcance de esta revisión y registro técnico</summary>
    ${m ? `<p>Aplicación ${escapeHtml(m.version_aplicacion)} · ejecución ${escapeHtml(m.fecha)}</p>` : '<p>Este informe es anterior al manifiesto ampliado. No se reconstruyeron datos de origen que no habían sido registrados.</p>'}
    <ul>${faltantes.map(c => `<li><strong>${escapeHtml(c.lente)}: ${escapeHtml(c.estado.replaceAll("_", " "))}.</strong> ${escapeHtml(c.motivo || "")}</li>`).join("")}</ul>
    ${cobertura.registro_revision?.cruces?.texto ? `<p>${escapeHtml(cobertura.registro_revision.cruces.texto)}</p>` : cobertura.control_interdocumental?.estado === "no_evaluable" ? `<p>${escapeHtml(cobertura.control_interdocumental.motivo)}. Pendiente: ${escapeHtml((cobertura.control_interdocumental.condiciones_no_verificadas || ["Ver detalle por cuadro"]).join(", "))}.</p>` : ""}
    <p><a href="/api/informes/${d.id}/manifiesto" target="_blank" rel="noopener">Ver manifiesto técnico y proveniencia</a></p></details>`;
}

function renderEvaluacionPiloto(d) {
  const card = document.getElementById("evaluacion-piloto-card");
  const estado = document.getElementById("evaluacion-piloto-estado");
  if (!card || !estado) return;
  card.style.display = puedeOperarInformes() ? "" : "none";
  if (!puedeOperarInformes()) return;
  const evaluacion = d.evaluacion_piloto || null;
  document.querySelectorAll('input[name="resultado_piloto"]').forEach((input) => {
    input.checked = !!evaluacion && input.value === evaluacion.resultado;
  });
  const comentario = document.getElementById("comentario-evaluacion-piloto");
  if (comentario) comentario.value = evaluacion?.comentario || "";
  estado.textContent = evaluacion
    ? "Última evaluación guardada. Podés actualizarla; se conservará la trazabilidad de cada registro."
    : "Todavía no hay una evaluación humana de este resultado.";
}

document.getElementById("form-evaluacion-piloto")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const seleccionado = document.querySelector('input[name="resultado_piloto"]:checked');
  if (!seleccionado || !state.detalleId) return;
  const boton = event.currentTarget.querySelector('button[type="submit"]');
  boton.disabled = true;
  try {
    await apiFetch(`/informes/${state.detalleId}/evaluacion-piloto`, {
      method: "POST",
      body: JSON.stringify({
        resultado: seleccionado.value,
        comentario: document.getElementById("comentario-evaluacion-piloto")?.value.trim() || "",
      }),
    });
    toast("Evaluación del piloto guardada");
    await refrescarDetalle();
  } catch (error) {
    toast("No se pudo guardar la evaluación: " + error.message, true);
  } finally {
    boton.disabled = false;
  }
});

const GUIA_LS_KEY = "gobernanza_guia_informe_vista";

function actualizarGuiaPrimeraVez() {
  const guia = document.getElementById("guia-primera-vez");
  if (!guia) return;
  guia.style.display = localStorage.getItem(GUIA_LS_KEY) ? "none" : "block";
}

document.getElementById("btn-cerrar-guia")?.addEventListener("click", () => {
  document.getElementById("guia-primera-vez").style.display = "none";
});
document.getElementById("btn-entendido-guia")?.addEventListener("click", () => {
  localStorage.setItem(GUIA_LS_KEY, "1");
  document.getElementById("guia-primera-vez").style.display = "none";
});
document.getElementById("btn-abrir-guia")?.addEventListener("click", () => {
  document.getElementById("guia-primera-vez").style.display = "block";
});

function actualizarStepper(d) {
  const pasos = {
    cargado: true,
    analizado: !!d.devolucion,
    resultado: !!d.devolucion,
  };
  const orden = ["cargado", "analizado", "resultado"];
  let ultimoActivo = null;
  orden.forEach((p) => { if (pasos[p]) ultimoActivo = p; });
  // Con el resultado listo, los pasos ya no dicen nada nuevo.
  const stepper = document.querySelector(".stepper");
  if (stepper) stepper.style.display = d.devolucion ? "none" : "";
  document.querySelectorAll(".stepper .step").forEach((el) => {
    el.classList.remove("done", "active");
    if (pasos[el.dataset.step] && el.dataset.step !== ultimoActivo) el.classList.add("done");
    else if (el.dataset.step === ultimoActivo) el.classList.add("active");
  });
}

function porcentajeLectura(lectura) {
  const total = Number(lectura?.series_aparentes || 0);
  const leidas = Number(lectura?.series_leidas || 0);
  if (total <= 0) return null;
  return total > 0 && leidas >= total ? "100" : Math.min(99.9, total > 0 ? 100 * leidas / total : 0).toFixed(1).replace(/\.0$/, "");
}

// Lo primero que se ve: cuántos casos hay y los principales, con su celda y su cuenta.
// Todo lo demás (cifras, lectura ejecutiva, lentes, cobertura, descargas) queda plegado.
function renderResumenSimple(d) {
  const el = document.getElementById("resumen-simple");
  if (!el) return;
  const casos = d.revision?.casos
    ? d.revision.casos.map((c) => ({ prioridad: c.prioridad, h: c.primary_finding || {} }))
    : [...(d.hallazgos || [])]
      .filter((h) => (h.evidencia || {}).naturaleza !== "contexto")
      .sort((a, b) => ((b.evidencia || {}).puntaje_prioridad || 0) - ((a.evidencia || {}).puntaje_prioridad || 0))
      .map((h) => ({ prioridad: h.severidad, h }));
  const total = d.revision?.casos_revision ?? casos.length;
  const alta = d.revision?.prioridades?.alta ?? casos.filter((c) => c.prioridad === "alta").length;
  const estado = d.devolucion?.cobertura?.registro_revision?.estado;
  const titulo = total
    ? `${contar(total, "caso")} para revisar${alta ? ` · ${alta} de prioridad alta` : ""}`
    : "No aparecieron casos con estos controles";
  const aviso = estado && estado !== "completo"
    ? `<p class="resumen-simple-aviso">Lectura ${escapeHtml(estado)}: hay partes del archivo sin leer o sin controlar. El detalle dice cuáles.</p>` : "";
  // La respuesta y el permiso viajan con cada señal del detalle; el caso trae una copia de su señal principal.
  const porId = new Map((d.hallazgos || []).map((x) => [Number(x.id), x]));
  const items = casos.slice(0, 5).map(({ prioridad, h }) => {
    const e = h.evidencia || {};
    const donde = e.hoja && e.celda ? `${e.hoja}!${e.celda}` : (e.hoja || e.indicador || nombreLenteLegible(h.lente));
    return `<li><strong>${escapeHtmlUnaVez(donde)}</strong>${prioridad === "alta" ? ' <span class="badge badge-alta">alta</span>' : ""}
      <span class="resumen-simple-texto">${escapeHtmlUnaVez(h.resumen_llano || h.descripcion_es || h.descripcion || "Sin descripción registrada")}</span>${botonOrigenHallazgo(h)}${renderRespuestaCaso(porId.get(Number(h.id)))}</li>`;
  }).join("");
  const quedan = total - Math.min(5, casos.length);
  el.innerHTML = `<h3>${escapeHtml(titulo)}</h3>${aviso}
    ${items ? `<ol>${items}</ol>` : "<p>Esto no garantiza que no haya errores: sólo que estos controles no encontraron nada.</p>"}
    ${quedan > 0 ? `<p class="resumen-simple-pie"><span class="solo-avanzado">Y ${contar(quedan, "caso")} más en «Ver todo el detalle».</span>`
      + `<span class="solo-basico">Y ${contar(quedan, "caso")} más: están en el informe de revisión (PDF) y en el modo avanzado.</span></p>` : ""}`;
  el.querySelectorAll?.("[data-respuesta]").forEach((b) => b.addEventListener("click", responderSenal));
  const completo = document.getElementById("detalle-completo");
  if (completo && el.dataset.informe !== String(d.id)) completo.open = false;
  el.dataset.informe = String(d.id);
}

// «¿Qué resultó ser?» en cada caso principal, a la vista (antes sólo estaba en el anexo plegado). Mismo bloque y
// mismo envío que en el anexo (responderSenal); el comentario vigente viaja en data-comentario para no perderlo.
const RESPUESTAS_CASO = [["error_real", "Error real"], ["dato_correcto", "Dato correcto"], ["no_se", "Todavía no sé"]];
function renderRespuestaCaso(h) {
  if (!h || !Number.isSafeInteger(Number(h.id))) return "";
  const r = h.respuesta;
  const actual = r ? `<p class="respuesta-actual"><strong>Respuesta registrada:</strong> ${escapeHtmlUnaVez(r.texto)}</p>` : "";
  if (!h.puede_responder) return actual ? `<div class="respuesta-senal respuesta-senal-caso">${actual}</div>` : "";
  return `<div class="respuesta-senal respuesta-senal-caso" data-hallazgo="${Number(h.id)}" data-comentario="${escapeHtmlUnaVez(r?.comentario || "")}">
      <p class="respuesta-pregunta">¿Qué resultó ser?</p>
      <span class="respuesta-botones">${RESPUESTAS_CASO.map(([valor, texto]) => `<button type="button" class="btn btn-secondary btn-mini btn-respuesta${r?.respuesta === valor ? " activa" : ""}" data-respuesta="${valor}">${texto}</button>`).join(" · ")}</span>
      ${actual}
      <small>Sirve para medir la herramienta, no a vos.</small>
    </div>`;
}

// Pregunta de cierre, al final del informe: una vez por informe (vale la última respuesta).
let cierreInformeActual = null;
function textoCierre(r) {
  if (!r) return "";
  const n = r.errores_no_senalados;
  return `Respuesta registrada: corregiste algo: ${escapeHtmlUnaVez(r.texto)}`
    + (n != null ? ` · errores que no se señalaron: ${Number(n)}` : "")
    + (r.registrado_en ? ` (${escapeHtmlUnaVez(String(r.registrado_en).slice(0, 10))})` : "");
}
function renderCierreInforme(d) {
  const el = document.getElementById("cierre-informe");
  if (!el) return;
  const c = d.cierre_informe;
  cierreInformeActual = c ? { ...c, informe_id: d.id } : null;
  if (!c || (!c.puede_responder && !c.respuesta)) { el.hidden = true; el.innerHTML = ""; return; }
  el.hidden = false;
  const r = c.respuesta;
  const estado = r ? textoCierre(r) : c.pendiente ? "Pendiente: todavía no respondiste." : "";
  const prueba = c.es_prueba ? '<p class="hint">Marcado como prueba: no cuenta para las mediciones.</p>' : "";
  if (!c.puede_responder) {
    el.innerHTML = `<h3>Antes de entregarlo</h3>${prueba}<p class="cierre-estado">${estado}</p>`;
    return;
  }
  el.innerHTML = `<h3>Antes de entregarlo</h3>${prueba}
    <p class="respuesta-pregunta">¿Corregiste algo del informe antes de entregarlo?</p>
    <span class="respuesta-botones" role="group" aria-label="¿Corregiste algo del informe?">${[["si", "Sí"], ["no", "No"], ["todavia_no", "Todavía no"]].map(([valor, texto]) => `<button type="button" class="btn btn-secondary btn-mini btn-respuesta${r?.corrigio === valor ? " activa" : ""}" data-cierre="${valor}" aria-pressed="${r?.corrigio === valor}">${texto}</button>`).join(" ")}</span>
    <label>¿Encontraste errores que la herramienta no señaló? Cantidad <input type="number" min="0" max="1000" step="1" id="cierre-errores" value="${r?.errores_no_senalados != null ? Number(r.errores_no_senalados) : ""}" /></label>
    <div class="btn-row"><button type="button" class="btn btn-primary btn-mini" id="btn-guardar-cierre">Guardar respuesta</button></div>
    <p class="cierre-estado" role="status">${estado}</p>
    <small>Sirve para medir la herramienta, no a vos. Podés cambiar la respuesta: vale la última.</small>`;
  el.querySelectorAll?.("[data-cierre]").forEach((b) => b.addEventListener("click", () => {
    el.querySelectorAll("[data-cierre]").forEach((x) => { x.classList.toggle("activa", x === b); x.setAttribute("aria-pressed", String(x === b)); });
  }));
  el.querySelector("#btn-guardar-cierre")?.addEventListener("click", guardarCierreInforme);
}

function renderResumenTiles(d) {
  if (typeof renderRegistroRevision === "function") renderRegistroRevision(d);
  const porSeveridad = { alta: 0, media: 0, baja: 0 };
  d.hallazgos.forEach((h) => { porSeveridad[h.severidad] = (porSeveridad[h.severidad] || 0) + 1; });
  const tiles = [
    { num: d.revision?.casos_revision ?? d.hallazgos.length, lbl: d.revision ? "Casos de revisión" : "Señales encontradas" },
    { num: d.revision?.prioridades?.alta ?? porSeveridad.alta, lbl: "Casos de prioridad alta" },
  ];
  const lectura = d.devolucion?.cobertura?.excel?.lectura;
  if (lectura && lectura.series_aparentes) {
    tiles.push({
      num: porcentajeLectura(lectura) + " %",
      lbl: "Series temporales reconocidas",
      nota: `${lectura.series_leidas} de ${lectura.series_aparentes} series`,
      estado: lectura.series_leidas < lectura.series_aparentes ? "parcial" : lectura.estado,
    });
  } else {
    // Sin series por período no hay porcentaje, pero sí se sabe qué entró: decirlo es mejor que
    // no decir nada, y evita que el lector lea el silencio como "no se leyó el archivo".
    const hojas = d.devolucion?.cobertura?.excel?.hojas || [];
    const filas = hojas.reduce((suma, h) => suma + Number(h.filas_datos || 0), 0);
    if (hojas.length && filas) {
      const conDatos = hojas.filter((h) => Number(h.filas_datos || 0) > 0).length;
      tiles.push({
        num: filas,
        lbl: "Filas de datos incorporadas",
        nota: `${conDatos} de ${contar(hojas.length, "hoja")} con datos`,
        estado: conDatos < hojas.length ? "parcial" : "completa",
      });
    }
  }
  document.getElementById("resumen-tiles").innerHTML = tiles
    .map((t) => `<div class="summary-tile${t.estado && t.estado !== "completa" ? " parcial" : ""}"><div class="num">${escapeHtml(String(t.num))}</div><div class="lbl">${escapeHtml(t.lbl)}</div>${t.nota ? `<div class="nota">${escapeHtml(t.nota)}</div>` : ""}</div>`)
    .join("");
  renderPrincipalesHallazgos(d, lectura);
}

function botonOrigenHallazgo(h) {
  const id = Number(h.id);
  return Number.isSafeInteger(id) && id > 0
    ? `<button type="button" class="btn btn-secondary btn-mini" data-origen-hallazgo="${id}">Ver origen y evidencia</button>` : '';
}

// «Qué pasó»: frase llana armada por el servidor con plantillas (services/reportes/lenguaje_llano.py).
function quePaso(h) {
  return h && h.resumen_llano ? `<p class="que-paso"><strong>Qué pasó:</strong> ${escapeHtmlUnaVez(h.resumen_llano)}</p>` : "";
}

function renderPrincipalesHallazgos(d, lectura) {
  const el = document.getElementById("resumen-principales");
  if (!el) return;
  const top = [...d.hallazgos]
    .filter((h) => (h.evidencia || {}).naturaleza !== "contexto")
    .sort((a, b) => ((b.evidencia || {}).puntaje_prioridad || 0) - ((a.evidencia || {}).puntaje_prioridad || 0))
    .slice(0, 5);
  const bloque = d.devolucion?.cobertura?.controles_solicitados || d.saneamiento?.controles_solicitados || {};
  const controles = bloque.controles || [];
  const orientacion = d.saneamiento?.orientacion_analisis || d.saneamiento?.opciones_tecnicas?.orientacion_analisis;
  const incompleto = controles.some(c => c.estado === "no_evaluable" || c.cobertura_parcial) || bloque.estado === "parcialmente_evaluado" || bloque.estado === "no_evaluable";
  const estadoConsulta = incompleto ? "La consulta quedó sin evaluar o se evaluó parcialmente. No equivale a un control superado."
    : controles.length ? "Los controles específicos solicitados fueron ejecutados; sus resultados no certifican el informe."
    : orientacion ? "No hay una evaluación específica registrada para la consulta. Las señales generales no acreditan que se haya respondido."
    : "Exploración abierta, sin una consulta específica declarada.";
  const consulta = `<h3>Resultado de la consulta</h3><p>${escapeHtml(estadoConsulta)}</p>${controles.map(c => `<p><strong>${escapeHtmlUnaVez(c.nombre || "Control solicitado")}:</strong> ${escapeHtmlUnaVez(c.resultado || "Sin resultado registrado")}</p>`).join("")}`;
  const porcentaje = lectura ? porcentajeLectura(lectura) : null;
  const aviso = !lectura ? "" : porcentaje === null
    ? `<p class="aviso-lectura">No se pudo calcular la cobertura de series temporales. Esto no significa que el archivo no se haya leído: consultá el alcance de cada control y de la exploración IA.</p>`
    : `<p class="aviso-lectura">Se reconoció el ${porcentaje} % de las series temporales identificadas. Este porcentaje no mide la lectura total del archivo.${lectura.series_leidas < lectura.series_aparentes ? " Los controles temporales se limitan a las series reconocidas; otros controles pueden tener un alcance diferente." : ""}</p>`;
  el.innerHTML = `${consulta}<h3>Principales revisiones sugeridas</h3>${aviso}${!top.length ? "<p>No se seleccionaron señales para este resumen. Revisá la cobertura antes de interpretar el resultado.</p>" : ""}
    <ol class="resumen-principales">${top.map((h) => {
      const ev = h.evidencia || {};
      const donde = ev.hoja && ev.celda ? `${ev.hoja}!${ev.celda}` : (ev.indicador || "");
      return `<li><strong>${escapeHtmlUnaVez(donde)}</strong> ${escapeHtmlUnaVez(h.resumen_llano || h.descripcion_es || h.descripcion || "Sin descripción registrada")} ${botonOrigenHallazgo(h)}</li>`;
    }).join("")}</ol>
    ${d.hallazgos.length > top.length ? `<p class="hint">Y ${d.hallazgos.length - top.length} ${d.hallazgos.length - top.length === 1 ? "señal" : "señales"} más en el detalle.</p>` : ""}`;
}

function tituloAlcanceSeries(valor) {
  return {
    auto: "automático",
    nivel_general: "solo nivel general",
    principales: "principales aperturas",
    todas: "todas las aperturas",
  }[valor] || valor || "no especificado";
}

function descripcionNormalizacionSeries(meta) {
  if (!meta || meta.formato !== "largo") return "";
  const periodo = meta.columna_periodo || "período";
  const dimension = meta.columna_dimension || "apertura";
  const valores = (meta.columnas_valor || []).slice(0, 4).join(" / ") || "valor";
  const solicitado = tituloAlcanceSeries(meta.alcance_solicitado || "auto");
  const aplicado = tituloAlcanceSeries(meta.alcance_aplicado || meta.alcance_solicitado || "todas");
  const filas = meta.filas_entrada
    ? `${meta.filas_analizadas || meta.filas_entrada}/${meta.filas_entrada} filas`
    : `${meta.filas_analizadas || "-"} filas`;
  const aperturas = meta.series_detectadas
    ? `${meta.series_analizadas || meta.series_detectadas}/${meta.series_detectadas} aperturas`
    : `${meta.series_analizadas || "-"} aperturas`;
  const cambio = solicitado !== aplicado ? `; solicitado ${solicitado}` : "";
  return `Se detectó tabla larga (${periodo} / ${dimension} / ${valores}). Alcance aplicado: ${aplicado}${cambio}; ${filas}; ${aperturas}.`;
}


function descripcionPdf(meta) {
  if (!meta || !meta.cantidad_archivos) return "";
  const archivos = meta.cantidad_archivos === 1 ? "1 PDF" : `${meta.cantidad_archivos} PDFs`;
  const paginas = meta.paginas_documento
    ? `${meta.paginas_analizadas || "-"} de ${contar(meta.paginas_documento, "página")}`
    : `${contar(meta.paginas_analizadas, "página")}`;
  const modo = (meta.modos_extraccion || []).includes("tabla") ? "tablas" : "texto por página";
  const recorte = meta.truncado_por_paginas
    ? " Se aplicó recorte por límite de páginas; no es lectura completa del documento."
    : "";
  return `${archivos}: se leyó ${paginas}, con límite ${meta.limite_paginas_pdf || "-"} y extracción de ${modo}.${recorte}`;
}

function hayHallazgoNivelGeneral(d) {
  return (d.hallazgos || []).some((h) => {
    const e = h.evidencia || {};
    const textos = [e.serie, ...(Array.isArray(e.series) ? e.series : []), ...(Array.isArray(e.series_compactas) ? e.series_compactas : [])]
      .filter(Boolean)
      .map((x) => String(x).toLowerCase().replace(/\s+/g, "_"));
    return textos.some((x) => x.includes("nivel_general") || x.includes("total_general") || x.startsWith("ng_"));
  });
}

function contextoSeries(d) {
  const meta = d.saneamiento?.normalizacion_series || {};
  if (meta.formato !== "largo") return "";
  const partes = [descripcionNormalizacionSeries(meta)];
  if (meta.alcance_aplicado !== "nivel_general" && !hayHallazgoNivelGeneral(d)) {
    partes.push("Los hallazgos visibles corresponden a aperturas; no implican por sí solos un problema del nivel general.");
  }
  return partes.filter(Boolean).join(" ");
}

function renderLecturaEjecutiva(d) {
  const el = document.getElementById("lectura-ejecutiva");
  const porSeveridad = { alta: 0, media: 0, baja: 0 };
  d.hallazgos.forEach((h) => { porSeveridad[h.severidad] = (porSeveridad[h.severidad] || 0) + 1; });
  const lentesActivas = [...new Set(d.hallazgos.map((h) => h.lente))];
  const prioridad = { alta: 0, media: 1, baja: 2 };
  if (d.revision) Object.assign(porSeveridad, {alta:0,media:0,baja:0}, d.revision.prioridades);
  const principal = d.revision?.casos?.[0]?.primary_finding || ordenarControles(d.hallazgos)[0];
  const controlesSolicitados = d.devolucion?.cobertura?.controles_solicitados?.controles || [];
  const controlesNoEvaluados = controlesSolicitados.filter((control) => control.estado === "no_evaluable");
  const resumenControles = controlesSolicitados.map((control) => `${control.nombre}: ${control.resultado}`).join(" ");
  const coberturaParcial = ["COBERTURA_PARCIAL", "PREGUNTA_NO_EVALUADA"].includes(d.devolucion?.cobertura?.estado) || d.devolucion?.cobertura?.condiciones_validez?.puede_concluir === false;
  const nivel = porSeveridad.alta ? "alta" : porSeveridad.media ? "media" : d.hallazgos.length ? "baja" : controlesNoEvaluados.length || coberturaParcial ? "media" : "ok";
  let tono = {
    alta: "Hay señales de alta prioridad para revisar antes de decidir.",
    media: "Hay señales relevantes que conviene pedir contexto o documentar.",
    baja: "Hay señales leves o exploratorias; sirven para seguimiento.",
    ok: "No aparecieron señales comunicables con la información cargada.",
  }[nivel];
  const foco = principal
    ? `Primer foco sugerido: ${principal.lente}${principal.modo ? " · " + principal.modo : ""}.`
    : "No hay foco prioritario.";
  let queAparecio = principal
    ? principal.descripcion
    : resumenControles || "No aparecieron señales que requieran una revisión prioritaria.";
  let porQueImporta = {
    alta: "Puede afectar una decisión o un control importante. Conviene revisarla antes de avanzar.",
    media: "Merece contexto o documentación adicional antes de aceptarla o descartarla.",
    baja: "Es una observación exploratoria. Puede dejarse en seguimiento sin tratarla como un problema confirmado.",
    ok: "Los controles ejecutados no seleccionaron señales. Esto no demuestra ausencia de errores; revisá también la cobertura y lo no evaluado.",
  }[nivel];
  let queRevisar = principal
    ? preguntaInstitucional(principal)
    : "No se requiere información adicional para explicar señales, porque no se detectaron señales con estos controles. Conservá el reporte como evidencia de la revisión.";
  if (!principal && controlesSolicitados.length) {
    if (controlesNoEvaluados.length) {
      tono = "La pregunta declarada no pudo evaluarse por completo con la estructura disponible.";
      porQueImporta = "Cero señales no equivale a conformidad cuando un control pedido quedó sin evaluar.";
      queRevisar = "Revisá el motivo informado, ajustá la estructura del archivo y volvé a ejecutar el análisis.";
    } else {
      tono = "Los controles pedidos fueron ejecutados y su resultado se informa por separado de las señales.";
      porQueImporta = "La respuesta surge de cálculos determinísticos aplicados a la estructura identificada.";
      queRevisar = resumenControles;
    }
  }
  const contexto = contextoSeries(d);
  if (!principal && coberturaParcial) {
    tono = "La revisión tiene cobertura parcial o condiciones pendientes.";
    queAparecio = "No se detectaron inconsistencias con los controles evaluables.";
    porQueImporta = "Los controles sin datos suficientes no equivalen a resultados conformes.";
    queRevisar = "Consultá el alcance de esta revisión para completar las condiciones pendientes y volver a analizar.";
  }
  const temporal = d.devolucion?.cobertura?.resumen_temporal;
  if (temporal?.cantidad >= 10 && !d.hallazgos.some(h => h.evidencia?.naturaleza === "control")) {
    tono = "La lectura requiere distinguir variaciones anuales y señales de otros controles.";
    queAparecio = `${temporal.cantidad} señales temporales anuales y ${temporal.otras_senales} señales de otros controles. No equivalen a ese número de errores.`;
    porQueImporta = "Varios movimientos pueden compartir contexto de período, unidad, cobertura o metodología. Una variación nominal no demuestra un cambio real.";
    queRevisar = "Revisar el contexto compartido por período y después las celdas particulares. Los controles de fórmulas se leen por separado.";
  }
  el.innerHTML = `
    <div class="executive-read executive-${nivel}">
      <div>
        <span class="badge ${nivel === "ok" ? "badge-ok" : "badge-" + nivel}">${(controlesNoEvaluados.length || coberturaParcial) && !principal ? "cobertura parcial" : nivel === "ok" ? "sin señales" : "prioridad " + nivel}</span>
        <p>${tono}</p>
      </div>
      <div class="executive-quick" aria-label="Lectura rápida en tres pasos">
        <div class="executive-quick-item">
          <span>1 · Qué llamó la atención</span>
          <p>${queAparecio}</p>
        </div>
        <div class="executive-quick-item">
          <span>2 · Por qué merece revisión</span>
          <p>${porQueImporta}</p>
        </div>
        <div class="executive-quick-item">
          <span>3 · Qué revisar ahora</span>
          <p>${queRevisar}</p>
        </div>
      </div>
      ${contexto ? `<small class="executive-context">${contexto}</small>` : ""}
      ${temporal?.cantidad ? `<section class="executive-context"><h3>Variaciones anuales para contextualizar</h3><p>${escapeHtml(temporal.aclaracion)}</p><p>${Object.entries(temporal.periodos).map(([p,n]) => `${escapeHtml(p)}: ${n} señales`).join(" · ")}</p><details><summary>Referencias para empezar la lectura</summary><p>${escapeHtml(temporal.criterio)}</p><ul>${temporal.referencias.map(x => `<li>${escapeHtml(x.hoja || "Archivo")} · ${escapeHtml(x.periodo)}: ${escapeHtml(x.serie)}. Ratio histórico: ${x.ratio}.</li>`).join("")}</ul></details></section>` : ""}
      <details class="executive-tech">
        <summary>Ver resumen técnico</summary>
        <div class="executive-meta">
          <span>${contar(d.hallazgos.length, "hallazgo")}</span>
          <span>${contar(lentesActivas.length, "lente activa", "lentes activas")}</span>
          <span>${contar(d.coincidencias.length, "coincidencia")}</span>
        </div>
        <small>${foco} Abrí los bloques de abajo si necesitás evidencia, comparación entre modelos, límites de lectura o descargar un reporte.</small>
      </details>
    </div>`;
}

function renderCriterioRazonable(d) {
  const conEvidencia = d.hallazgos.filter((h) => h.evidencia && Object.keys(h.evidencia).length).length;
  const tiposRegla = new Set(["REGLA_FORMAL_O_ARITMETICA", "FORMULA_EXCEL", "PATRON_ARITMETICO_INFERIDO", "CONTROL_EXPLICITO_DEL_ARCHIVO", "CONSISTENCIA_ARITMETICA_PDF"]);
  const reglasFormales = d.hallazgos.filter((h) => tiposRegla.has(h.tipo_evidencia)).length;
  const reglasConFundamento = d.hallazgos.filter((h) => tiposRegla.has(h.tipo_evidencia) && h.limites?.fundamento_regla).length;
  const items = [
    { label: "Evidencia explicitada", ok: conEvidencia === d.hallazgos.length || d.hallazgos.length === 0, detail: `${conEvidencia} de ${contar(d.hallazgos.length, "hallazgo")}` },
    { label: "Fundamento de regla", ok: reglasConFundamento === reglasFormales, detail: reglasFormales ? `${reglasConFundamento} de ${contar(reglasFormales, "regla")} con fuente y alcance` : "sin reglas formales categóricas" },
    { label: "Incertidumbre visible", ok: true, detail: "se comunica por lente, severidad, tipo de evidencia y triangulación" },
    { label: "Revisión humana", ok: !!d.decision, detail: d.decision ? "decisión registrada" : "pendiente de decisión" },
    { label: "Alcance agregado", ok: true, detail: "sin microdatos, proveedores, contratistas ni casos individuales en la lectura" },
    { label: "Neutralidad política", ok: true, detail: "no mide ideologías, partidos ni mérito de gestión" },
  ];
  document.getElementById("criterio-razonable").innerHTML = `
    <div class="criterio-grid">
      ${items.map((it) => `
        <div class="criterio-item ${it.ok ? "ok" : "pendiente"}">
          <strong>${it.label}</strong>
          <span>${it.detail}</span>
        </div>`).join("")}
    </div>`;
}

function renderTrazabilidadCuadros(bloques) {
  const conTraza = (bloques || []).filter((b) => b.trazabilidad_controles);
  if (!conTraza.length) return "";
  const controles = conTraza.flatMap((b) => Object.values(b.trazabilidad_controles || {})).filter((c) => c.seleccionado);
  const ejecutados = controles.filter((c) => c.estado === "ejecutado").length;
  const modulos = controles.filter((c) => c.estado === "modulo_ejecutado").length;
  const sinTraza = controles.filter((c) => c.estado === "sin_traza_de_ejecucion").length;
  const nombresResultado = {senal_justificada: "señales justificadas", senal_infundada: "señales infundadas",
    omision: "omisiones", sin_senal_revisado: "sin señal tras revisión"};
  return `<details class="control-trace"><summary>Trazabilidad por cuadro: ${contar(conTraza.length, "cuadro")}; ${contar(ejecutados, "control ejecutado")}, ${contar(modulos, "módulo invocado")}, ${contar(sinTraza, "selección sin traza propia", "selecciones sin traza propia")}</summary>
    <p>La selección de la IA confirmada indica qué corresponde intentar. Sólo «ejecutado» acredita el paso del control; «módulo invocado» no acredita cada subcontrol. Cero señales tampoco significa que el dato sea correcto.</p>
    ${typeof state !== "undefined" && state.currentUser?.rol === "admin" && state.detalleId ? `<p><a href="/tecnico.html?casos=${Number(state.detalleId)}">Incorporar un caso revisado a la biblioteca</a></p>` : ""}
    ${conTraza.map((b) => {
      const traza = Object.entries(b.trazabilidad_controles || {});
      const experiencia = b.experiencia_comparable || [];
      return `<details><summary>${escapeHtml(b.archivo || "Archivo")} · ${escapeHtml(b.hoja || "Hoja")} · cuadro ${Number(b.bloque) || 0}</summary>
        <ul>${traza.filter(([, c]) => c.seleccionado).map(([codigo, c]) => `<li><strong>${escapeHtml(codigo)}:</strong> ${escapeHtml(String(c.estado).replaceAll("_", " "))}. ${escapeHtml(c.motivo || "")}</li>`).join("")}</ul>
        <p><strong>Antecedentes estructurales comparables:</strong> ${experiencia.length ? experiencia.map((e) => {
          const resultados = Object.entries(e.resultados || {}).map(([k, n]) => `${Number(n) || 0} ${escapeHtml(nombresResultado[k] || k)}`).join(", ");
          return `${escapeHtml(e.control)}: ${Number(e.casos_comparables) || 0} lecturas confirmadas, ${Number(e.revisados_por_persona) || 0} resultados revisados${resultados ? ` (${resultados})` : ""}`;
        }).join("; ") : "sin controles con antecedentes medidos"}. La coincidencia de estructura y roles no es una probabilidad de acierto.</p>
      </details>`;
    }).join("")}
  </details>`;
}

function renderCoberturaLimites(d) {
  const el = document.getElementById("cobertura-limites");
  if (!el) return;
  const cobertura = d.devolucion?.cobertura || {};
  const lentes = cobertura.lentes || [];
  const opts = cobertura.opciones_tecnicas || {};
  const pdf = cobertura.pdf || {};
  const excluidas = cobertura.columnas_excluidas || [];
  const contextualizacion = cobertura.contextualizacion || {};
  const controlesContexto = contextualizacion.controles || [];
  const controlesSolicitados = cobertura.controles_solicitados?.controles || [];
  const registro = cobertura.registro_revision || null;
  // Un límite que afirma una comparación que no se hizo contradice al registro: se corrige con él.
  const limites = (cobertura.limites_globales || []).map((x) => (registro?.cruces && registro.cruces.estado !== "evaluado")
    ? String(x).replace("Se compararon los años comunes entre las ediciones cargadas.", registro.cruces.texto)
    : x);
  const negativoRizoma = cobertura.controles_negativos?.rizoma;
  el.innerHTML = `
    <div class="coverage-box">
      <div class="coverage-head">
        <span class="badge ${cobertura.estado === "SIN_SENALES_COMUNICABLES" ? "badge-ok" : "badge-media"}">${escapeHtml(registro ? ({completo: "Lectura completa", parcial: "Lectura parcial", insuficiente: "Lectura insuficiente"}[registro.estado] || registro.estado) : String(cobertura.estado || "sin estado").replaceAll("_", " ").replace("SENALES", "SEÑALES"))}</span>
        <span>${contar(cobertura.filas_analizadas ?? d.n_filas, "fila agregada analizada", "filas agregadas analizadas")}</span>
      </div>
      ${cobertura.excel_resumen?.length ? `<p><strong>${escapeHtml(cobertura.excel_resumen[0])}</strong></p><details><summary>Ver hojas incluidas y límites de lectura</summary><ul>${cobertura.excel_resumen.slice(1).map(x => `<li>${escapeHtml(x)}</li>`).join("")}</ul></details>` : ""}
      ${renderTrazabilidadCuadros(cobertura.excel?.bloques)}
      <div class="coverage-lenses">
        ${lentes.filter(l => !["no_aplicable","no_evaluable"].includes(l.estado)).map((l) => `<span>${l.lente}: ${l.hallazgos}</span>`).join("")}
      </div>
      <details><summary>Controles no aplicables o no evaluables</summary>${lentes.filter(l => ["no_aplicable","no_evaluable"].includes(l.estado)).map(l => `<p><strong>${escapeHtml(l.lente)}</strong> · ${escapeHtml(l.estado.replaceAll('_',' '))}: ${escapeHtml(l.motivo || '')}</p>`).join('')}</details>
      <div class="coverage-detail">
        <p><strong>Opciones técnicas:</strong> fórmulas fuera de patrón ${opts.revisar_formulas_excel ? "sí" : "no"}, planillas sin fórmulas ${opts.inferir_patrones_calculo ? "sí" : "no"}, promedios que no ponderan ${opts.revisar_metodo_calculo ? "sí" : "no"}, PDF ${opts.limite_paginas_pdf || "-"} páginas.</p>
        ${controlesSolicitados.length ? `<div class="requested-controls"><strong>Respuesta a la pregunta declarada</strong><ul>${controlesSolicitados.map((control) => `<li><span class="badge ${control.estado === "no_evaluable" ? "badge-media" : control.estado === "observado" ? "badge-alta" : "badge-ok"}">${control.estado.replaceAll("_", " ")}</span> <strong>${control.nombre}:</strong> ${control.resultado}</li>`).join("")}</ul></div>` : ""}
        ${pdf.cantidad_archivos ? `<p><strong>PDF:</strong> ${pdf.paginas_analizadas || "-"} de ${pdf.paginas_documento ? contar(pdf.paginas_documento, "página") : "- páginas"}, extracción ${Array.isArray(pdf.modos_extraccion) ? pdf.modos_extraccion.join(", ") : "-"}${pdf.truncado_por_paginas ? ". Documento recortado por límite." : ""}</p>` : ""}
        ${controlesContexto.length ? `<p><strong>Contextualización:</strong> ${controlesContexto.map((c) => `${c.nombre}: ${c.estado}`).join("; ")}.</p>` : ""}
        ${negativoRizoma ? `<p><strong>Control negativo de Rizoma:</strong> ${negativoRizoma.metodo}; ${negativoRizoma.columnas.join(" / ")}; r = ${negativoRizoma.coeficiente_pearson}; n = ${negativoRizoma.n_observaciones}; por debajo del umbral |r| ≥ ${negativoRizoma.umbral_seleccion_abs}.</p>` : ""}
        ${excluidas.length ? `<p><strong>Columnas excluidas:</strong> ${excluidas.join(", ")}</p>` : ""}
        ${limites.length ? `<ul>${limites.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>` : ""}
      </div>
    </div>`;
}

function detalleHallazgo(h) {
  const e = h.evidencia || {};
  const columnas = Array.isArray(e.columnas) ? e.columnas.filter(Boolean) : [e.columna, e.columna_mayor, e.columna_menor, e.columna_total].filter(Boolean);
  if (e.fila_detalle) return e.fila_detalle;
  if (e.celda) return e.celda;
  if (e.serie) return e.serie;
  if (e.filas_detalle?.length) return e.filas_detalle.slice(0, 3).join("; ");
  if (columnas.length) return columnas.join(" / ");
  if (e.columna_detalle) return e.columna_detalle;
  if (Array.isArray(e.notas_cobertura) && e.notas_cobertura.length) {
    return e.notas_cobertura.slice(0, 2).map((item) => item.detalle || item).join("; ");
  }
  return "la señal indicada";
}

// El backend (services/guardrails.py::pregunta_institucional) ya calcula y
// persiste esta pregunta para practicamente todo hallazgo -- este fallback
// casi nunca corre. Antes duplicaba el mapa por lente ademas de guardrails.py
// y markdown.py; se dejo un solo texto generico para no tener una tercera
// copia que se desincronice si cambia la redaccion en el backend.
function preguntaInstitucional(h) {
  return h.pregunta_es || h.pregunta_institucional || `Explicar con evidencia documentada qué contexto justifica ${detalleHallazgo(h)}.`;
}

function renderPreguntaSugerida(hallazgos) {
  const el = document.getElementById("pregunta-sugerida");
  if (!hallazgos.length) {
    el.innerHTML = `<p>No hay pregunta sugerida porque el barrido no encontró señales comunicables.</p>`;
    return;
  }
  const prioridad = { alta: 0, media: 1, baja: 2 };
  const h = [...hallazgos].sort((a, b) => (prioridad[a.severidad] ?? 9) - (prioridad[b.severidad] ?? 9))[0];
  el.innerHTML = `
    <div class="lente-tag">${nombreLenteLegible(h.lente)} ${badgeSeveridad(h.severidad)}</div>
    ${quePaso(h)}
    <p>${preguntaInstitucional(h)}</p>
    <small>La pregunta no acusa, no concluye y no evalúa oportunidad institucional: ordena qué contexto pedir antes de decidir.</small>`;
}

function renderComoLeerResultado() {
  const items = [
    ["Marco preventivo", "Ordena señales para revisión responsable."],
    ["Lectura ejecutiva", "Resume evidencia agregada y contexto disponible."],
    ["Gobernanza operativa", "Ayuda a decidir qué contexto pedir y qué seguimiento corresponde."],
    ["Complemento de gestión", "Aporta lectura temprana para equipos responsables."],
    ["Decisión humana", "El responsable define pasos siguientes."],
    ["Alcance agregado", "Opera sobre reportes consolidados, indicadores, series y métricas agregadas."],
    ["Comparación institucional", "Compara dimensiones agregadas y patrones de comportamiento."],
    ["Hipótesis revisables", "Las asociaciones orientan preguntas, no conclusiones automáticas."],
    ["Criterio técnico", "Contrasta datos con reglas explícitas y criterios documentados."],
    ["Neutralidad institucional", "Se concentra en consistencia, método y evidencia agregada."],
  ];
  document.getElementById("que-no-es").innerHTML = items
    .map(([t, d]) => `<div class="no-es-item"><strong>${t}</strong><span>${d}</span></div>`)
    .join("");
}

let LENTES = [
  {
    id: "conciliador",
    nombre: "Conciliador",
    pregunta: "¿La señal puede venir de carga, acumulados o reclasificación?",
    salidaVacia: "No encontró artefactos técnicos claros que condicionen la lectura.",
  },
  {
    id: "ajedrecista",
    nombre: "Ajedrecista",
    pregunta: "¿Hay una configuración imposible o fuera de lugar?",
    salidaVacia: "No encontró imposibilidades lógicas ni configuraciones prioritarias para revisar.",
  },
  {
    id: "cronista",
    nombre: "Cronista",
    pregunta: "¿Cuándo cambia la historia de la serie?",
    salidaVacia: "No detectó cortes temporales comunicables con la información disponible.",
  },
  {
    id: "orquesta",
    nombre: "Orquesta",
    pregunta: "¿Las magnitudes son coherentes entre sí?",
    salidaVacia: "No detectó rupturas de coherencia sistémica con la información disponible.",
  },
  {
    id: "radiologo",
    nombre: "Radiólogo",
    pregunta: "¿El caso se parece a antecedentes comparables?",
    salidaVacia: "No encontró semejanzas históricas señalables; puede faltar banco comparable suficiente.",
  },
  {
    id: "rizoma",
    nombre: "Rizoma",
    pregunta: "¿Aparecen conexiones inesperadas?",
    salidaVacia: "No detectó asociaciones exploratorias con evidencia suficiente para comunicar.",
  },
  {
    id: "matematico",
    nombre: "Matemático",
    pregunta: "¿El cálculo corresponde al tipo de informe?",
    salidaVacia: "No detectó un método de cálculo metodológicamente dudoso con la información disponible.",
  },
];

function renderGuiaLentesDesdeMatriz() {
  const guia = document.getElementById("guia-lentes");
  if (guia) {
    guia.innerHTML = LENTES.map((lente) => `
      <article class="guide-lens-card guide-lens-${escapeHtml(lente.id)}${lente.id === "conciliador" ? " guide-lens-transversal" : ""}">
        <span class="guide-kicker">${escapeHtml(lente.rol || "Lectura especializada")}</span>
        <h3>${escapeHtml(lente.nombre)}</h3>
        <p><strong>${escapeHtml(lente.pregunta)}</strong></p>
        <dl>
          <dt>Preguntas de control</dt>
          <dd><ul>${(lente.preguntas || []).map((pregunta) => `<li>${escapeHtml(pregunta)}</li>`).join("")}</ul></dd>
        </dl>
        <details class="plegable"><summary>Evidencia, límites y cuándo no evalúa</summary>
        <dl>
          <dt>Evidencia mínima</dt>
          <dd>${(lente.evidenciaMinima || []).map(escapeHtml).join("; ") || "Evidencia trazable del objeto revisado."}</dd>
          <dt>Cuándo observa</dt>
          <dd>${escapeHtml(lente.criterios?.observado || "Cuando la señal requiere explicación o corrección.")}</dd>
          <dt>Cuándo no puede evaluar</dt>
          <dd>${escapeHtml(lente.criterios?.no_evaluable || "Cuando falta evidencia suficiente.")}</dd>
          <dt>Límites</dt>
          <dd>${(lente.limites || []).map(escapeHtml).join(" ")}</dd>
        </dl>
        </details>
      </article>
    `).join("");
  }
  const tabla = document.querySelector("#tabla-guide-compare tbody");
  if (tabla) {
    tabla.innerHTML = LENTES.map((lente) => `
      <tr class="${lente.id === "conciliador" ? "guide-compare-transversal" : ""}">
        <th>${escapeHtml(lente.nombre)}</th>
        <td>${escapeHtml(lente.rol || "-")}</td>
        <td>${escapeHtml(lente.criterios?.observado || "-")}</td>
        <td>${(lente.evidenciaMinima || []).map(escapeHtml).join("; ") || "-"}</td>
      </tr>
    `).join("");
  }
}

async function cargarMatrizLentes() {
  try {
    const matriz = await apiFetch("/certificaciones/lentes");
    if (!Array.isArray(matriz) || matriz.length !== 7) return;
    LENTES = matriz.map((lente) => ({
      id: lente.id,
      nombre: lente.nombre,
      rol: lente.rol,
      pregunta: lente.pregunta_central,
      preguntas: lente.preguntas || [],
      evidenciaMinima: lente.evidencia_minima || [],
      criterios: lente.criterios || {},
      limites: lente.limites || [],
      salidaVacia: lente.salida_vacia,
    }));
    renderGuiaLentesDesdeMatriz();
  } catch (_error) {
    // La guía HTML y la matriz de respaldo conservan una explicación usable.
  }
}

function estadoLente(items) {
  const alta = items.some((h) => h.severidad === "alta");
  const media = items.some((h) => h.severidad === "media");
  const baja = items.some((h) => h.severidad === "baja");
  if (alta) return { texto: "Atención alta", cls: "badge-alta", nivel: 100 };
  if (media) return { texto: "Atención media", cls: "badge-media", nivel: 66 };
  if (baja || items.length) return { texto: "Señal baja", cls: "badge-baja", nivel: 38 };
  return { texto: "Sin señales", cls: "badge-ok", nivel: 8 };
}

function nombreLenteLegible(lente) {
  return ({conciliador:"Conciliación de totales", ajedrecista:"Coherencia de datos", cronista:"Cambios entre períodos", orquesta:"Comparación conjunta", radiologo:"Antecedentes comparables", rizoma:"Relaciones entre variables", matematico:"Patrones y métodos de cálculo"})[lente] || escapeHtml(lente || "Control");
}

function resumenEvidencia(h) {
  const e = h.evidencia || {};
  const partes = [];
  if (e.puntaje_prioridad != null) {
    for (const [k,label] of [['valor_observado','Valor observado'],['valor_anterior','Anterior'],['valor_posterior','Posterior'],['regla','Regla'],['diferencia_absoluta','Diferencia absoluta'],['diferencia_porcentual','Diferencia %']]) {
      if (Object.prototype.hasOwnProperty.call(e,k)) partes.push(`${label}: ${escapeHtml(e[k] == null ? 'vacío' : String(e[k]))}`);
    }
  }
  if (e.celda) partes.push(`Celda: ${e.celda}${e.hoja ? ` · Hoja: ${e.hoja}` : ""}`);
  if (e.periodo_previo || e.periodo) partes.push(`Período: ${e.periodo_previo || "-"} -> ${e.periodo || "-"}`);
  if (e.serie) partes.push(`Serie: ${e.serie}`);
  const columnas = Array.isArray(e.columnas) ? e.columnas.filter(Boolean) : [e.columna, e.columna_mayor, e.columna_menor, e.columna_total].filter(Boolean);
  if (columnas.length) partes.push(`Columnas: ${columnas.join(" / ")}`);
  if (e.fila_detalle) partes.push(`Ubicación: ${e.fila_detalle}`);
  if (e.texto_control) partes.push(`Pasaje a revisar: “${e.texto_control}”`);
  if (Array.isArray(e.notas_cobertura) && e.notas_cobertura.length) {
    const notas = e.notas_cobertura.slice(0, 3).map((item) => item.detalle || item).join("; ");
    partes.push(`Notas de cobertura: ${notas}`);
  }
  if (e.muestra?.fila_detalle) partes.push(`Muestra: ${e.muestra.fila_detalle}`);
  if (e.filas_detalle?.length) partes.push(`Filas: ${e.filas_detalle.slice(0, 4).join("; ")}`);
  if (e.metodo) partes.push(`Método: ${e.metodo}`);
  if (e.coeficiente_pearson !== undefined) partes.push(`Pearson: r = ${e.coeficiente_pearson} · n = ${e.n_observaciones}`);
  if (e.periodo_desde || e.periodo_hasta) partes.push(`Período: ${e.periodo_desde || "-"} a ${e.periodo_hasta || "-"} · faltantes: ${e.datos_faltantes ?? "-"}`);
  if (e.umbral_seleccion_abs !== undefined) partes.push(`Umbral: |r| ≥ ${e.umbral_seleccion_abs}`);
  if (e.correlacion_primeras_diferencias !== undefined && e.correlacion_primeras_diferencias !== null) partes.push(`Primeras diferencias: r = ${e.correlacion_primeras_diferencias} · n = ${e.n_primeras_diferencias}`);
  if (e.limitacion_muestra) partes.push(e.limitacion_muestra);
  const fundamento = h.limites?.fundamento_regla;
  if (fundamento?.regla) {
    partes.push(`Regla: ${fundamento.regla}${fundamento.fuente ? ` · Fuente: ${fundamento.fuente}` : ""}`);
  }
  if (e.filas_credito_cero_con_ejecucion_detalle?.length) {
    partes.push(`Crédito cero con ejecución: ${e.filas_credito_cero_con_ejecucion_detalle.slice(0, 4).join("; ")}`);
  }
  const anidadas = [];
  [e.reversas_mensuales, e.acumulados_que_retroceden, e.ratios_extremos].forEach((grupo) => {
    (grupo || []).forEach((item) => {
      if (item.filas_detalle?.length) {
        const nombre = item.columna || item.relacion || "detalle";
        anidadas.push(`${nombre}: ${item.filas_detalle.slice(0, 3).join("; ")}`);
      }
    });
  });
  if (anidadas.length) partes.push(anidadas.slice(0, 3).join(" | "));
  return partes.slice(0, 9);
}
function renderInformeLentes(hallazgos, controles = []) {
  const condicion = id => controles.find(c => c.lente === id);
  const estadoVisible = (items, id) => {
    const c = condicion(id);
    if (c && ["no_aplicable", "no_evaluable"].includes(c.estado)) return {
      cls: "badge-media", nivel: 0, texto: c.estado === "no_aplicable" ? "no aplicable" : "no evaluado"
    };
    return estadoLente(items);
  };
  const el = document.getElementById("informe-lentes");
  el.innerHTML = `
    <div class="lentes-mapa" aria-label="Mapa visual de lentes">
      ${LENTES.map((lente) => {
        const items = hallazgos.filter((h) => h.lente === lente.id);
        const estado = estadoVisible(items, lente.id);
        return `
          <div class="lente-mapa-row ${items.length ? "activa" : "quieta"}">
            <div class="lente-mapa-main">
              <span class="lente-mapa-nombre">${lente.nombre}</span>
              <span class="lente-mapa-count">${items.length}</span>
            </div>
            <div class="lente-barra"><span class="${estado.cls}" style="width:${estado.nivel}%"></span></div>
            <span class="badge ${estado.cls}">${estado.texto}</span>
          </div>
        `;
      }).join("")}
    </div>
    <div class="lentes-grid">
      ${LENTES.map((lente) => {
        const items = hallazgos.filter((h) => h.lente === lente.id);
        const estado = estadoVisible(items, lente.id);
        return `
          <section class="lente-panel ${items.length ? "con-hallazgos" : "sin-hallazgos"}">
            <div class="lente-panel-head">
              <div>
                <div class="lente-nombre">${lente.nombre}</div>
                <div class="lente-pregunta">${escapeHtml(lente.pregunta)}</div>
              </div>
              <span class="badge ${estado.cls}">${estado.texto}</span>
            </div>
            ${
              items.length
                ? `<ul class="lente-lista">${items.map((h) => `<li>${h.descripcion}</li>`).join("")}</ul>`
                : `<p class="lente-vacia">${escapeHtml(condicion(lente.id)?.motivo || lente.salidaVacia)}</p>`
            }
            ${(lente.preguntas || []).length ? `
              <details class="lente-preguntas-detalle">
                <summary>Ver preguntas y evidencia esperada</summary>
                <ul>${lente.preguntas.map((pregunta) => `<li>${escapeHtml(pregunta)}</li>`).join("")}</ul>
                <p><strong>Evidencia mínima:</strong> ${(lente.evidenciaMinima || []).map(escapeHtml).join("; ")}.</p>
              </details>` : ""}
          </section>
        `;
      }).join("")}
    </div>`;
}

function botonesDescargaReporte() {
  return Array.from(document.querySelectorAll("[data-reporte-formato]"));
}

function actualizarControlesReporte() {
  const checks = Array.from(document.querySelectorAll(".hallazgo-check"));
  const elegidos = checks.filter((c) => c.checked).length;
  state.reporteSeleccion = new Set(checks.filter((c) => c.checked).map((c) => Number(c.dataset.id)));
  const totalHallazgos = state.detalle?.hallazgos?.length ?? checks.length;
  const texto = totalHallazgos
    ? `${elegidos} de ${contar(totalHallazgos, "hallazgo")} seleccionados`
    : "Reporte ejecutivo sin hallazgos";
  const contador = document.getElementById("reporte-contador");
  const contadorGlobal = document.getElementById("reporte-global-contador");
  const btn = document.getElementById("btn-descargar-reporte");
  const btnGlobal = document.getElementById("btn-descargar-reporte-global");
  const botonesFormato = botonesDescargaReporte();
  if (contador) contador.textContent = texto;
  if (contadorGlobal) contadorGlobal.textContent = texto;
  if (btn) btn.disabled = !state.detalle?.devolucion;
  if (btnGlobal) btnGlobal.disabled = !state.detalle?.devolucion;
  botonesFormato.forEach((boton) => { boton.disabled = !state.detalle?.devolucion; });
}

function setSeleccionReporte(valor) {
  document.querySelectorAll(".hallazgo-check").forEach((check) => { check.checked = valor; });
  actualizarControlesReporte();
}

async function descargarReporteSeleccionado(event) {
  const formato = event?.currentTarget?.dataset?.reporteFormato || "pdf";
  const ids = Array.from(state.reporteSeleccion);
  const btn = event?.currentTarget || document.getElementById("btn-descargar-reporte-global") || document.getElementById("btn-descargar-reporte");
  const btnLocal = document.getElementById("btn-descargar-reporte");
  const btnGlobal = document.getElementById("btn-descargar-reporte-global");
  const botonesFormato = botonesDescargaReporte();
  const payload = {
    incluir_triangulacion: document.getElementById("reporte-incluir-triangulacion")?.checked ?? true,
    incluir_devolucion: document.getElementById("reporte-incluir-devolucion")?.checked ?? true,
    incluir_detalle_modelos: document.getElementById("reporte-detalle-modelos")?.checked ?? false,
    formato,
    pieza: event?.currentTarget?.dataset?.reportePieza || "ejecutivo",
  };
  if (ids.length) payload.hallazgo_ids = ids;
  if (btnLocal) btnLocal.disabled = true;
  if (btnGlobal) btnGlobal.disabled = true;
  botonesFormato.forEach((boton) => { boton.disabled = true; });
  const textoOriginal = btn?.textContent || "";
  if (btn) btn.textContent = "Preparando…";
  try {
    const { blob, filename } = await apiFetchDownload(`/informes/${state.detalleId}/reporte`, payload);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast("Reporte descargado");
  } catch (e) {
    toast("No se pudo descargar el reporte: " + e.message, true);
  } finally {
    if (btnLocal) btnLocal.textContent = "Informe de revisión PDF";
    if (btnGlobal) btnGlobal.textContent = "Informe de revisión PDF";
    if (btn && btn !== btnLocal && btn !== btnGlobal) btn.textContent = textoOriginal;
    actualizarControlesReporte();
  }
}


function esLector() {
  return state.currentUser?.rol === "lector";
}

function esAdmin() {
  return state.currentUser?.rol === "admin";
}

function puedeOperarInformes() {
  return ["admin", "analista"].includes(state.currentUser?.rol);
}

function puedeRegistrarAprendizaje() {
  return puedeOperarInformes();
}

function puedeBorrarInformes() {
  return puedeOperarInformes();
}

function ordenarControles(hallazgos) {
  const valor = h => h.evidencia?.puntaje_prioridad ?? ({alta:80,media:50,baja:20}[h.severidad] || 0);
  const contexto = h => h.evidencia?.naturaleza === "contexto" || h.evidencia?.requiere_contexto_anual;
  return [...hallazgos].sort((a,b) => Number(!!contexto(a))-Number(!!contexto(b)) || valor(b)-valor(a));
}

const RESPUESTAS_SENAL = [["error_real", "Era un error real"], ["dato_correcto", "El dato estaba bien"], ["no_se", "No sé todavía"]];

function textoRespuestaSenal(r) {
  // El detalle llega escapado (escapeDeep) y la respuesta del POST no: se escapa una sola vez en los dos casos.
  return `<strong>Respuesta registrada:</strong> ${escapeHtmlUnaVez(r.texto)}${r.comentario ? ` · ${escapeHtmlUnaVez(r.comentario)}` : ""}`
    + (r.creado_en ? ` <small>(${escapeHtmlUnaVez(String(r.creado_en).slice(0, 10))})</small>` : "");
}

// «¿Qué resultó ser esta señal?»: sólo quien hizo el informe responde; quien sólo mira ve la respuesta registrada.
function renderRespuestaSenal(h) {
  const actual = h.respuesta ? `<p class="respuesta-actual">${textoRespuestaSenal(h.respuesta)}</p>` : "";
  if (!h.puede_responder) return actual ? `<div class="respuesta-senal">${actual}</div>` : "";
  return `<div class="respuesta-senal" data-hallazgo="${Number(h.id)}">
      <p class="respuesta-pregunta">¿Qué resultó ser esta señal?</p>
      ${actual}
      <div class="respuesta-botones">${RESPUESTAS_SENAL.map(([valor, texto]) => `<button type="button" class="btn btn-respuesta${h.respuesta?.respuesta === valor ? " activa" : ""}" data-respuesta="${valor}">${texto}</button>`).join("")}</div>
      <input type="text" class="respuesta-comentario" maxlength="500" value="${escapeHtmlUnaVez(h.respuesta?.comentario || "")}" placeholder="Opcional: qué pasó (hasta 500 caracteres)" aria-label="Comentario opcional sobre la señal" />
      <small>Si cambiás la respuesta, se guarda con el comentario que quede escrito acá.</small>
      <small>Tu respuesta queda registrada con fecha. Sirve para medir la herramienta, no para evaluarte.</small>
    </div>`;
}

async function responderSenal(ev) {
  const btn = ev.currentTarget;
  const bloque = btn.closest(".respuesta-senal");
  // En el caso principal no hay campo de comentario: se reenvía el vigente (data-comentario) para no borrarlo.
  const comentario = bloque.querySelector(".respuesta-comentario")?.value ?? bloque.dataset.comentario ?? "";
  try {
    const r = await apiFetch(`/informes/${state.detalleId}/hallazgos/${Number(bloque.dataset.hallazgo)}/respuesta`,
      { method: "POST", body: JSON.stringify({ respuesta: btn.dataset.respuesta, comentario }) });
    // La misma señal puede estar en un caso principal y en el anexo: se actualizan los dos bloques.
    const id = Number(bloque.dataset.hallazgo);
    const hallazgo = state.detalle?.hallazgos?.find((x) => Number(x.id) === id);
    if (hallazgo) hallazgo.respuesta = r.respuesta;
    document.querySelectorAll(`.respuesta-senal[data-hallazgo="${id}"]`).forEach((b) => {
      b.querySelectorAll(".btn-respuesta").forEach((x) => x.classList.toggle("activa", x.dataset.respuesta === btn.dataset.respuesta));
      if (b.dataset.comentario !== undefined) b.dataset.comentario = r.respuesta.comentario || "";
      let actual = b.querySelector(".respuesta-actual");
      if (!actual) {
        actual = document.createElement("p");
        actual.className = "respuesta-actual";
        b.querySelector(b.classList.contains("respuesta-senal-caso") ? ".respuesta-botones" : ".respuesta-pregunta").after(actual);
      }
      actual.innerHTML = b.classList.contains("respuesta-senal-caso")
        ? `<strong>Respuesta registrada:</strong> ${escapeHtmlUnaVez(r.respuesta.texto)}` : textoRespuestaSenal(r.respuesta);
    });
    toast("Respuesta registrada.");
  } catch (e) {
    toast(e.message, true);
  }
}

async function guardarCierreInforme() {
  const el = document.getElementById("cierre-informe");
  const c = cierreInformeActual;
  if (!el || !c) return;
  const elegido = el.querySelector("[data-cierre].activa");
  if (!elegido) { toast("Elegí Sí, No o Todavía no.", true); return; }
  const crudo = String(el.querySelector("#cierre-errores")?.value ?? "").trim();
  if (crudo && !/^\d+$/.test(crudo)) { toast("La cantidad de errores tiene que ser un número entero (0 o más).", true); return; }
  const boton = el.querySelector("#btn-guardar-cierre");
  if (boton) boton.disabled = true;
  try {
    const r = await apiFetch(`/informes/${Number(c.informe_id)}/cierre`, {
      method: "POST", body: JSON.stringify({ corrigio: elegido.dataset.cierre, errores_no_senalados: crudo === "" ? null : Number(crudo) }),
    });
    const nuevo = { ...c, pendiente: false, respuesta: r.cierre };
    if (state.detalle?.id === c.informe_id) state.detalle.cierre_informe = nuevo;
    const fila = (state.informes || []).find((i) => i.id === c.informe_id);
    if (fila) fila.cierre_pendiente = false;
    renderCierreInforme({ id: c.informe_id, cierre_informe: nuevo });
    toast("Respuesta registrada.");
  } catch (e) {
    toast(e.message, true);
    if (boton) boton.disabled = false;
  }
}

// Lector del cuadro: cuando una relación leída tiene pocas aplicaciones, los números no alcanzan para confirmarla y
// se le pregunta a quien hizo el informe. Sólo con su «sí» da señales, al volver a analizar.
function textoLecturaRespuesta(r) {
  if (r === true) return "Respondiste que sí.";
  if (r === false) return "Respondiste que no.";
  return "";
}

function renderLecturaCuadro(m) {
  if (!m) return "";
  const preguntas = m?.preguntas || [];
  const sinLeer = m?.sin_leer || [];
  const resumen = m.resumen;
  const titulos = { completada: "Lectura recibida", parcial: "Lectura parcial", no_completada: "Lectura no completada" };
  const cobertura = resumen
    ? `<p class="lector-cobertura"><strong>${titulos[resumen.estado] || "Estado de la lectura"}.</strong> ${Number(resumen.tramos_con_lectura) || 0} de ${Number(resumen.tramos) || 0} tramos de filas y columnas con al menos dos respuestas; ${Number(resumen.relaciones_acordadas) || 0} relaciones acordadas.</p>
       ${m.fallo ? `<p>${escapeHtmlUnaVez(m.fallo.motivo)}. Los demás controles conservan sus resultados.</p>` : resumen.estado === "no_completada" ? "<p>No hubo suficientes respuestas para contrastar la lectura. Los demás controles conservan sus resultados; esta lectura quedó limitada.</p>" : ""}
       ${resumen.lecturas_fallidas ? `<p>${Number(resumen.lecturas_fallidas)} lecturas de modelos no se completaron. La cobertura quedó limitada.</p>` : ""}
       <p>${Number(resumen.relaciones_controladas) || 0} relaciones controladas. Recibir las lecturas no garantiza que se hayan identificado y controlado todos los totales del cuadro.</p>
       ${resumen.diferencias_no_mostradas ? `<p><strong>Detalle limitado:</strong> se muestran ${Number(resumen.diferencias_mostradas) || 0} de ${Number(resumen.diferencias_total) || 0} diferencias; ${Number(resumen.diferencias_no_mostradas) || 0} adicionales quedan registradas. El límite es de cinco por relación; no son errores independientes.</p><ul>${(resumen.limites_de_muestra || []).map((x) => `<li>${escapeHtmlUnaVez(x.archivo)} · hoja ${escapeHtmlUnaVez(x.hoja)} · ${escapeHtmlUnaVez(x.relacion)}: ${Number(x.mostradas) || 0} de ${Number(x.total) || 0} diferencias mostradas.</li>`).join("")}</ul>` : ""}
       ${resumen.estado !== "no_completada" && !resumen.relaciones_acordadas ? "<p>No hubo relaciones acordadas para comprobar. Esto no certifica que el cuadro esté libre de errores.</p>" : ""}`
    : "<p>Este análisis no tiene un resumen de cobertura del lector. Volvé a analizar para actualizarlo.</p>";
  const noLeido = sinLeer.length
    ? `<p><strong>Fuera de esta lectura:</strong> ${[...new Set(sinLeer.map((s) => `${escapeHtmlUnaVez(s.archivo || "Archivo")} · hoja ${escapeHtmlUnaVez(s.hoja)} (${escapeHtmlUnaVez(s.motivo)})`))].join("; ")}.</p>`
    : "";
  const bloques = (m.hojas || []).filter((h) => h.columnas?.length && h.filas?.length);
  const alcance = bloques.length
    ? `<details><summary>Ver hojas y bloques leídos</summary><ul>${bloques.map((h) => `<li>${escapeHtmlUnaVez(h.archivo || "Archivo")} · hoja ${escapeHtmlUnaVez(h.hoja)} · columnas ${escapeHtmlUnaVez(h.columnas.join(" a "))} · filas ${escapeHtmlUnaVez(h.filas.join(" a "))}</li>`).join("")}</ul></details>`
    : "";
  const prueba = m.requiere_reanalisis
    ? " <small>Volvé a analizar para confirmar cada relación en su archivo y hoja. Se conserva el historial anterior.</small>"
    : m.modo === "activo" ? "" : " <small>(En prueba: todavía no genera señales en el informe.)</small>";
  const items = preguntas.map((q) => {
    const estado = `<span class="lector-respuesta">${textoLecturaRespuesta(q.respuesta)}</span>`;
    const botones = m.puede_confirmar
      ? `<span class="lector-botones"><button type="button" class="btn btn-secondary btn-mini${q.respuesta === true ? " activa" : ""}" aria-pressed="${q.respuesta === true}" data-lector-confirma="si" data-pregunta="${escapeHtmlUnaVez(q.id)}">Sí, es así</button>
         <button type="button" class="btn btn-secondary btn-mini${q.respuesta === false ? " activa" : ""}" aria-pressed="${q.respuesta === false}" data-lector-confirma="no" data-pregunta="${escapeHtmlUnaVez(q.id)}">No</button></span>`
      : "";
    return `<li class="lector-pregunta" data-pregunta="${escapeHtmlUnaVez(q.id)}">Leímos que ${escapeHtmlUnaVez(q.fundamento || q.relacion)}
      <small>(${escapeHtmlUnaVez(q.archivo || "Archivo")} · hoja ${escapeHtmlUnaVez(q.hoja)}: ${escapeHtmlUnaVez(q.relacion)})</small>. ¿Es así? ${botones} ${estado}</li>`;
  }).join("");
  return `<div class="lector-cuadro"><strong>Así se leyó el cuadro.</strong>${prueba}
    ${cobertura}${alcance}${noLeido}${items ? `<p><strong>Tu confirmación permite comprobar estas relaciones:</strong></p><ul>${items}</ul>` : ""}
    <small>La IA propone relaciones sin ver los números de la grilla, salvo los valores que reconoce como años; las reglas comprueban y la persona decide.
    ${items ? "Las respuestas quedan registradas y se aplican al volver a analizar el informe." : "Que no aparezcan señales no demuestra que todos los datos sean correctos."}
    <a href="/detalle#lector-del-cuadro" target="_blank" rel="noopener">Cómo funciona el lector</a>.</small></div>`;
}

async function confirmarLectura(ev) {
  const btn = ev.currentTarget;
  const id = btn.dataset.pregunta;
  const item = btn.closest(".lector-pregunta");
  const botones = item.querySelectorAll("[data-lector-confirma]");
  if (btn.disabled) return;
  botones.forEach((b) => { b.disabled = true; });
  try {
    const r = await apiFetch(`/informes/${state.detalleId}/lector/${encodeURIComponent(id)}`,
      { method: "POST", body: JSON.stringify({ confirma: btn.dataset.lectorConfirma === "si" }) });
    botones.forEach((b) => {
      const seleccionada = (b.dataset.lectorConfirma === "si") === r.pregunta.respuesta;
      b.classList.toggle("activa", seleccionada);
      b.setAttribute("aria-pressed", String(seleccionada));
    });
    item.querySelector(".lector-respuesta").textContent = textoLecturaRespuesta(r.pregunta.respuesta);
    toast(r.aviso);
  } catch (e) {
    toast(e.message, true);
  } finally {
    botones.forEach((b) => { b.disabled = false; });
  }
}

function renderHallazgos(hallazgos, revision = null, comparacion = null) {
  hallazgos = ordenarControles(hallazgos);
  const el = document.getElementById("lista-hallazgos");
  if (!hallazgos.length) {
    el.innerHTML = `<div class="empty-state">No hay casos de control para mostrar. Consultá la cobertura y las limitaciones en el informe de revisión disponible desde el botón superior.</div>`;
    actualizarControlesReporte();
    return;
  }
  el.innerHTML = `
    <div class="hallazgos-toolbar">
      <div class="hallazgos-toolbar-main">
        <strong>Reporte descargable</strong>
        <span id="reporte-contador"></span>
      </div>
      <div class="hallazgos-toolbar-actions">
        <button type="button" class="btn btn-secondary btn-mini" id="btn-reporte-todos">Todos</button>
        <button type="button" class="btn btn-secondary btn-mini" id="btn-reporte-ninguno">Ninguno</button>
        <label class="mini-check"><input type="checkbox" id="reporte-incluir-triangulacion" checked /> Triangulación breve</label>
        <label class="mini-check"><input type="checkbox" id="reporte-incluir-devolucion" checked /> Devolución ejecutiva</label>
        <label class="mini-check"><input type="checkbox" id="reporte-detalle-modelos" /> Detalle de modelos</label>
        <button type="button" class="btn btn-primary" id="btn-descargar-reporte">Informe de revisión PDF</button>
        <details><summary>Detalle técnico opcional</summary><button type="button" class="btn btn-secondary" data-reporte-formato="pdf" data-reporte-pieza="anexo">Detalle técnico PDF</button></details>
        <button type="button" class="btn btn-secondary" data-reporte-formato="markdown">Descargar MD</button>
      </div>
    </div>
    ${puedeRegistrarAprendizaje() ? `<details class="plegable aprendizaje-plegable"><summary>Aprendizaje curado · para docentes y calibración</summary><div class="aprendizaje-hallazgo-box">
      <div>
        <strong>Aprendizaje curado</strong>
        <span>${state.currentUser?.rol === "admin" ? "Podés proponer y luego validar aprendizajes estructurados." : "Tu rol puede proponer aprendizajes; la validación queda para admin."}</span>
      </div>
      <select id="aprendizaje-tipo">
        <option value="criterio_metodologico">Criterio metodológico</option>
        <option value="falso_positivo">Falso positivo</option>
        <option value="regla_validada">Regla validada</option>
        <option value="regla_descartada">Regla descartada</option>
        <option value="ajuste_umbral">Ajuste de umbral</option>
      </select>
      <input type="text" id="aprendizaje-titulo" placeholder="Título breve del aprendizaje" />
      <textarea id="aprendizaje-hallazgo-contenido" placeholder="Qué se aprendió y cómo debería orientar futuras lecturas"></textarea>
      <button type="button" class="btn btn-secondary btn-mini" id="btn-registrar-aprendizaje-hallazgo">Guardar aporte de calibración</button><p id="calibracion-confirmacion" class="calibracion-confirmacion" role="status" hidden></p>
    </div></details>` : ""}
    ${revision?.casos ? renderCasosRevision(revision, comparacion) + '<details class="hallazgos-adicionales"><summary>Anexo: todas las señales técnicas y selección para el PDF</summary>' : ''}
    ${hallazgos
      .map((h, indice) => {
        const evidencia = resumenEvidencia(h);
        const checked = state.reporteSeleccion.has(h.id) ? "checked" : "";
        return `
        ${indice === 20 ? '<details class="hallazgos-adicionales"><summary>Ver resto de controles y contexto temporal</summary>' : ''}
        <div class="hallazgo sev-${h.severidad}">
          <div class="hallazgo-head">
            <label class="hallazgo-select">
              <input type="checkbox" class="hallazgo-check" data-id="${h.id}" ${checked} />
              <span>Incluir</span>
            </label>
            <div class="hallazgo-main">
              <div class="lente-tag">${nombreLenteLegible(h.lente)} ${badgeSeveridad(h.severidad)}</div>
              ${quePaso(h)}
              <p>${h.descripcion_es || h.descripcion}</p>
              ${h.evidencia?.puntaje_prioridad != null ? `<small>${h.evidencia.naturaleza === 'contexto' ? 'Contexto' : 'Control'} · ${Number(h.evidencia.puntaje_prioridad)} puntos</small>` : ''}
              ${h.evidencia?.detalle_contexto ? `<details><summary>Ver variaciones originales (${h.evidencia.detalle_contexto.length})</summary><ul>${h.evidencia.detalle_contexto.map(x => `<li>${escapeHtmlUnaVez(x.descripcion)}</li>`).join('')}</ul></details>` : ''}
              <details><summary>Detalles del control</summary><small class="hallazgo-meta">Tipo: ${h.tipo_evidencia || "-"} · Señal: ${h.limites?.tipo_senal || h.evidencia?.tipo_senal || "institucional"} · Incertidumbre: ${h.incertidumbre || "media"} · Alcance: ${h.alcance || "agregado"}</small></details>
              ${botonOrigenHallazgo(h)}
              ${evidencia.length ? `<div class="hallazgo-evidencia">${evidencia.map((x) => `<span>${x}</span>`).join("")}</div>` : ""}
              ${h.limites?.contexto_tecnico ? `<p class="hint"><strong>Contexto técnico (conciliador):</strong> ${h.limites.contexto_tecnico}</p>` : ""}
              ${renderRespuestaSenal(h)}
            </div>
          </div>
        </div>`;
      })
      .join("")}${hallazgos.length > 20 ? "</details>" : ""}${revision?.casos ? "</details>" : ""}`;
  document.querySelectorAll(".hallazgo-check").forEach((check) => {
    check.addEventListener("change", actualizarControlesReporte);
  });
  el.querySelectorAll("[data-respuesta]").forEach((btn) => btn.addEventListener("click", responderSenal));
  document.getElementById("btn-reporte-todos").addEventListener("click", () => setSeleccionReporte(true));
  document.getElementById("btn-reporte-ninguno").addEventListener("click", () => setSeleccionReporte(false));
  document.getElementById("btn-descargar-reporte").addEventListener("click", descargarReporteSeleccionado);
  el.querySelectorAll("[data-reporte-formato]").forEach((btn) => btn.addEventListener("click", descargarReporteSeleccionado));
  document.getElementById("btn-registrar-aprendizaje-hallazgo")?.addEventListener("click", registrarAprendizajeSeleccionado);
  el.querySelector('[data-comparar-base]')?.addEventListener('click', async () => {
    const base = Number(el.querySelector('[data-base-id]').value);
    if (!Number.isInteger(base) || base < 1) { toast('Indicá el número del informe base.', true); return; }
    try {
      const actual = Number(el.querySelector('[data-comparar-base]').dataset.informe);
      const delta = await apiFetch(`/informes/${actual}/comparacion?base_id=${base}`);
      el.querySelector('[data-delta]').innerHTML = renderDeltaCorridas(delta);
    } catch (e) { toast(e.message, true); }
  });
  actualizarControlesReporte();
}

async function registrarAprendizajeSeleccionado() {
  const ids = Array.from(state.reporteSeleccion);
  const tipo = document.getElementById("aprendizaje-tipo")?.value || "criterio_metodologico";
  const titulo = document.getElementById("aprendizaje-titulo")?.value.trim();
  const contenido = document.getElementById("aprendizaje-hallazgo-contenido")?.value.trim();
  if (!titulo || !contenido) {
    toast("Completá título y aprendizaje antes de guardar", true);
    return;
  }
  const boton = document.getElementById("btn-registrar-aprendizaje-hallazgo");
  if (boton?.disabled) return;
  const aviso = document.getElementById("calibracion-confirmacion");
  if (boton) boton.disabled = true;
  if (aviso) { aviso.hidden = false; aviso.textContent = "Guardando aporte…"; }
  try {
    await apiFetch("/aprendizaje", {
      method: "POST",
      body: JSON.stringify({
        tipo,
        titulo,
        contenido,
        informe_id: state.detalleId,
        hallazgo_ids: ids,
      }),
    });
    if (document.getElementById("aprendizaje-titulo").value.trim() === titulo) document.getElementById("aprendizaje-titulo").value = "";
    if (document.getElementById("aprendizaje-hallazgo-contenido").value.trim() === contenido) document.getElementById("aprendizaje-hallazgo-contenido").value = "";
    state.aprendizaje = null;
    if (aviso) aviso.textContent = `Guardado: «${titulo}». Quedó como propuesta en la memoria compartida de calibración, pendiente de validación de administración. No cambia automáticamente el sistema. Para corregirlo, registrá un nuevo aporte que identifique el anterior.`;
    toast("Aporte de calibración guardado");
  } catch (e) {
    if (aviso) aviso.textContent = "No se pudo confirmar el registro. Conservamos el texto; revisá Calibración antes de reenviarlo para evitar duplicados. " + e.message;
    toast("No se pudo registrar el aprendizaje: " + e.message, true);
  } finally {
    if (boton) boton.disabled = false;
  }
}

function renderExploracionSemantica(d, datosEscapados = false) {
  const textoSeguro = datosEscapados ? value => String(value ?? "") : escapeHtml;
  const resultado = d.devolucion?.cobertura?.exploracion_semantica;
  let panel = document.getElementById("exploracion-semantica");
  if (!panel) {
    panel = document.createElement("section");
    panel.id = "exploracion-semantica";
    panel.className = "card";
    const ancla = document.getElementById("lista-hallazgos");
    if (ancla) ancla.after(panel);
  }
  panel.hidden = !resultado;
  if (!resultado) return;
  const hs = resultado.hallazgos || [];
  panel.style.overflowWrap = "anywhere";
  panel.innerHTML = `<h3>Observaciones exploratorias de contexto (IA) · ${hs.length}</h3>
    <p>Independientes de los controles determinísticos. Requieren revisión humana; no certifican errores.</p>
    <p>${textoSeguro(resultado.titulo_estado || resultado.estado.replaceAll("_", " "))}. ${textoSeguro(resultado.limites || "")}</p>
    ${(resultado.modelos || []).map(m => `<p><strong>${textoSeguro(m.modelo)}</strong>: ${m.elementos_cubiertos ?? (m.respondio ? m.elementos_enviados : 0)}/${m.elementos_totales ?? "?"} elementos con salida válida; ${m.bloques_cubiertos ?? (m.respondio ? m.bloques_enviados : 0)}/${m.bloques_totales ?? "?"} bloques. Enviados: ${m.elementos_enviados ?? 0} elementos. ${m.evaluada ? "Estrategia completada, incluida comparación transversal" : "Exploración no completada"}.</p>
    ${!m.evaluada && m.hipotesis_conservadas ? `<p class="hint">Salida parcial utilizable: ${Number(m.hipotesis_conservadas)} hipótesis conservadas. No acredita cobertura completa de los elementos enviados.</p>` : ""}
    ${(m.motivos || []).map(x => `<p class="hint">Causa: ${textoSeguro(x)}</p>`).join("")}
    ${m.llamadas?.length ? `<details><summary>Diagnóstico por intento</summary>${m.llamadas.map(l => `<p>${textoSeguro(l.fase || "interpretación")} ${textoSeguro(l.lote || "")} · intento ${l.intento}: ${textoSeguro(l.status)}; ${textoSeguro(l.error_type || "sin error")}; HTTP ${l.http_status ?? "no informado"}; ${l.latency ?? "?"} s; entrada ${l.input_tokens ?? "tokens no informados"} / ${l.input_elements} elementos; salida ${l.output_received ? "recibida" : "no recibida"}; parseo ${textoSeguro(l.parse_status)}. ${textoSeguro(l.discard_reason || "")}</p>`).join("")}</details>` : ""}`).join("")}
    ${hs.map(h => `<article class="hallazgo"><strong>${textoSeguro(h.tipo)} · ${textoSeguro(h.modelo)} · pendiente de revisión humana</strong>
    <p>${textoSeguro(h.explicacion)}</p><ul>${h.evidencia_comparativa.map(e => `<li>${textoSeguro(e.archivo)} / ${textoSeguro(e.hoja)} / ${textoSeguro(e.celda || "nombre de hoja")}: «${textoSeguro(e.texto)}»</li>`).join("")}</ul>
    <p>Explicación alternativa: ${textoSeguro(h.alternativa)}</p></article>`).join("")}`;
}

function renderTriangulacion(d) {
  renderExploracionSemantica(d, true);
  const el = document.getElementById("triangulacion-body");
  const bloques = [];
  const estadosModelos = Array.isArray(d.modelos_consultados) ? d.modelos_consultados : [];
  const resumenIA = document.getElementById("resumen-apoyo-ia");
  const sinSenales = !(d.hallazgos || []).length;
  if (resumenIA) resumenIA.textContent = sinSenales && estadosModelos.length
    ? "No había señales para interpretar. La exploración del libro y su cobertura se informan aparte."
    : estadosModelos.length
    ? `Apoyo de IA: ${estadosModelos.filter(x => x.estado === "respondio").length} de ${estadosModelos.length} modelos devolvieron una lectura de las señales utilizable; la exploración del libro se informa aparte. Ver detalles en «Cómo se hizo el control».`
    : "Sin lecturas de IA registradas para este informe. Consultá los controles y su cobertura.";
  if (estadosModelos.length) {
    bloques.push(
      `<p><strong>Modelos seleccionados y resultado:</strong></p><ul class="model-status-list">` +
      estadosModelos.map((item) => {
        const nombre = NOMBRE_MODELO_PROGRESO[item.modelo] || item.modelo;
        const respondio = item.estado === "respondio";
        return `<li class="${respondio ? "ok" : "error"}"><strong>${escapeHtml(nombre)}</strong>: ${escapeHtml(item.detalle || (respondio ? "Respondió." : "No respondió."))}</li>`;
      }).join("") + `</ul>`
    );
  }
  if (d.coincidencias.length) {
    bloques.push(`<p><strong>Coincidencias entre modelos:</strong></p><ul>${d.coincidencias.map((c) => `<li>${c}</li>`).join("")}</ul>`);
  }
  if (d.divergencias.length) {
    bloques.push(`<p><strong>Divergencias entre modelos:</strong></p><ul>${d.divergencias.map((c) => `<li>${c}</li>`).join("")}</ul>`);
  }
  if (d.hallazgos_singulares.length) {
    bloques.push(
      `<p><strong>Lectura por modelo:</strong></p>` +
      d.hallazgos_singulares
        .map((hs) => `<div class="hallazgo"><div class="lente-tag">${hs.modelo} · confianza: ${hs.confianza || "-"}</div><p>${hs.lectura || "-"}</p></div>`)
        .join("")
    );
  }
  const alcances = d.devolucion?.cobertura?.manifiesto?.modelos || [];
  for (const m of alcances) {
    const enviados = m.alcance_ia?.hallazgos_enviados;
    const total = m.alcance_ia?.total_hallazgos;
    if (Number.isFinite(enviados) && Number.isFinite(total) && total > 0) bloques.push(`<p>${escapeHtml(m.proveedor)}: lectura de ${enviados} de ${total} señales, con evidencia abreviada. El informe conserva todos los resultados.</p>`);
  }
  el.innerHTML = bloques.length ? bloques.join("") : `<div class="empty-state">No hubo modelos consultados porque no se encontraron señales para interpretar.</div>`;
}

function etiquetaEstadoCertificacion(estado) {
  return {
    en_revision: "En revisión",
    con_observaciones: "Con observaciones",
    lista_para_emision: "Apto para instancia humana de decisión",
    sellada: "Sellada",
    reemplazada: "Reemplazada",
  }[estado] || estado || "Sin iniciar";
}

function claseEstadoControl(estado) {
  return estado === "conforme" ? "ok" : estado === "observado" ? "observado" : "pendiente";
}

async function cargarCertificacionR1(proyectoId, containerId = "proyecto-r1-panel") {
  const panel = document.getElementById(containerId);
  if (!panel || !proyectoId) return;
  try {
    const evaluacion = await apiFetch(`/certificaciones/proyectos/${proyectoId}/evaluacion`);
    renderCertificacionR1(panel, evaluacion, proyectoId, containerId);
  } catch (e) {
    panel.innerHTML = `<div class="empty-state">No se pudo cargar R-1: ${escapeHtml(e.message)}</div>`;
  }
}

function renderCertificacionR1(panel, evaluacion, proyectoId, containerId) {
  // R-1 lo inicia el equipo docente: a quien participa no se le ofrece si no hay una evaluación abierta.
  const tarjeta = panel.closest(".project-r1-card");
  if (tarjeta) tarjeta.hidden = !evaluacion && !esAdmin();
  if (!evaluacion && !esAdmin()) {
    panel.innerHTML = `<div class="empty-state">R-1 lo inicia el equipo docente cuando un proyecto lo amerita. No hace falta para entregar.</div>`;
    return;
  }
  if (!evaluacion) {
    panel.innerHTML = `
    <div class="cert-intro"><strong>La evaluación todavía no fue iniciada.</strong><p>Iniciarla crea una instantánea del proyecto y los controles de la versión vigente del protocolo. No emite ni aprueba nada automáticamente.</p></div>
      ${esLector() ? "" : '<button type="button" class="btn btn-primary r1-start">Iniciar protocolo R-1</button>'}`;
    panel.querySelector(".r1-start")?.addEventListener("click", async () => {
      try {
        await apiFetch(`/certificaciones/proyectos/${proyectoId}/evaluacion`, { method: "POST" });
        toast("Evaluación R-1 iniciada");
        await cargarCertificacionR1(proyectoId, containerId);
      } catch (e) { toast("No se pudo iniciar R-1: " + e.message, true); }
    });
    return;
  }
  const resultados = evaluacion.resultados || [];
  const conformes = resultados.filter((r) => r.aplica && r.estado === "conforme").length;
  const pendientes = resultados.filter((r) => r.aplica && r.estado !== "conforme").length;
  const etiquetasConclusion = { ia_justificada: "La IA está justificada", automatizacion_simple: "Conviene una automatización simple", mejora_de_proceso: "Conviene mejorar el proceso sin IA", no_implementar: "No corresponde implementar tecnología", informacion_insuficiente: "Información insuficiente" };
  panel.innerHTML = `
    <div class="cert-head"><div><span class="badge ${evaluacion.estado === "lista_para_emision" || evaluacion.estado === "sellada" ? "badge-ok" : "badge-media"}">${escapeHtml(etiquetaEstadoCertificacion(evaluacion.estado))}</span><strong>${escapeHtml(evaluacion.protocolo.nombre)} · ${escapeHtml(evaluacion.protocolo.version)}</strong></div><small>${conformes} conformes · ${pendientes} pendientes</small></div>
    ${evaluacion.sello ? `<div class="seal-card seal-${escapeHtml(evaluacion.sello.estado)}"><span class="seal-mark">R-1</span><div><strong>Sello ${escapeHtml(evaluacion.sello.estado)}</strong><p>${escapeHtml(evaluacion.sello.resumen_alcance)}</p><a href="/verificar-sello/${encodeURIComponent(evaluacion.sello.identificador_publico)}" target="_blank" rel="noopener">Abrir verificación pública</a>${esAdmin() && evaluacion.sello.estado === "vigente" ? '<div><button type="button" class="btn btn-secondary btn-mini r1-revoke">Revocar constancia</button></div>' : ""}</div></div>` : ""}
    <div class="r1-control-list">
      ${resultados.map((r) => `<article class="r1-control ${claseEstadoControl(r.estado)}" data-resultado-id="${r.id}">
        <div><span>${escapeHtml(r.control.codigo)}</span><strong>${escapeHtml(r.control.nombre)}</strong><em>${escapeHtml(r.aplica ? r.estado : "no aplicable")}</em></div>
        <p>${escapeHtml(r.control.descripcion)}</p>
        ${r.control.evidencia_requerida?.campos?.length ? `<p><strong>Evidencia mínima:</strong> ${r.control.evidencia_requerida.campos.map(escapeHtml).join(" · ")}</p>` : ""}
        ${r.observacion ? `<p><strong>Observación:</strong> ${escapeHtml(r.observacion)}</p>` : ""}
        ${r.accion_requerida ? `<p><strong>Acción:</strong> ${escapeHtml(r.accion_requerida)}</p>` : ""}
        ${!r.aplica ? `<p><strong>Justificación:</strong> ${escapeHtml(r.justificacion_aplicabilidad || "-")}</p>` : ""}
        <small>${contar((r.evidencias || []).length, "evidencia")}</small>
        <div class="actions-row compact-actions">
          ${!esLector() && !evaluacion.sello ? '<button type="button" class="cert-add-evidence btn btn-secondary btn-mini">Aportar evidencia</button>' : ""}
          ${esAdmin() && !evaluacion.sello ? '<button type="button" class="r1-review btn btn-secondary btn-mini">Revisar control</button>' : ""}
        </div>
      </article>`).join("")}
    </div>
    <section class="cert-r1-conclusion"><strong>Conclusión humana sobre la necesidad de IA</strong><p>${escapeHtml(etiquetasConclusion[evaluacion.conclusion_r1] || "Todavía no fue registrada.")}</p>${evaluacion.fundamento_conclusion_r1 ? `<p>${escapeHtml(evaluacion.fundamento_conclusion_r1)}</p>` : ""}${esAdmin() && !evaluacion.sello ? '<button type="button" class="btn btn-secondary btn-mini r1-conclusion">Registrar conclusión</button>' : ""}</section>
    ${esAdmin() && evaluacion.estado === "lista_para_emision" && !evaluacion.sello ? '<div class="cert-issue"><button type="button" class="btn btn-primary r1-issue">Emitir constancia R-1</button><p>La preparación queda sujeta a la instancia humana correspondiente; no equivale a aprobación automática del proyecto.</p></div>' : ""}
    <p class="cert-disclaimer">R-1 acredita preparación documentada bajo el protocolo indicado. Puede concluir que falta información o que IA no es la alternativa apropiada.</p>`;
  panel.querySelectorAll(".cert-add-evidence").forEach((btn) => btn.addEventListener("click", async (event) => {
    const resultadoId = Number(event.currentTarget.closest(".r1-control").dataset.resultadoId);
    const descripcion = window.prompt("Describí la evidencia y qué demuestra:");
    if (!descripcion?.trim()) return;
    const referencia = window.prompt("Referencia o enlace (opcional):") || null;
    try {
      await apiFetch(`/certificaciones/resultados/${resultadoId}/evidencias`, { method: "POST", body: JSON.stringify({ tipo: "aporte_proyecto", descripcion: descripcion.trim(), referencia }) });
      toast("Evidencia incorporada");
      await cargarCertificacionR1(proyectoId, containerId);
    } catch (e) { toast("No se pudo aportar evidencia: " + e.message, true); }
  }));
  panel.querySelectorAll(".r1-review").forEach((btn) => btn.addEventListener("click", async (event) => {
    const card = event.currentTarget.closest(".r1-control");
    const resultadoId = Number(card.dataset.resultadoId);
    const actual = resultados.find((r) => r.id === resultadoId);
    const estado = window.prompt("Estado: conforme, observado o no_evaluable", actual.estado);
    if (!estado || !["conforme", "observado", "no_evaluable"].includes(estado.trim())) return;
    const aplicaTexto = window.prompt("¿El control aplica? Escribí sí o no", actual.aplica ? "sí" : "no");
    if (!aplicaTexto) return;
    const aplica = !["no", "n"].includes(aplicaTexto.trim().toLowerCase());
    const justificacion = aplica ? null : window.prompt("Justificá por qué no aplica:", actual.justificacion_aplicabilidad || "");
    const observacion = estado.trim() === "observado" ? window.prompt("Observación:", actual.observacion || "") : (actual.observacion || null);
    const accion = window.prompt("Acción requerida o siguiente paso (opcional):", actual.accion_requerida || "") || null;
    try {
      await apiFetch(`/certificaciones/resultados/${resultadoId}`, { method: "PUT", body: JSON.stringify({ aplica, estado: estado.trim(), justificacion_aplicabilidad: justificacion || null, observacion: observacion || null, accion_requerida: accion }) });
      toast("Control R-1 reevaluado");
      await cargarCertificacionR1(proyectoId, containerId);
    } catch (e) { toast("No se pudo revisar el control: " + e.message, true); }
  }));
  panel.querySelector(".r1-issue")?.addEventListener("click", async () => {
    const resumen = window.prompt("Alcance del análisis (qué se revisó realmente):", "Proyecto evaluado bajo el protocolo de Preparación para IA Responsable R-1.");
    if (!resumen?.trim()) return;
    const limites = window.prompt("Análisis excluidos -lista no exhaustiva-, separados por punto y coma (opcional):") || "";
    try {
      await apiFetch(`/certificaciones/evaluaciones/${evaluacion.id}/emitir`, { method: "POST", body: JSON.stringify({ alcance_del_analisis: resumen.trim(), excluidos_del_analisis: limites.split(";").map((x) => x.trim()).filter(Boolean) }) });
      toast("Constancia R-1 emitida");
      await cargarCertificacionR1(proyectoId, containerId);
    } catch (e) { toast("No se pudo emitir R-1: " + e.message, true); }
  });
  panel.querySelector(".r1-conclusion")?.addEventListener("click", async () => {
    const conclusion = window.prompt("Conclusión: ia_justificada, automatizacion_simple, mejora_de_proceso, no_implementar o informacion_insuficiente", evaluacion.conclusion_r1 || "informacion_insuficiente");
    if (!conclusion || !Object.prototype.hasOwnProperty.call(etiquetasConclusion, conclusion.trim())) return;
    const fundamento = window.prompt("Fundamento de la conclusión humana:", evaluacion.fundamento_conclusion_r1 || "");
    if (!fundamento?.trim() || fundamento.trim().length < 20) return;
    try {
      await apiFetch(`/certificaciones/evaluaciones/${evaluacion.id}/conclusion-r1`, { method: "PUT", body: JSON.stringify({ conclusion: conclusion.trim(), fundamento: fundamento.trim() }) });
      toast("Conclusión R-1 registrada");
      await cargarCertificacionR1(proyectoId, containerId);
    } catch (e) { toast("No se pudo registrar la conclusión: " + e.message, true); }
  });
  panel.querySelector(".r1-revoke")?.addEventListener("click", async () => {
    const motivo = window.prompt("Motivo de la revocación (quedará registrado):");
    if (!motivo?.trim() || motivo.trim().length < 10) return;
    try {
      await apiFetch(`/certificaciones/sellos/${evaluacion.sello.id}/revocar`, { method: "POST", body: JSON.stringify({ motivo: motivo.trim() }) });
      toast("Constancia R-1 revocada");
      await cargarCertificacionR1(proyectoId, containerId);
    } catch (e) { toast("No se pudo revocar: " + e.message, true); }
  });
}

function progresoAgregar(claseTexto, icono, html) {
  const log = document.getElementById("progreso-log");
  const li = document.createElement("li");
  li.className = claseTexto;
  li.innerHTML = `<span class="progreso-icono">${icono}</span><span>${html}</span>`;
  log.appendChild(li);
  log.scrollTop = log.scrollHeight;
}

const NOMBRE_MODELO_PROGRESO = { claude: "Claude", gpt: "GPT", gemini: "Gemini", renderix: "Renderix", deepseek: "DeepSeek", llama: "Llama" };

function progresoEvento(evento, faltantes) {
  if (evento.tipo === "lente") {
    if (evento.cantidad > 0) {
      progresoAgregar("ok", "●", `${escapeHtml(evento.nombre)}: ${contar(evento.cantidad, "hallazgo")}`);
    } else {
      progresoAgregar("vacio", "○", `${escapeHtml(evento.nombre)}: sin señales`);
      faltantes.sinSenales.push(evento.nombre);
    }
  } else if (evento.tipo === "control_solicitado") {
    const noEvaluado = evento.estado === "no_evaluable";
    progresoAgregar(
      noEvaluado ? "error" : "ok",
      noEvaluado ? "!" : "●",
      `${escapeHtml(evento.nombre)}: ${escapeHtml(String(evento.estado || "").replaceAll("_", " "))} <span class="progreso-detalle">${escapeHtml(evento.detalle || "")}</span>`
    );
  } else if (evento.tipo === "modelo") {
    const nombre = NOMBRE_MODELO_PROGRESO[evento.modelo] || evento.modelo;
    if (evento.ok) {
      progresoAgregar("ok", "●", `${escapeHtml(nombre)}: respondió`);
    } else {
      progresoAgregar("error", "✕", `${escapeHtml(nombre)}: <span class="progreso-detalle">${escapeHtml(evento.error || "no disponible")}</span>`);
      faltantes.modelos.push(`${nombre} (${evento.error || "no disponible"})`);
    }
  } else if (evento.tipo === "convergencia") {
    progresoAgregar("ok", "●", `Convergencia multilente: ${contar(evento.grupos, "grupo detectado", "grupos detectados")}`);
  } else if (evento.tipo === "cobertura") {
    const falta = document.getElementById("progreso-falta");
    const partes = [];
    if (faltantes.sinSenales.length) partes.push(`Lentes sin señales: ${faltantes.sinSenales.join(", ")}.`);
    if (faltantes.modelos.length) partes.push(`Modelos que no respondieron: ${faltantes.modelos.join("; ")}.`);
    const excluidas = evento.cobertura?.columnas_excluidas || [];
    if (excluidas.length) partes.push(`Columnas excluidas por sensibles: ${excluidas.join(", ")}.`);
    if (partes.length) {
      document.getElementById("progreso-falta-texto").textContent = partes.join(" ");
      falta.style.display = "block";
    }
  } else if (evento.tipo === "error") {
    progresoAgregar("error", "✕", `Error: ${escapeHtml(evento.detalle || "sin detalle")}`);
  }
}

async function ejecutarAnalisisStream() {
  const btn = document.getElementById("btn-analizar");
  if (!puedeOperarInformes()) {
    toast("Tu rol es de solo lectura: no puede analizar informes.", true);
    btn.disabled = false;
    btn.textContent = "Analizar informe";
    return;
  }
  const modelosSeleccionados = Array.from(document.querySelectorAll(".modelo-check:checked")).map((el) => el.value);
  if (modelosSeleccionados.length === 0) {
    toast("Elegí al menos un modelo para triangular", true);
    btn.disabled = false;
    btn.textContent = "Analizar informe";
    return;
  }
  try {
    const payload = { modelos: modelosSeleccionados };
    if (state.currentUser?.email_notificaciones) payload.notify_email = state.currentUser.email_notificaciones;
    const encolar = () => apiFetch(`/jobs/informes/${state.detalleId}/analizar`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (state.detalle?.saneamiento?.interpretacion_previa?.estado !== "confirmada"
        && state.detalle?.saneamiento?.origen_interpretacion === "datos_estructurados") {
      await window.prepararYConfirmarInforme(new FormData(), async (form) => {
        const accion = form.get("interpretacion_accion") || "preparar";
        const propuesta = await apiFetch(`/informes/${state.detalleId}/interpretacion`, {
          method: "POST", body: JSON.stringify({ accion, revision: Number(form.get("interpretacion_revision")) || undefined,
            correcciones: JSON.parse(form.get("interpretacion_correcciones") || "{}") }),
        });
        return accion === "confirmar" ? encolar() : propuesta;
      });
    } else {
      await encolar();
    }
    toast(payload.notify_email ? "Informe en cola. Te avisará por correo al finalizar." : "Informe en cola de análisis");
    await refrescarDetalle();
  } catch (e) {
    toast("No se pudo encolar el informe: " + e.message, true);
    btn.disabled = false;
    btn.textContent = "Analizar informe";
  }
}

document.getElementById("btn-analizar").addEventListener("click", () => {
  const btn = document.getElementById("btn-analizar");
  btn.disabled = true;
  btn.textContent = "Analizando…";
  ejecutarAnalisisStream();
});

const btnRecargarAprendizaje = document.getElementById("btn-recargar-aprendizaje");
if (btnRecargarAprendizaje) {
  btnRecargarAprendizaje.addEventListener("click", cargarAprendizaje);
}



// ---------- casos compartidos de Gobernanza Incubadora ----------

function colorCaso(caso, index = 0) {
  const tema = String(caso?.etiqueta || "").toLowerCase();
  const coloresPorTema = [
    { claves: ["atención", "atencion", "soporte"], color: "azul" },
    { claves: ["actos", "normativa", "juríd", "jurid"], color: "verde" },
    { claves: ["contrat"], color: "coral" },
    { claves: ["gestión documental", "gestion documental", "expediente"], color: "dorado" },
    { claves: ["presupuesto"], color: "petroleo" },
    { claves: ["riesgos", "control"], color: "violeta" },
    { claves: ["información estratégica", "informacion estrategica"], color: "petroleo" },
    { claves: ["gobernanza incubadora"], color: "azul" },
  ];
  const encontrado = coloresPorTema.find((item) => item.claves.some((clave) => tema.includes(clave)));
  if (encontrado) return encontrado.color;
  const colores = ["azul", "verde", "dorado", "coral", "violeta", "petroleo"];
  return colores[index % colores.length];
}

function actividadCasoLabel(caso) {
  const actividad = Number(caso.actividad || 0);
  if (caso.entrega_final) return "con entrega";
  if (Number(caso.intervenciones_docente || 0) > 0) return "con devolución docente";
  if (actividad >= 12) return "conversación intensa";
  if (actividad >= 5) return "en desarrollo";
  return "idea inicial";
}

function caseProgress(caso) {
  if (caso.entrega_final) return 100;
  const actividad = Math.min(Number(caso.actividad || 0), 14);
  const docente = Math.min(Number(caso.intervenciones_docente || 0), 4);
  const contexto = caso.bajada ? 18 : 0;
  const diagnostico = caso.diagnostico?.necesita_segunda_vuelta ? 0 : 12;
  return Math.min(92, 18 + contexto + actividad * 4 + docente * 7 + diagnostico);
}

function caseDiagnosticText(caso) {
  const diag = caso.diagnostico || {};
  if (caso.entrega_final) return "Caso con entrega para revisar como evidencia final.";
  if (diag.necesita_segunda_vuelta) return "Conviene volver sobre la formulación del problema.";
  if (Number(caso.intervenciones_docente || 0) > 0) return "Ya tuvo intercambio docente: buen caso para observar evolución.";
  if (Number(caso.actividad || 0) >= 5) return "Tiene conversación suficiente para mirar cómo se fue afinando.";
  return "Todavía está en una primera definición.";
}

function renderFiltrosCasos(casos) {
  const contenedor = document.getElementById("casos-proyectos-filtros");
  if (!contenedor) return;
  const etiquetas = Array.from(new Set(casos.map((c) => c.etiqueta).filter(Boolean))).sort((a, b) => a.localeCompare(b, "es"));
  const actual = state.proyectoCasosFiltro;
  const botones = [{ etiqueta: "Todas las líneas", valor: "" }, ...etiquetas.map((e) => ({ etiqueta: e, valor: e }))];
  contenedor.innerHTML = botones.map((item) => {
    const activos = item.valor ? casos.filter((c) => c.etiqueta === item.valor).length : casos.length;
    const active = actual === item.valor ? " active" : "";
    return `<button type="button" class="case-filter${active}" data-caso-filtro="${escapeHtml(item.valor)}">${escapeHtml(item.etiqueta)} <span>${activos}</span></button>`;
  }).join("");
  contenedor.querySelectorAll("[data-caso-filtro]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.proyectoCasosFiltro = btn.dataset.casoFiltro || "";
      reiniciarPaginaCasos();
      renderCasosProyectos(state.proyectoCasos);
    });
  });
}


function renderFichaVotacion(caso) {
  const ficha = caso.ficha_votacion || {};
  const criterios = Array.isArray(ficha.criterios) ? ficha.criterios : [];
  const item = (label, value) => `
    <div class="case-vote-item">
      <strong>${escapeHtml(label)}</strong>
      <span>${escapeHtml(value || "A precisar")}</span>
    </div>`;
  const chips = criterios.length ? `
    <div class="case-vote-checks" aria-label="Criterios detectados">
      ${criterios.map((c) => `<span class="${c.ok ? "ok" : "pending"}">${c.ok ? "✓" : "•"} ${escapeHtml(c.label)}</span>`).join("")}
    </div>` : "";
  return `
    <div class="case-vote-brief">
      <div class="case-vote-head">
        <strong>Para orientar el voto</strong>
        <span>${escapeHtml(ficha.madurez || "Madurez a estimar")}</span>
      </div>
      ${renderProjectSkillChart(caso.diagnostico?.habilidades, { compact: true })}
      ${item("Problema", ficha.problema)}
      ${item("Valor público", ficha.valor_publico)}
      ${item("Datos", ficha.datos)}
      ${item("Rol de la IA", ficha.rol_ia)}
      ${item("Supervisión", ficha.supervision)}
      ${item("Riesgo/límite", ficha.riesgos)}
      ${item("Indicador", ficha.indicador)}
      ${chips}
    </div>`;
}

function renderDetalleCaso(caso) {
  const bloque = (clave, titulo, texto, vacio) => `<section class="case-full-section" data-caso-seccion="${clave}"><h4 tabindex="-1">${escapeHtml(titulo)}</h4>
    <div class="case-full-text">${escapeHtml(texto || vacio)}</div></section>`;
  return `<div class="case-reading-tools" aria-label="Herramientas de lectura">
    <div class="case-reading-actions"><button type="button" class="btn btn-secondary btn-mini" data-caso-ir="situacion">Ir a la situación</button>
    <button type="button" class="btn btn-secondary btn-mini" data-caso-ir="propuesta">Ir a la propuesta</button>
    <button type="button" class="btn btn-secondary btn-mini" data-caso-cerrar>Cerrar trabajo</button></div>
    <label>Buscar en este trabajo<input type="search" maxlength="200" data-caso-buscar placeholder="Palabra o frase"></label>
    <p class="hint">Enter: siguiente coincidencia. Mayús + Enter: anterior. La búsqueda distingue tildes.</p>
    <div class="case-reading-actions"><span role="status" aria-live="polite" data-caso-resultados>Escribí para buscar en el texto.</span>
    <button type="button" class="btn btn-secondary btn-mini" data-caso-anterior disabled>Anterior coincidencia</button>
    <button type="button" class="btn btn-secondary btn-mini" data-caso-siguiente disabled>Siguiente coincidencia</button></div>
    </div><p class="hint">Texto guardado por el participante. Puede estar en elaboración; no es una validación de la IA ni una aprobación docente.</p>
    <p><strong>${escapeHtml(estadoCasoLegible(caso.estado))}</strong>${caso.actualizado_en ? ` · Actualizado: ${escapeHtml(fmtFecha(caso.actualizado_en))}` : ""}</p>
    ${bloque("situacion", "Situación planteada", caso.situacion, "Todavía no hay una situación escrita.")}
    ${bloque("propuesta", "Propuesta guardada completa", caso.propuesta, "Todavía no hay una propuesta guardada para leer.")}
    <button type="button" class="btn btn-secondary" data-caso-cerrar>Cerrar trabajo y volver a la tarjeta</button>`;
}

function resaltarTextoCaso(texto, consulta) {
  const buscar = consulta.trim();
  if (!buscar) return escapeHtml(texto);
  const patron = new RegExp(buscar.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "giu");
  let salida = "", inicio = 0;
  for (const coincidencia of texto.matchAll(patron)) {
    salida += escapeHtml(texto.slice(inicio, coincidencia.index)) + `<mark tabindex="-1">${escapeHtml(coincidencia[0])}</mark>`;
    inicio = coincidencia.index + coincidencia[0].length;
  }
  return salida + escapeHtml(texto.slice(inicio));
}

function activarLecturaCaso(details, contenido) {
  const buscar = contenido.querySelector("[data-caso-buscar]");
  const resultado = contenido.querySelector("[data-caso-resultados]");
  const anterior = contenido.querySelector("[data-caso-anterior]");
  const siguiente = contenido.querySelector("[data-caso-siguiente]");
  const originales = Array.from(contenido.querySelectorAll(".case-full-text"), el => [el, el.textContent]);
  let marcas = [], actual = -1;
  const informar = () => {
    resultado.textContent = !buscar.value.trim() ? "Escribí para buscar en el texto." : !marcas.length ? "No hay coincidencias." : actual < 0 ? `${marcas.length} coincidencias.` : `${actual + 1} de ${marcas.length} coincidencias.`;
    anterior.disabled = siguiente.disabled = !marcas.length;
  };
  const mover = paso => {
    if (!marcas.length) return;
    if (actual >= 0) marcas[actual].classList.remove("case-match-current");
    actual = actual < 0 ? (paso > 0 ? 0 : marcas.length - 1) : (actual + paso + marcas.length) % marcas.length;
    marcas[actual].classList.add("case-match-current");
    marcas[actual].scrollIntoView({block: "center"});
    informar();
  };
  buscar.addEventListener("input", () => {
    originales.forEach(([el, texto]) => { el.innerHTML = resaltarTextoCaso(texto, buscar.value); });
    marcas = Array.from(contenido.querySelectorAll(".case-full-text mark"));
    actual = -1;
    informar();
  });
  buscar.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); mover(e.shiftKey ? -1 : 1); }
  });
  anterior.addEventListener("click", () => mover(-1));
  siguiente.addEventListener("click", () => mover(1));
  contenido.querySelectorAll("[data-caso-ir]").forEach(btn => btn.addEventListener("click", () => {
    const titulo = contenido.querySelector(`[data-caso-seccion="${btn.dataset.casoIr}"] h4`);
    titulo.focus({preventScroll: true});
    titulo.scrollIntoView({block: "start"});
  }));
  contenido.querySelectorAll("[data-caso-cerrar]").forEach(btn => btn.addEventListener("click", () => {
    details.open = false;
    const resumen = details.querySelector("summary");
    resumen.focus({preventScroll: true});
    resumen.scrollIntoView({block: "center"});
  }));
}

async function cargarDetalleCaso(details) {
  if (!details.open || details.dataset.cargado || details.dataset.cargando) return;
  const contenido = details.querySelector("[data-caso-contenido]");
  details.dataset.cargando = "1";
  contenido.innerHTML = '<p role="status">Cargando el trabajo completo…</p>';
  try {
    const caso = await apiFetch(`/proyectos-ia/casos/${Number(details.dataset.casoDetalle)}`);
    contenido.innerHTML = renderDetalleCaso(caso);
    activarLecturaCaso(details, contenido);
    details.dataset.cargado = "1";
  } catch (e) {
    contenido.innerHTML = `<p role="status">No se pudo cargar el trabajo: ${escapeHtml(e.message)}</p><button type="button" class="btn btn-secondary btn-mini">Reintentar</button>`;
    contenido.querySelector("button").addEventListener("click", () => cargarDetalleCaso(details));
  } finally {
    delete details.dataset.cargando;
  }
}

function renderVotoCaso(caso) {
  if (state.actividadVotacion && !(state.actividadVotacion.proyectos_ids || []).includes(Number(caso.id))) {
    return '<p class="hint">Este proyecto no participa en la actividad de votación actual.</p>';
  }
  if (state.primeraVueltaCerrada) {
    const votos = Number(caso.votos_total || 0);
    return `<div class="case-vote-closed"><strong>${votos}</strong><span>${votos === 1 ? "voto en la primera vuelta" : "votos en la primera vuelta"}</span></div>`;
  }
  if (caso.es_propio) return `<span class="case-own">Tu proyecto</span>`;
  return `<label class="case-choice"><input type="radio" name="proyecto-voto" value="${caso.id}"
    ${state.votoSeleccionado === caso.id ? "checked" : ""} ${state.votoEnviando ? "disabled" : ""}>
    <span>Elegir${caso.mi_voto ? " · Tu voto actual" : ""}</span></label>`;
}

function renderPanelVoto() {
  const grid = document.getElementById("casos-proyectos-grid");
  let panel = document.getElementById("casos-panel-voto");
  if (!panel) {
    panel = document.createElement("section");
    panel.id = "casos-panel-voto";
    grid.before(panel);
  }
  if (state.primeraVueltaCerrada) { panel.replaceChildren(); return; }
  const caso = state.proyectoCasos.find(c => c.id === state.votoSeleccionado && !c.es_propio);
  if (!caso) { panel.replaceChildren(); return; }
  panel.innerHTML = `<form class="case-vote-form">
    <h3>${escapeHtml(caso.titulo || "Proyecto seleccionado")}</h3>
    <label for="voto-justificacion">Justificación</label>
    <textarea id="voto-justificacion" required minlength="40" maxlength="1200" ${state.votoEnviando ? "disabled" : ""}>${escapeHtml(state.votoBorrador || "")}</textarea>
    <div class="case-vote-actions"><small id="voto-contador"></small>
    <button type="submit" class="btn btn-primary" ${state.votoEnviando ? "disabled" : ""}>${state.votoEnviando ? "Guardando..." : state.miVoto ? "Actualizar voto" : "Votar"}</button></div>
    <p class="case-vote-status" role="status">${escapeHtml(state.votoEstado || (state.miVoto ? "El nuevo voto reemplazará al anterior. Su justificación quedará en el historial." : "Un voto activo por participante. Mínimo 40 caracteres."))}</p>
    <details id="voto-historial"><summary>Historial de votos</summary><div></div></details>
  </form>`;
  const campo = panel.querySelector("textarea");
  const contar = () => {
    state.votoBorrador = campo.value;
    panel.querySelector("#voto-contador").textContent = `${campo.value.trim().replace(/\s+/g, " ").length} / 1200 caracteres`;
  };
  campo.addEventListener("input", contar);
  contar();
  panel.querySelector("#voto-historial").addEventListener("toggle", async e => {
    if (!e.target.open) return;
    const contenido = e.target.querySelector("div");
    contenido.textContent = "Cargando historial...";
    try {
      const historial = await apiFetch("/proyectos-ia/votos/historial");
      contenido.innerHTML = historial.map(h => `<article><strong>Proyecto ${Number(h.proyecto_id)} · ${fmtFecha(h.creado_en)}</strong><p>${escapeHtml(h.detalle?.justificacion || "Este registro antiguo no conserva la justificación.")}</p>${h.detalle?.justificacion_anterior ? `<p>Justificación anterior: ${escapeHtml(h.detalle.justificacion_anterior)}</p>` : ""}</article>`).join("") || "Todavía no hay votos registrados.";
    } catch (error) { contenido.textContent = error.message; }
  });
  panel.querySelector("form").addEventListener("submit", e => { e.preventDefault(); enviarVotoProyecto(); });
}

async function enviarVotoProyecto() {
  if (state.votoEnviando) return;
  const proyectoId = state.votoSeleccionado;
  const justificacion = (state.votoBorrador || "").trim().replace(/\s+/g, " ");
  if (justificacion.length < 40) {
    state.votoEstado = "La justificación debe tener al menos 40 caracteres.";
    renderPanelVoto();
    return;
  }
  state.votoEnviando = true;
  renderCasosProyectos(state.proyectoCasos);
  try {
    const voto = await apiFetch("/proyectos-ia/votos", {
      method: "POST",
      body: JSON.stringify({ proyecto_id: Number(proyectoId), justificacion, actividad_id: state.actividadVotacion?.id }),
    });
    state.miVoto = voto;
    state.proyectoCasos.forEach(c => { c.mi_voto = c.id === voto.proyecto_id ? voto.justificacion : ""; });
    state.votoEstado = "Voto guardado.";
    toast("Voto justificado registrado.");
  } catch (e) {
    state.votoEstado = e.message;
    toast(e.message, true);
  } finally {
    state.votoEnviando = false;
    renderCasosProyectos(state.proyectoCasos);
  }
}

function filtrarCasosProyecto(casos, {tema = "", estado = "", busqueda = "", propio = false, enfocado = null} = {}) {
  const texto = normalizarBusqueda(busqueda);
  return casos.filter(c => (!tema || c.etiqueta === tema)
    && (!estado || c.estado === estado)
    && (!propio || c.es_propio)
    && (!enfocado || Number(c.id) === Number(enfocado))
    && normalizarBusqueda([c.titulo, c.organismo_area, c.etiqueta, c.bajada].join(" ")).includes(texto));
}

function estadoCasoLegible(estado) {
  return {en_proceso:"En elaboración", entregado:"Entregado · pendiente de revisión docente", revisado:"Con devolución docente"}[estado] || estado || "En elaboración";
}

const CASOS_POR_PAGINA = 12;

function reiniciarPaginaCasos() { state.casosLimite = CASOS_POR_PAGINA; }

function renderVerMasCasos(grid, quedan) {
  let pie = document.getElementById("casos-proyectos-mas");
  if (!pie) {
    pie = document.createElement("div");
    pie.id = "casos-proyectos-mas";
    pie.className = "casos-ver-mas";
    grid.insertAdjacentElement("afterend", pie);
  }
  if (quedan <= 0) { pie.hidden = true; pie.innerHTML = ""; return; }
  pie.hidden = false;
  pie.innerHTML = `<button type="button" class="btn btn-secondary">Ver más casos (${quedan === 1 ? "queda 1" : `quedan ${quedan}`})</button>`;
  pie.querySelector("button").addEventListener("click", () => {
    const desde = Math.max(CASOS_POR_PAGINA, Number(state.casosLimite) || CASOS_POR_PAGINA);
    state.casosLimite = desde + CASOS_POR_PAGINA;
    renderCasosProyectos(state.proyectoCasos);
    const primeraNueva = grid.querySelectorAll("article.case-card")[desde];
    if (primeraNueva) {
      primeraNueva.setAttribute("tabindex", "-1");
      primeraNueva.focus({ preventScroll: true });
    }
  });
}

function renderCasosProyectos(casos) {
  const grid = document.getElementById("casos-proyectos-grid");
  const resumen = document.getElementById("casos-proyectos-resumen");
  if (!grid) return;
  renderPanelVoto();
  renderFiltrosCasos(casos);
  const filtro = state.proyectoCasosFiltro;
  const busqueda = normalizarBusqueda(document.getElementById("buscar-casos")?.value || "");
  const propio = document.getElementById("solo-mi-caso")?.checked;
  const visibles = filtrarCasosProyecto(casos, {tema:filtro, estado:document.getElementById("estado-casos")?.value || "", busqueda, propio, enfocado:state.casoEnfocado});
  if (resumen) {
    const activos = visibles.filter((c) => Number(c.actividad || 0) >= 5).length;
    const conDocente = visibles.filter((c) => Number(c.intervenciones_docente || 0) > 0).length;
    const etiquetas = new Set(casos.map((c) => c.etiqueta).filter(Boolean));
    resumen.innerHTML = casos.length
      ? `<div><strong>${visibles.length}</strong><span>casos visibles</span></div><div><strong>${activos}</strong><span>con intercambio activo</span></div><div><strong>${conDocente}</strong><span>con intervención docente</span></div><div><strong>${etiquetas.size}</strong><span>líneas de trabajo</span></div>`
      : "Todavía no hay casos cargados para compartir.";
  }
  if (!casos.length) {
    grid.innerHTML = `<div class="empty-state">Todavía no hay proyectos con contexto cargado.</div>`;
    renderVerMasCasos(grid, 0);
    return;
  }
  if (!visibles.length) {
    grid.innerHTML = `<div class="empty-state">No hay proyectos que coincidan con estos filtros. Usá “Ver todos” para restablecer la lista.</div>`;
    renderVerMasCasos(grid, 0);
    return;
  }
  // De a CASOS_POR_PAGINA: un caso enfocado o buscado ya queda dentro de la lista filtrada.
  const limite = Math.max(CASOS_POR_PAGINA, Number(state.casosLimite) || CASOS_POR_PAGINA);
  const enPagina = visibles.slice(0, limite);
  grid.innerHTML = enPagina.map((caso, index) => {
    const progreso = caseProgress(caso);
    const estado = actividadCasoLabel(caso);
    return `
    <article id="caso-compartido-${Number(caso.id)}" class="case-card case-card-${colorCaso(caso, index)}">
      <div class="case-card-topline">
        <span class="case-chip">${escapeHtml(caso.etiqueta || "Gobernanza Incubadora")}</span>
        <span class="case-number">Caso ${caso.numero || index + 1}</span>
      </div>
      <h3>${escapeHtml(caso.titulo || "Caso en definición")}</h3>
      <p class="case-bajada">${escapeHtml(caso.bajada || "El participante todavía está precisando la situación de uso.")}</p>
      <details class="case-details" data-caso-detalle="${Number(caso.id)}"><summary>Ver trabajo completo</summary>
        <div data-caso-contenido></div>
        <details class="case-orientation"><summary>Ver ficha orientativa para comparar</summary>${renderFichaVotacion(caso)}</details>
      </details>
      ${renderVotoCaso(caso)}
      <div class="case-progress" aria-label="Avance estimado del caso">
        <span style="width:${progreso}%"></span>
      </div>
      <div class="case-insight">
        <strong>${escapeHtml(estado)}</strong>
        <span>${escapeHtml(caseDiagnosticText(caso))}</span>
      </div>
      <div class="case-stats">
        <div><strong>${Number(caso.actividad || 0)}</strong><span>mensajes IA</span></div>
        <div><strong>${Number(caso.intervenciones_docente || 0)}</strong><span>docente</span></div>
        <div><strong>${fmtFecha(caso.ultimo_movimiento)}</strong><span>última actividad</span></div>
      </div>
      <div class="case-card-meta">
        ${caso.organismo_area ? `<span>${escapeHtml(caso.organismo_area)}</span>` : `<span>Área en definición</span>`}
        <strong>${escapeHtml(estadoCasoLegible(caso.estado))}</strong>
      </div>
    </article>`;
  }).join("");
  renderVerMasCasos(grid, visibles.length - enPagina.length);
  grid.querySelectorAll("[data-caso-detalle]").forEach((details) => {
    details.addEventListener("toggle", () => cargarDetalleCaso(details));
  });
  grid.querySelectorAll('input[name="proyecto-voto"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.votoBorradores ||= {};
      if (state.votoSeleccionado) state.votoBorradores[state.votoSeleccionado] = state.votoBorrador;
      state.votoSeleccionado = Number(input.value);
      const caso = state.proyectoCasos.find(c => c.id === state.votoSeleccionado);
      state.votoBorrador = state.votoBorradores[caso.id] ?? caso.mi_voto ?? "";
      state.votoEstado = "";
      renderPanelVoto();
      document.getElementById("casos-panel-voto").scrollIntoView({block: "center", behavior: "smooth"});
      document.getElementById("voto-justificacion").focus({preventScroll: true});
    });
  });
}

function tituloCorto(texto, max = 38) {
  const limpio = String(texto || "Caso en definición").replace(/\s+/g, " ").trim();
  if (limpio.length <= max) return limpio;
  return `${limpio.slice(0, max - 1).trim()}…`;
}

function fuerzaDirigida(nodos, enlaces, opciones) {
  const { ancho, alto, iteraciones = 260 } = opciones;
  const cx = ancho / 2;
  const cy = alto / 2;
  const area = ancho * alto;
  const k = Math.sqrt(area / Math.max(nodos.length, 1)) * 1.05;
  let temperatura = Math.max(ancho, alto) / 10;
  const enfriamiento = temperatura / iteraciones;
  const indice = new Map(nodos.map((n, i) => [n.id, i]));
  const centro = { x: cx, y: cy, radio: 62 };
  // El rótulo va debajo del círculo y es más ancho que él: se reserva su lugar para que no
  // quede cortado; arriba se deja libre la franja que tapan la leyenda y el panel de detalle.
  const limitarAlArea = (n) => {
    const margenX = Math.max(n.radio + 22, (n.etiquetaAncho || 0) / 2 + 10);
    const margenArriba = Math.max(n.radio + 12, 110);
    const margenAbajo = n.radio + (n.tipo === "tema" ? 44 : 26);
    n.x = Math.min(ancho - margenX, Math.max(margenX, n.x));
    n.y = Math.min(alto - margenAbajo, Math.max(margenArriba, n.y));
  };

  for (let iter = 0; iter < iteraciones; iter++) {
    const despX = new Array(nodos.length).fill(0);
    const despY = new Array(nodos.length).fill(0);

    for (let i = 0; i < nodos.length; i++) {
      for (let j = i + 1; j < nodos.length; j++) {
        const dx = nodos[i].x - nodos[j].x;
        const dy = nodos[i].y - nodos[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const fuerza = (k * k) / dist;
        const ux = dx / dist;
        const uy = dy / dist;
        despX[i] += ux * fuerza;
        despY[i] += uy * fuerza;
        despX[j] -= ux * fuerza;
        despY[j] -= uy * fuerza;
      }
    }

    enlaces.forEach((e) => {
      const i = indice.get(e.from);
      const j = indice.get(e.to);
      if (i == null || j == null) return;
      const dx = nodos[i].x - nodos[j].x;
      const dy = nodos[i].y - nodos[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const fuerza = (dist * dist) / k;
      const ux = dx / dist;
      const uy = dy / dist;
      despX[i] -= ux * fuerza;
      despY[i] -= uy * fuerza;
      despX[j] += ux * fuerza;
      despY[j] += uy * fuerza;
    });

    nodos.forEach((n, i) => {
      despX[i] += (cx - n.x) * 0.012;
      despY[i] += (cy - n.y) * 0.012;
    });

    nodos.forEach((n, i) => {
      const d = Math.sqrt(despX[i] * despX[i] + despY[i] * despY[i]) || 0.01;
      const lim = Math.min(d, temperatura);
      n.x += (despX[i] / d) * lim;
      n.y += (despY[i] / d) * lim;
      limitarAlArea(n);
    });

    // Colisiones: dos nodos (o un nodo y el centro fijo «Conexiones») no se encimen.
    for (let i = 0; i < nodos.length; i++) {
      for (let j = i + 1; j <= nodos.length; j++) {
        const otro = j < nodos.length ? nodos[j] : centro;
        const dx = nodos[i].x - otro.x;
        const dy = nodos[i].y - otro.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        // Los rótulos de los puntos de contacto son anchos: se separan también por su texto.
        const ambosTemas = nodos[i].tipo === "tema" && otro.tipo === "tema";
        const porRotulo = ((nodos[i].etiquetaAncho || 0) + (otro.etiquetaAncho || 0)) / 2 * (ambosTemas ? 0.9 : 0.55);
        const minimo = Math.max(nodos[i].radio + otro.radio + 26, porRotulo);
        if (dist >= minimo) continue;
        const empuje = (minimo - dist) / (otro === centro ? 1 : 2);
        nodos[i].x += (dx / dist) * empuje;
        nodos[i].y += (dy / dist) * empuje;
        if (otro !== centro) { otro.x -= (dx / dist) * empuje; otro.y -= (dy / dist) * empuje; limitarAlArea(otro); }
        limitarAlArea(nodos[i]);
      }
    }

    temperatura = Math.max(temperatura - enfriamiento, 0.02);
  }
  return nodos;
}

function renderCasosOportunidad(casos, mostrarAporte = false) {
  return (casos || []).map((caso) => `
    <li>
      <button type="button" class="connection-case-link" data-abrir-caso="${Number(caso.id)}">${escapeHtml(caso.titulo || "Proyecto en definición")}</button>
      ${caso.cohorte ? `<small class="connection-case-cohort">Cohorte: ${escapeHtml(caso.cohorte)}</small>` : ""}
      ${mostrarAporte && caso.aporte ? `<span>${escapeHtml(caso.aporte)}</span>` : ""}
    </li>
  `).join("");
}

function renderOportunidadesConexiones(oportunidades) {
  const items = oportunidades || [];
  if (!items.length) {
    return `<section class="connection-opportunities"><div class="empty-state">Todavía no hay suficientes proyectos relacionados para proponer una prueba conjunta.</div></section>`;
  }
  const destacada = items.find((item) => item.destacada) || items[0];
  const restantes = items.filter((item) => item.id !== destacada.id);
  const componentes = (destacada.componentes || []).map((item, index) => `
    <li><span>${index + 1}</span><strong>${escapeHtml(item)}</strong></li>
  `).join("");
  const tipos = (destacada.tipos || []).map((tipo) => `<span class="connection-type-chip">${escapeHtml(tipo)}</span>`).join("");
  const otras = restantes.map((item) => `
    <article class="connection-opportunity-card">
      <div class="connection-opportunity-head">
        <span>${Number(item.cantidad || 0)} proyectos relacionados</span>
        <strong>${escapeHtml(item.nombre)}</strong>
      </div>
      <p>${escapeHtml(item.bajada || "")}</p>
      <div class="connection-card-result"><small>CAPACIDAD POSIBLE</small><span>${escapeHtml(item.resultado || "")}</span></div>
      <details>
        <summary>Ver prueba y proyectos</summary>
        <p><strong>Prueba mínima:</strong> ${escapeHtml(item.prueba || "")}</p>
        <ul class="connection-case-list">${renderCasosOportunidad(item.casos)}</ul>
      </details>
    </article>
  `).join("");
  return `
    <section class="connection-opportunities" aria-labelledby="connection-opportunities-title">
      <div class="connection-section-heading">
        <div>
          <span class="section-kicker">Primera hipótesis integrada</span>
          <h3 id="connection-opportunities-title">${escapeHtml(destacada.nombre)}</h3>
          <p>${escapeHtml(destacada.bajada || "")}</p>
        </div>
        <div class="connection-type-list">${tipos}</div>
      </div>
      <article class="connection-feature">
        <div class="connection-feature-main">
          <div class="connection-feature-result">
            <small>RESULTADO INSTITUCIONAL POSIBLE</small>
            <strong>${escapeHtml(destacada.resultado || "")}</strong>
          </div>
          <ol class="connection-pipeline">${componentes}</ol>
          <div class="connection-feature-test">
            <small>PRUEBA MÍNIMA CONJUNTA</small>
            <p>${escapeHtml(destacada.prueba || "")}</p>
          </div>
        </div>
        <aside class="connection-feature-cases">
          <span>${Number(destacada.cantidad || 0)} iniciativas aportan piezas</span>
          <ul class="connection-case-list connection-case-list-detailed">${renderCasosOportunidad(destacada.casos, true)}</ul>
          <p>La relación es una hipótesis de cartera. Los equipos deben confirmar alcance, datos y responsabilidades antes de integrarla.</p>
        </aside>
      </article>
      ${otras.length ? `<div class="connection-opportunity-title"><span class="section-kicker">Otras combinaciones detectadas</span><h3>Familias que podrían compartir capacidades</h3></div><div class="connection-opportunity-grid">${otras}</div>` : ""}
    </section>
  `;
}

function montarSelectorConexiones(contenedor, data) {
  const grupos = [...(data.cruces || []), ...(data.oportunidades || [])];
  const proyectos = new Map((data.proyectos || []).map(p => [Number(p.id), p]));
  grupos.forEach(g => (g.casos || []).forEach(p => proyectos.set(Number(p.id), p)));
  const panel = document.createElement("section"); panel.className = "card";
  panel.innerHTML = `<h3>Conexiones de un proyecto</h3><label for="conexion-proyecto">Elegí el proyecto que querés explorar</label>
    <select id="conexion-proyecto" style="width:100%;max-width:100%"><option value="">Todos los proyectos (mapa general)</option></select>
    <p class="hint">Al elegir un proyecto, el mapa muestra sólo sus temas y los proyectos con los que se vincula. Son afinidades detectadas en la cartera disponible: propuestas de colaboración para validar con los equipos.</p>
    <div id="conexion-proyecto-resultados" aria-live="polite"></div>`;
  contenedor.prepend(panel);
  const select = panel.querySelector("select"), resultado = panel.querySelector("#conexion-proyecto-resultados");
  [...proyectos.values()].sort((a,b) => (a.titulo || "").localeCompare(b.titulo || "", "es")).forEach(p => select.add(new Option((p.titulo || "Proyecto en definición") + (p.cohorte ? ` · ${p.cohorte}` : ""), String(p.id))));
  const mostrar = () => {
    const id = Number(select.value);
    if (!select.value) { resultado.innerHTML = ""; return; }
    const relacionados = grupos.filter(g => (g.casos || []).some(p => Number(p.id) === id));
    resultado.innerHTML = `<ul class="connection-case-list">${renderCasosOportunidad([proyectos.get(id)])}</ul>` + (relacionados.length ? relacionados.map(g => `
      <article class="sugerencia-item"><h4>${escapeHtml(g.nombre || "Afinidad compartida")}</h4>
      <p>${escapeHtml(g.bajada || "Punto de contacto entre propuestas.")}</p>
      ${g.prueba ? `<p><strong>Prueba conjunta sugerida:</strong> ${escapeHtml(g.prueba)}</p>` : ""}
      <ul class="connection-case-list">${renderCasosOportunidad((g.casos || []).filter(p => Number(p.id) !== id), true)}</ul></article>`).join("")
      : "<p>No se detectaron conexiones para este proyecto en la cartera disponible. Esto no significa que no puedan existir.</p>");
  };
  if (state.conexionFoco) {
    select.value = String(state.conexionFoco);
    // El proyecto elegido ya no está (por ejemplo, tras recargar la cartera): vuelve el mapa general.
    if (select.value !== String(state.conexionFoco)) state.conexionFoco = null;
    else mostrar();
  }
  select.onchange = () => {
    // Elegir un proyecto enfoca también el grafo; «Todos los proyectos» vuelve al mapa completo.
    state.conexionFoco = select.value ? Number(select.value) : null;
    state.conexionFocoElegido = true;
    renderRizomaCasos(data);
    document.getElementById("conexion-proyecto")?.focus();
  };
}

function renderRizomaCasos(data) {
  const contenedor = document.getElementById("casos-rizoma-grid");
  if (!contenedor) return;
  const cruces = data?.cruces || [];
  const oportunidades = data?.oportunidades || [];
  if (!cruces.length && !oportunidades.length) {
    contenedor.innerHTML = `<div class="empty-state">Todavía no hay suficientes proyectos relacionados para proponer conexiones.</div>`;
    montarSelectorConexiones(contenedor, data || {});
    return;
  }

  // Con un proyecto elegido, el mapa muestra todos sus temas y los proyectos que los comparten,
  // sin los recortes del mapa general (8 temas, 7 casos por tema, 22 proyectos): antes, un
  // proyecto podía no aparecer en el grafo aunque tuviera conexiones.
  // La primera vez se abre enfocado en el proyecto propio: el mapa completo abrumaba. «Todos los proyectos» lo recupera.
  if (!state.conexionFocoElegido && data?.mi_proyecto_id) state.conexionFoco = Number(data.mi_proyecto_id);
  // Un proyecto sin temas compartidos no tiene grafo propio: se muestra el mapa general.
  const pedido = Number(state.conexionFoco || 0);
  const foco = pedido && cruces.some((c) => (c.casos || []).some((p) => Number(p.id) === pedido)) ? pedido : 0;
  const temas = foco
    ? cruces.filter((c) => (c.casos || []).some((p) => Number(p.id) === foco)).slice(0, 12)
    : cruces.slice(0, 8);
  const casosPorTema = foco ? 14 : 7;
  const proyectoMap = new Map();
  const enlaces = [];
  // El proyecto elegido va primero en cada tema, para que el recorte nunca lo deje afuera.
  const casosDelTema = (cruce) => {
    const casos = cruce.casos || [];
    if (!foco) return casos.slice(0, casosPorTema);
    const propio = casos.filter((p) => Number(p.id) === foco);
    return [...propio, ...casos.filter((p) => Number(p.id) !== foco)].slice(0, casosPorTema);
  };
  temas.forEach((cruce, temaIndex) => {
    casosDelTema(cruce).forEach((caso) => {
      const id = `p-${caso.id}`;
      if (!proyectoMap.has(id)) {
        proyectoMap.set(id, {
          id,
          titulo: caso.titulo || "Caso en definición",
          etiqueta: caso.etiqueta || "Gobernanza Incubadora",
          cohorte: caso.cohorte || "",
        });
      }
      enlaces.push({ temaIndex, temaId: `tema-${temaIndex}`, proyectoId: id });
    });
  });
  const proyectos = Array.from(proyectoMap.values()).slice(0, foco ? 40 : 22);
  const proyectosVisibles = new Set(proyectos.map((p) => p.id));
  const enlacesVisibles = enlaces.filter((e) => proyectosVisibles.has(e.proyectoId));

  const ancho = 1180;
  const alto = 760;
  const cx = ancho / 2;
  const cy = alto / 2;
  const temaRadioInicial = 205;
  const proyectoRadioInicial = 340;

  const nodosFuerza = [];
  temas.forEach((cruce, index) => {
    const ang = -Math.PI / 2 + (index * Math.PI * 2) / Math.max(temas.length, 1);
    const cantidad = Number(cruce.cantidad || 0);
    nodosFuerza.push({
      id: `tema-${index}`,
      tipo: "tema",
      x: cx + Math.cos(ang) * temaRadioInicial,
      y: cy + Math.sin(ang) * temaRadioInicial,
      radio: Math.max(26, Math.min(46, 22 + cantidad)),
      etiquetaAncho: tituloCorto(cruce.nombre, 24).length * 7.8,
    });
  });
  proyectos.forEach((proyecto, index) => {
    const ang = -Math.PI / 2 + (index / Math.max(proyectos.length, 1)) * Math.PI * 2;
    const conexiones = enlacesVisibles.filter((e) => e.proyectoId === proyecto.id).length;
    nodosFuerza.push({
      id: proyecto.id,
      tipo: "proyecto",
      x: cx + Math.cos(ang) * proyectoRadioInicial,
      y: cy + Math.sin(ang) * proyectoRadioInicial,
      radio: Math.max(8, Math.min(17, 7 + conexiones * 3)),
      etiquetaAncho: tituloCorto(proyecto.titulo, 26).length * 6.6,
    });
  });

  fuerzaDirigida(
    nodosFuerza,
    enlacesVisibles.map((e) => ({ from: e.temaId, to: e.proyectoId })),
    { ancho, alto },
  );

  const posiciones = new Map(nodosFuerza.map((n) => [n.id, n]));
  const temaCoords = temas.map((_, index) => posiciones.get(`tema-${index}`));
  const projectCoords = proyectos.map((p) => posiciones.get(p.id));
  const projectCoordMap = new Map(proyectos.map((p, index) => [p.id, projectCoords[index]]));

  const lines = enlacesVisibles.map((enlace) => {
    const tema = temaCoords[enlace.temaIndex];
    const proyecto = projectCoordMap.get(enlace.proyectoId);
    if (!tema || !proyecto) return "";
    return `<line class="obsidian-edge obsidian-edge-${colorCaso(temas[enlace.temaIndex] || {}, enlace.temaIndex)}" data-from="${enlace.temaId}" data-to="${enlace.proyectoId}" x1="${tema.x}" y1="${tema.y}" x2="${proyecto.x}" y2="${proyecto.y}" />`;
  }).join("");

  const centerNode = `
    <g class="obsidian-center-node" data-node-id="centro" tabindex="0" data-title="Conexiones" data-detail="Lectura transversal de proyectos: conecta temas, datos, riesgos y decisiones de implementación sin exponer ni comparar personas.">
      <circle cx="${cx}" cy="${cy}" r="62" />
      <text x="${cx}" y="${cy - 5}" text-anchor="middle">Conexiones</text>
      <text class="obsidian-subtext" x="${cx}" y="${cy + 18}" text-anchor="middle">${enlacesVisibles.length} enlaces</text>
    </g>`;

  const themeNodes = temas.map((cruce, index) => {
    const coord = temaCoords[index];
    const cantidad = Number(cruce.cantidad || 0);
    const radio = coord.radio;
    const nombre = escapeHtml(cruce.nombre);
    const casos = (cruce.casos || []).map((caso) => caso.titulo || "Caso en definición").join(" · ");
    const detail = escapeHtml(`${cruce.tipo_label || "Punto de contacto"}. ${cantidad} casos conectados. ${cruce.bajada || ""} ${casos ? "Ejemplos: " + casos : ""}`);
    return `<g class="obsidian-node obsidian-topic obsidian-topic-${colorCaso(cruce, index)}" data-node-id="tema-${index}" tabindex="0" data-title="${nombre}" data-detail="${detail}">
      <circle cx="${coord.x}" cy="${coord.y}" r="${radio}" />
      <text x="${coord.x}" y="${coord.y + radio + 18}" text-anchor="middle">${escapeHtml(tituloCorto(cruce.nombre, 24))}</text>
      <text class="obsidian-subtext" x="${coord.x}" y="${coord.y + radio + 34}" text-anchor="middle">${cantidad} casos</text>
    </g>`;
  }).join("");

  const projectNodes = proyectos.map((proyecto, index) => {
    const coord = projectCoords[index];
    const conexiones = enlacesVisibles.filter((e) => e.proyectoId === proyecto.id).length;
    const radio = coord.radio;
    const title = escapeHtml(proyecto.titulo);
    const detail = escapeHtml(`${proyecto.etiqueta}. ${proyecto.titulo}.${proyecto.cohorte ? ` Cohorte: ${proyecto.cohorte}.` : ""} ${contar(conexiones, "punto de contacto detectado", "puntos de contacto detectados")}.`);
    return `<g class="obsidian-node obsidian-project obsidian-project-${colorCaso(proyecto, index)}" data-node-id="${proyecto.id}" tabindex="0" data-title="${title}" data-detail="${detail}">
      <circle cx="${coord.x}" cy="${coord.y}" r="${radio}" />
      <text x="${coord.x}" y="${coord.y + radio + 15}" text-anchor="middle">${escapeHtml(tituloCorto(proyecto.titulo, 26))}</text>
    </g>`;
  }).join("");

  const resumen = temas.map((cruce, index) => `
    <article class="rizoma-summary-card rizoma-card-${colorCaso(cruce, index)}">
      <div><strong>${escapeHtml(cruce.nombre)}</strong><span>${Number(cruce.cantidad || 0)} casos</span></div>
      <em class="connection-type-chip">${escapeHtml(cruce.tipo_label || "Punto de contacto")}</em>
      <p>${escapeHtml(cruce.bajada || "Punto de contacto transversal entre proyectos.")}</p>
      ${(cruce.lineas || []).length ? `<small>${escapeHtml((cruce.lineas || []).slice(0, 4).join(" · "))}</small>` : ""}
    </article>
  `).join("");

  const esTactil = Boolean(window.matchMedia?.("(hover: none)").matches);
  contenedor.innerHTML = `
    ${renderOportunidadesConexiones(oportunidades)}
    <div class="connection-map-heading">
      <div><span class="section-kicker">Mapa de afinidades</span><h3>Qué relaciones sostienen las oportunidades</h3></div>
      <p>El mapa permite explorar temas comunes. Las fichas anteriores traducen esas afinidades en pruebas institucionales posibles.</p>
    </div>
    <div class="rizoma-overview">
      <div><strong>${data.total_casos || 0}</strong><span>casos analizados</span></div>
      <div><strong>${cruces.length}</strong><span>puntos de contacto</span></div>
      <div><strong>${enlacesVisibles.length}</strong><span>conexiones visibles</span></div>
      <div><strong>${oportunidades.length}</strong><span>oportunidades de cartera</span></div>
    </div>
    <div class="rizoma-graph-panel obsidian-graph-panel">
      <div class="rizoma-legend">
        <span><i class="legend-topic"></i> Punto de contacto</span>
        <span><i class="legend-case"></i> Proyecto</span>
        <span><i class="legend-link"></i> Conexión detectada</span>
        <span class="rizoma-legend-hint">${esTactil ? "Tocá un nodo para ver qué conecta · deslizá de costado para recorrer el mapa" : "Arrastrá los nodos · rueda para zoom · arrastrá el fondo para mover"}</span>
      </div>
      <svg id="rizoma-svg" class="rizoma-graph obsidian-graph" viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Grafo de conexiones entre proyectos">
        <rect id="rizoma-bg" class="rizoma-graph-bg obsidian-graph-bg" x="1" y="1" width="${ancho - 2}" height="${alto - 2}" rx="24" />
        <g id="rizoma-viewport">
          <g id="rizoma-lines">${lines}</g>
          <g>${centerNode}</g>
          <g>${themeNodes}</g>
          <g>${projectNodes}</g>
        </g>
      </svg>
      <div id="rizoma-detail" class="rizoma-detail-panel">
        <strong>Seleccioná una conexión</strong>
        <span>${esTactil ? "Tocá un nodo para ver qué conecta y qué ejemplos sostienen esa relación." : "Pasá el mouse o enfocá un nodo para ver qué conecta y qué ejemplos sostienen esa relación. Arrastralo para reacomodar el mapa."}</span>
      </div>
    </div>
    <div class="rizoma-summary-grid">${resumen}</div>
  `;

  montarSelectorConexiones(contenedor, data || {});
  activarInteraccionGrafo(contenedor, enlacesVisibles);
}

let estadoArrastreGrafo = null;

function _coordEnGrafo(svg, viewport, evento) {
  const punto = svg.createSVGPoint();
  punto.x = evento.clientX;
  punto.y = evento.clientY;
  const matriz = viewport.getScreenCTM().inverse();
  return punto.matrixTransform(matriz);
}

function _iniciarListenersGrafoGlobal() {
  if (window.__rizomaGrafoListenersInit) return;
  window.__rizomaGrafoListenersInit = true;

  window.addEventListener("mousemove", (evento) => {
    const est = estadoArrastreGrafo;
    if (!est) return;
    if (est.nodoActivo) {
      const p = _coordEnGrafo(est.svg, est.viewport, evento);
      const circulo = est.nodoActivo.querySelector("circle");
      const textos = est.nodoActivo.querySelectorAll("text");
      const radio = Number(circulo.getAttribute("r")) || 10;
      circulo.setAttribute("cx", p.x);
      circulo.setAttribute("cy", p.y);
      textos.forEach((texto, i) => {
        texto.setAttribute("x", p.x);
        texto.setAttribute("y", i === 0 ? p.y + radio + 18 : p.y + radio + 34);
      });
      const id = est.nodoActivo.dataset.nodeId;
      est.contenedor.querySelectorAll(`.obsidian-edge[data-from="${id}"]`).forEach((l) => {
        l.setAttribute("x1", p.x);
        l.setAttribute("y1", p.y);
      });
      est.contenedor.querySelectorAll(`.obsidian-edge[data-to="${id}"]`).forEach((l) => {
        l.setAttribute("x2", p.x);
        l.setAttribute("y2", p.y);
      });
    } else if (est.fondoActivo) {
      est.vista.tx = evento.clientX - est.inicio.x;
      est.vista.ty = evento.clientY - est.inicio.y;
      est.viewport.setAttribute("transform", `translate(${est.vista.tx} ${est.vista.ty}) scale(${est.vista.escala})`);
    }
  });

  window.addEventListener("mouseup", () => {
    const est = estadoArrastreGrafo;
    if (!est) return;
    if (est.nodoActivo) est.nodoActivo.classList.remove("is-dragging");
    est.nodoActivo = null;
    est.fondoActivo = false;
  });
}

function activarInteraccionGrafo(contenedor, enlacesVisibles) {
  const svg = contenedor.querySelector("#rizoma-svg");
  const viewport = contenedor.querySelector("#rizoma-viewport");
  const detalle = contenedor.querySelector("#rizoma-detail");
  const nodos = contenedor.querySelectorAll(".obsidian-node, .obsidian-center-node");
  if (!svg || !viewport) return;

  const conectados = new Map();
  nodos.forEach((n) => conectados.set(n.dataset.nodeId, new Set([n.dataset.nodeId])));
  enlacesVisibles.forEach((e) => {
    conectados.get(e.temaId)?.add(e.proyectoId);
    conectados.get(e.proyectoId)?.add(e.temaId);
  });

  function limpiarFoco() {
    nodos.forEach((n) => n.classList.remove("is-dim", "is-active"));
    contenedor.querySelectorAll(".obsidian-edge").forEach((l) => l.classList.remove("is-dim", "is-active"));
  }

  function enfocar(nodeId) {
    const relacionados = conectados.get(nodeId) || new Set([nodeId]);
    nodos.forEach((n) => {
      const activo = relacionados.has(n.dataset.nodeId);
      n.classList.toggle("is-active", activo);
      n.classList.toggle("is-dim", !activo);
    });
    contenedor.querySelectorAll(".obsidian-edge").forEach((l) => {
      const activo = l.dataset.from === nodeId || l.dataset.to === nodeId;
      l.classList.toggle("is-active", activo);
      l.classList.toggle("is-dim", !activo);
    });
  }

  estadoArrastreGrafo = {
    contenedor, svg, viewport,
    vista: { escala: 1, tx: 0, ty: 0 },
    inicio: { x: 0, y: 0 },
    nodoActivo: null,
    fondoActivo: false,
  };
  _iniciarListenersGrafoGlobal();

  nodos.forEach((nodo) => {
    const mostrar = () => {
      if (!detalle) return;
      detalle.innerHTML = `<strong>${escapeHtml(nodo.dataset.title || "Nodo")}</strong><span>${escapeHtml(nodo.dataset.detail || "Sin detalle disponible.")}</span>`;
      enfocar(nodo.dataset.nodeId);
    };
    nodo.addEventListener("mouseenter", mostrar);
    nodo.addEventListener("focus", mostrar);
    nodo.addEventListener("mouseleave", () => { if (!estadoArrastreGrafo.nodoActivo) limpiarFoco(); });
    nodo.addEventListener("blur", () => { if (!estadoArrastreGrafo.nodoActivo) limpiarFoco(); });

    nodo.addEventListener("mousedown", (evento) => {
      if (nodo.dataset.nodeId === "centro") return;
      evento.preventDefault();
      estadoArrastreGrafo.nodoActivo = nodo;
      nodo.classList.add("is-dragging");
    });
  });

  svg.addEventListener("mousedown", (evento) => {
    if (evento.target === svg || evento.target.id === "rizoma-bg") {
      estadoArrastreGrafo.fondoActivo = true;
      estadoArrastreGrafo.inicio = { x: evento.clientX - estadoArrastreGrafo.vista.tx, y: evento.clientY - estadoArrastreGrafo.vista.ty };
    }
  });

  svg.addEventListener("wheel", (evento) => {
    evento.preventDefault();
    const delta = evento.deltaY < 0 ? 1.1 : 0.9;
    const vista = estadoArrastreGrafo.vista;
    vista.escala = Math.min(3, Math.max(0.4, vista.escala * delta));
    viewport.setAttribute("transform", `translate(${vista.tx} ${vista.ty}) scale(${vista.escala})`);
  }, { passive: false });
}

async function cargarRizomaCasos() {
  const grid = document.getElementById("casos-rizoma-grid");
  if (grid) grid.innerHTML = `<div class="empty-state">Buscando conexiones entre proyectos...</div>`;
  try {
    const data = await apiFetch("/proyectos-ia/conexiones");
    renderRizomaCasos(data);
  } catch (e) {
    if (grid) grid.innerHTML = `<div class="empty-state">No se pudieron cargar las conexiones: ${escapeHtml(e.message)}</div>`;
  }
}

async function cargarCasosProyectos() {
  const grid = document.getElementById("casos-proyectos-grid");
  if (grid) grid.innerHTML = `<div class="empty-state">Cargando casos...</div>`;
  try {
    const [casos, estadoVotos] = await Promise.all([
      apiFetch("/proyectos-ia/casos"),
      apiFetch("/proyectos-ia/votos/estado"),
    ]);
    const miVoto = estadoVotos?.mi_voto;
    if (state.actividadVotacion?.id !== estadoVotos?.actividad?.id) {
      state.votoSeleccionado = null;
      state.votoBorrador = "";
    }
    state.actividadVotacion = estadoVotos?.actividad;
    state.primeraVueltaCerrada = Boolean(estadoVotos?.cerrada);
    const guia = document.querySelector(".vote-guidance");
    if (guia) {
      guia.querySelector("strong").textContent = state.primeraVueltaCerrada ? "Primera vuelta cerrada:" : "Primera vuelta abierta:";
      guia.querySelector("span").textContent = explicarR1(estadoVotos?.actividad?.alcance || "Preferencias pedagógicas, independientes de la evaluación docente y R-1.");
    }
    state.miVoto = miVoto;
    if (!state.votoSeleccionado && miVoto) {
      state.votoSeleccionado = miVoto.proyecto_id;
      state.votoBorrador = miVoto.justificacion;
    }
    const votosPorProyecto = estadoVotos?.votos_por_proyecto || {};
    casos.forEach((caso) => {
      caso.votos_total = Number(votosPorProyecto[caso.id] || 0);
      caso.mi_voto = miVoto?.proyecto_id === caso.id ? miVoto.justificacion : "";
    });
    state.proyectoCasos = casos;
    renderCasosProyectos(casos);
    if (state.casoEnfocado) {
      const ficha = document.getElementById(`caso-compartido-${state.casoEnfocado}`);
      if (ficha) ficha.querySelector('details').open = true;
    }
  } catch (e) {
    if (grid) grid.innerHTML = `<div class="empty-state">No se pudieron cargar los casos: ${escapeHtml(e.message)}</div>`;
  }
}


// ---------- Segunda vuelta de proyectos ----------

// La sigla R-1 se explica la primera vez que aparece en las pantallas de votación.
function explicarR1(texto) {
  const t = String(texto || "");
  return t.includes("R-1") && !t.includes("protocolo") ? t.replace("R-1", "R-1 (el protocolo opcional de preparación para IA responsable)") : t;
}

function renderSegundaVuelta() {
  const payload = state.segundaVuelta;
  if (!payload) return;
  const { estado, casos } = payload;
  const ronda = estado.segunda_vuelta || {};
  const cerrada = Boolean(ronda.cerrada);
  actualizarRotuloVotacion(estado);
  const finalistas = estado.finalistas || [];
  const finalistasIds = new Set(finalistas.map((item) => Number(item.proyecto_id)));
  const votosSegunda = ronda.votos_por_proyecto || {};
  const miVotoId = Number(ronda.mi_voto?.proyecto_id || 0);
  const seleccion = Number(state.segundaVueltaSeleccionado || miVotoId || 0);
  const maximoVotos = Math.max(0, ...finalistas.map((item) => Number(votosSegunda[item.proyecto_id] || 0)));
  const ganadorIds = new Set(
    finalistas
      .filter((item) => maximoVotos > 0 && Number(votosSegunda[item.proyecto_id] || 0) === maximoVotos)
      .map((item) => Number(item.proyecto_id))
  );

  const resumen = document.getElementById("segunda-vuelta-resumen");
  if (resumen) {
    resumen.innerHTML = `<strong>${Number(ronda.votos_total || 0)}</strong><span>${cerrada ? "votos finales · elección cerrada" : "votos emitidos en la segunda vuelta"}</span>`;
  }

  const resultados = document.getElementById("primera-vuelta-resultados");
  if (resultados) {
    const filas = estado.primera_vuelta || [];
    const ocultables = filas.filter((item, index) => index >= 5 && !finalistasIds.has(Number(item.proyecto_id))).length;
    resultados.innerHTML = filas.map((item, index) => {
      const votos = Number(item.votos || 0);
      const finalista = finalistasIds.has(Number(item.proyecto_id));
      const oculta = !state.primeraVueltaTodos && index >= 5 && !finalista;
      return `<article class="runoff-result-row${finalista ? " is-finalist" : ""}"${oculta ? " hidden" : ""}>
        <span class="runoff-position">${index + 1}</span>
        <div><strong>${escapeHtml(item.titulo || "Proyecto sin título")}</strong>${item.organismo_area ? `<small>${escapeHtml(item.organismo_area)}</small>` : ""}</div>
        ${finalista ? `<span class="runoff-finalist-badge">Finalista</span>` : ""}
        <span class="runoff-vote-count"><strong>${votos}</strong> ${votos === 1 ? "voto" : "votos"}</span>
      </article>`;
    }).join("") + (ocultables ? `<button type="button" class="btn btn-secondary btn-mini runoff-ver-todos" data-primera-vuelta-todos aria-expanded="${state.primeraVueltaTodos ? "true" : "false"}">${state.primeraVueltaTodos ? "Ver solo los primeros 5" : `Ver todos (${filas.length})`}</button>` : "");
    resultados.querySelector("[data-primera-vuelta-todos]")?.addEventListener("click", () => {
      state.primeraVueltaTodos = !state.primeraVueltaTodos;
      renderSegundaVuelta();
    });
  }

  const contenedor = document.getElementById("segunda-vuelta-finalistas");
  if (contenedor) {
    contenedor.innerHTML = finalistas.map((finalista, index) => {
      const id = Number(finalista.proyecto_id);
      const caso = casos.find((item) => Number(item.id) === id);
      const votos = Number(votosSegunda[id] || 0);
      const ganador = cerrada && ganadorIds.has(id);
      const descripcion = caso?.bajada || caso?.situacion || "Consultá la ficha para conocer el proyecto.";
      return `<article class="runoff-finalist-card${!cerrada && seleccion === id ? " is-selected" : ""}${ganador ? " is-winner" : ""}">
        <div class="runoff-finalist-topline"><span>${ganador ? (ganadorIds.size > 1 ? "Empate en preferencias" : "Mayor preferencia") : `Finalista ${index + 1}`}</span><strong>${votos} ${votos === 1 ? "voto" : "votos"}${cerrada ? (votos === 1 ? " final" : " finales") : " emitidos"}</strong></div>
        <h3>${escapeHtml(finalista.titulo || caso?.titulo || "Proyecto finalista")}</h3>
        ${finalista.organismo_area || caso?.organismo_area ? `<p class="runoff-area">${escapeHtml(finalista.organismo_area || caso.organismo_area)}</p>` : ""}
        <p>${escapeHtml(descripcion)}</p>
        ${caso ? `<details><summary>Ver explicación del proyecto</summary>${renderFichaVotacion(caso)}</details>` : ""}
        ${cerrada ? `<div class="runoff-closed-result"><strong>${ganador ? (ganadorIds.size > 1 ? "Empate en la segunda vuelta" : "Mayor preferencia de la actividad") : "Preferencias recibidas"}</strong><span>${Number(ronda.votos_total || 0) ? Math.round((votos / Number(ronda.votos_total)) * 100) : 0}% de los votos</span></div>` : `<label class="runoff-choice">
          <input type="radio" name="segunda-vuelta-voto" value="${id}" ${seleccion === id ? "checked" : ""} ${state.segundaVueltaEnviando ? "disabled" : ""}>
          <span>${miVotoId === id ? "Tu voto actual" : "Elegir este proyecto"}</span>
        </label>`}
      </article>`;
    }).join("");
    contenedor.querySelectorAll('input[name="segunda-vuelta-voto"]').forEach((input) => {
      input.addEventListener("change", () => {
        state.segundaVueltaSeleccionado = Number(input.value);
        renderSegundaVuelta();
      });
    });
  }

  const estadoEl = document.getElementById("segunda-vuelta-estado");
  const hero = document.querySelector("#view-segunda-vuelta .runoff-hero");
  if (hero) {
    hero.querySelector(".section-kicker").textContent = cerrada ? "Actividad cerrada" : "Actividad pedagógica";
    hero.querySelector("h2").textContent = state.rotuloVotacion || "Resultados de la actividad";
    hero.querySelector(".view-subtitle").textContent = explicarR1(estado.actividad?.alcance || "Preferencias pedagógicas: no modifica R-1 ni la evaluación docente.");
  }
  const justificacionLabel = document.getElementById("segunda-vuelta-justificacion-label");
  if (justificacionLabel) justificacionLabel.hidden = cerrada;
  if (estadoEl) {
    estadoEl.textContent = cerrada
      ? "La segunda vuelta finalizó. Los resultados quedaron consolidados."
      : miVotoId
      ? "Tu voto ya está registrado. Podés actualizarlo mientras la segunda vuelta esté abierta."
      : "Elegí un proyecto finalista y justificá tu preferencia.";
  }
  const boton = document.querySelector("#segunda-vuelta-form button[type='submit']");
  if (boton) {
    boton.hidden = cerrada;
    boton.disabled = cerrada || state.segundaVueltaEnviando || !seleccion;
    boton.textContent = state.segundaVueltaEnviando ? "Guardando..." : (miVotoId ? "Actualizar voto" : "Confirmar voto de segunda vuelta");
  }
}

async function cargarSegundaVuelta() {
  const resultados = document.getElementById("primera-vuelta-resultados");
  const finalistas = document.getElementById("segunda-vuelta-finalistas");
  if (resultados) resultados.innerHTML = `<div class="empty-state">Cargando resultados...</div>`;
  if (finalistas) finalistas.innerHTML = `<div class="empty-state">Cargando proyectos finalistas...</div>`;
  try {
    const [casos, estado] = await Promise.all([
      apiFetch("/proyectos-ia/casos"),
      apiFetch("/proyectos-ia/votos/segunda-vuelta/estado"),
    ]);
    state.segundaVuelta = { casos, estado };
    state.segundaVueltaSeleccionado = Number(estado.segunda_vuelta?.mi_voto?.proyecto_id || 0) || null;
    renderSegundaVuelta();
    const form = document.getElementById("segunda-vuelta-form");
    if (form) form.onsubmit = enviarVotoSegundaVuelta;
  } catch (error) {
    if (resultados) resultados.innerHTML = `<div class="empty-state">No se pudo cargar la votación: ${escapeHtml(error.message)}</div>`;
    if (finalistas) finalistas.replaceChildren();
  }
}

async function enviarVotoSegundaVuelta(evento) {
  evento.preventDefault();
  const proyectoId = Number(state.segundaVueltaSeleccionado || 0);
  if (!proyectoId || state.segundaVueltaEnviando) return;
  state.segundaVueltaEnviando = true;
  renderSegundaVuelta();
  try {
    await apiFetch("/proyectos-ia/votos/segunda-vuelta", {
      method: "POST",
      body: JSON.stringify({ proyecto_id: proyectoId, actividad_id: state.segundaVuelta?.estado?.actividad?.id,
        justificacion: document.getElementById("segunda-vuelta-justificacion")?.value.trim() || "" }),
    });
    toast("Voto de segunda vuelta registrado.");
    await cargarSegundaVuelta();
  } catch (error) {
    toast(error.message, true);
  } finally {
    state.segundaVueltaEnviando = false;
    renderSegundaVuelta();
  }
}


// ---------- Gobernanza Incubadora con supervision docente ----------


function proyectoCamposActuales() {
  return {
    titulo: document.getElementById("proyecto-titulo")?.value.trim() || "",
    organismo_area: document.getElementById("proyecto-area")?.value.trim() || "",
    situacion: document.getElementById("proyecto-situacion")?.value.trim() || "",
    entrega_final: document.getElementById("proyecto-entrega")?.value.trim() || "",
  };
}

function proyectoTieneCambiosLocales() {
  const actual = proyectoCamposActuales();
  const guardado = state.proyectoIA || {};
  return actual.titulo !== (guardado.titulo || "")
    || actual.organismo_area !== (guardado.organismo_area || "")
    || actual.situacion !== (guardado.situacion || "")
    || actual.entrega_final !== (guardado.entrega_final || "");
}

function marcarProyectoDirty() {
  state.proyectoIADirty = proyectoTieneCambiosLocales();
  renderProyectoSaveStatus();
}

function renderProyectoSaveStatus() {
  const texto = state.proyectoIADirty
    ? "Cambios sin guardar"
    : state.proyectoIALastSavedAt
      ? "Guardado " + fmtFecha(state.proyectoIALastSavedAt)
      : "Guardado en tu usuario";
  ["proyecto-guardado-estado", "proyecto-entrega-guardado"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = texto;
    el.className = "save-status " + (state.proyectoIADirty ? "save-status-pending" : "save-status-ok");
  });
}

function resumenProyectoParaMoodle() {
  const p = state.proyectoIA || {};
  const campos = proyectoCamposActuales();
  const mensajes = p.mensajes || [];
  const chatIA = mensajes.filter((m) => ["participante", "ia"].includes(m.remitente)).length;
  const chatDocente = mensajes.filter((m) => ["consulta_docente", "docente"].includes(m.remitente)).length;
  return [
    "Gobernanza Incubadora",
    "",
    "Título: " + (campos.titulo || "Sin definir"),
    "Organismo o área: " + (campos.organismo_area || "Sin definir"),
    "Estado: " + estadoProyectoLabel(p.estado),
    "Interacciones con IA registradas: " + chatIA,
    "Interacciones con docente registradas: " + chatDocente,
    "",
    "Situación a mejorar:",
    campos.situacion || "Sin definir",
    "",
    "Entrega / síntesis actual:",
    campos.entrega_final || "Pendiente",
  ].join("\n");
}

async function copiarResumenProyectoMoodle() {
  const texto = resumenProyectoParaMoodle();
  try {
    await navigator.clipboard.writeText(texto);
    toast("Resumen copiado para Moodle");
  } catch (e) {
    const area = document.createElement("textarea");
    area.value = texto;
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.focus();
    area.select();
    document.execCommand("copy");
    area.remove();
    toast("Resumen copiado para Moodle");
  }
}

window.addEventListener("beforeunload", (e) => {
  if (!state.proyectoIADirty) return;
  e.preventDefault();
  e.returnValue = "";
});

function estadoProyectoLabel(estado) {
  return { en_proceso: "en proceso", entregado: "Entregado · pendiente de revisión docente", revisado: "Revisado por el docente" }[estado] || estado || "en proceso";
}

function renderProyectoChat(mensajes, targetId = "proyecto-chat") {
  const el = document.getElementById(targetId);
  if (!el) return;
  const items = mensajes || [];
  if (!items.length) {
    el.innerHTML = `<div class="empty-state">Todavía no hay conversación registrada.</div>`;
    return;
  }
  const ultimoIA = [...items].reverse().find((m) => m.remitente === "ia");
  el.innerHTML = items.map((m) => `
    <div class="project-message project-message-${escapeHtml(m.remitente)}">
      <strong>${escapeHtml(m.remitente === "participante" ? "Participante" : m.remitente === "consulta_docente" ? "Participante" : m.remitente === "docente" ? "Docente" : "IA")}</strong>
      <p>${escapeHtml(m.contenido).replace(/\n/g, "<br>")}</p>
      ${targetId === "proyecto-chat" && m.remitente === "ia" && m.id === ultimoIA?.id ? `<div class="project-message-feedback"><span>¿Esta respuesta tuvo en cuenta lo que aportaste?</span><button type="button" class="btn btn-secondary btn-mini" data-escucha-feedback="si">Sí</button><button type="button" class="btn btn-secondary btn-mini" data-escucha-feedback="no">No</button></div>` : ""}
      <span>${fmtFecha(m.creado_en)}</span>
    </div>`).join("");
  el.querySelectorAll("[data-escucha-feedback]").forEach((btn) => {
    btn.addEventListener("click", () => registrarFeedbackEscucha(btn.dataset.escuchaFeedback, btn));
  });
  el.scrollTop = el.scrollHeight;
}

async function registrarFeedbackEscucha(valor, btn) {
  try {
    await apiFetch(`/proyectos-ia/mio/escucha/${encodeURIComponent(valor)}`, { method: "POST" });
    btn?.parentElement?.querySelectorAll("button").forEach((item) => { item.disabled = true; });
    if (valor === "no") {
      const input = document.getElementById("proyecto-mensaje");
      if (input) {
        input.value = "La respuesta anterior no tuvo en cuenta lo que ya aporté. No me hagas preguntas nuevas: resumí qué entendiste, reconocé qué puntos están completos y retomá solamente el pendiente necesario más importante.";
        input.focus();
      }
    }
    toast(valor === "si" ? "Gracias. Registramos que la respuesta te escuchó." : "Gracias. Lo registramos para revisar el acompañamiento.");
  } catch (e) {
    toast("No se pudo registrar la valoración: " + e.message, true);
  }
}

function renderProyectoCuenta() {
  const el = document.getElementById("proyecto-cuenta");
  if (!el || !state.currentUser) return;
  const nombre = state.currentUser.nombre || state.currentUser.email || "usuario";
  const rol = state.currentUser.rol || "";
  const esAdmin = rol === "admin";
  el.className = `project-account-note ${esAdmin ? "project-account-admin" : ""}`;
  el.innerHTML = esAdmin
    ? `<strong>Estás trabajando como ${escapeHtml(nombre)} · admin.</strong><span>El formulario personal guarda solo el proyecto del admin. Para ver lo que hicieron los alumnos, usá la sección Supervisión docente de esta misma pantalla.</span>`
    : `<strong>Guardando como ${escapeHtml(nombre)}.</strong><span>Tu contexto, conversación, consultas y entrega quedan asociados a este usuario. Si entrás con otra cuenta, vas a ver otro proyecto.</span>`;
}

function renderPredevolucionIA(data) {
  const pre = data.predevolucion_ia;
  if (!pre?.contenido) return "";
  const fecha = pre.creado_en ? ` · ${fmtFecha(pre.creado_en)}` : "";
  const desactualizada = pre.creado_en && data.actualizado_en && new Date(data.actualizado_en) > new Date(pre.creado_en);
  const aviso = desactualizada ? `<p class="hint">El proyecto se guardó después de esta pre-devolución: puede no reflejar la versión actual.</p>` : "";
  return `<strong>Pre-devolución automática · IA${fecha}</strong><p>${escapeHtml(pre.contenido).replace(/\n/g, "<br>")}</p>${aviso}`;
}

// Vuelca lo guardado en un campo sin pisar lo que la persona escribió y todavía no guardó.
// Antes, guardar el contexto, consultar al docente o hablar con el asistente re-dibujaba el
// proyecto y reemplazaba en silencio la entrega pegada por la versión vieja del servidor.
function volcarCampoProyecto(el, previo, nuevo) {
  if (!el) return false;
  const normal = (s) => String(s || "").replace(/\s+/g, " ").trim();
  const local = normal(el.value);
  const sinCambiosLocales = local === normal(previo) || local === normal(nuevo);
  if (document.activeElement === el) return sinCambiosLocales ? false : true;
  if (!sinCambiosLocales) return true;
  el.value = nuevo || "";
  return false;
}

function renderProyectoIA(data) {
  const previo = state.proyectoIA || {};
  state.proyectoIA = data;
  state.proyectoIADirty = false;
  state.proyectoIALastSavedAt = data.actualizado_en || data.creado_en || state.proyectoIALastSavedAt;
  renderProyectoCuenta();
  configurarEspacioIncubadora();
  const accesoDevolucion = document.getElementById("btn-mi-devolucion");
  if (accesoDevolucion) accesoDevolucion.hidden = !(data.predevolucion_ia?.contenido || data.retro_docente);
  renderProyectoProgreso(data);
  const titulo = document.getElementById("proyecto-titulo");
  const area = document.getElementById("proyecto-area");
  const situacion = document.getElementById("proyecto-situacion");
  const entrega = document.getElementById("proyecto-entrega");
  const conservados = [
    volcarCampoProyecto(titulo, previo.titulo, data.titulo),
    volcarCampoProyecto(area, previo.organismo_area, data.organismo_area),
    volcarCampoProyecto(situacion, previo.situacion, data.situacion),
    volcarCampoProyecto(entrega, previo.entrega_final, data.entrega_final),
  ].some(Boolean);
  state.proyectoIADirty = conservados;
  actualizarContadorEntrega();
  actualizarContadoresProyecto();
  renderProyectoClaridad(data);
  renderProyectoEscucha(data);
  const estado = document.getElementById("proyecto-estado");
  const conDevolucion = Boolean((data.retro_docente || "").trim());
  if (estado) estado.textContent = data.estado === "entregado" && conDevolucion ? "Entregado · con devolución docente" : estadoProyectoLabel(data.estado);
  const aclaracionEstado = document.getElementById("proyecto-estado-aclaracion");
  if (aclaracionEstado) {
    const esperaRevision = data.estado === "entregado" && !conDevolucion;
    aclaracionEstado.hidden = !esperaRevision;
    aclaracionEstado.textContent = esperaRevision
      ? (data.predevolucion_ia?.contenido
        ? "Ya tenés disponible la devolución preliminar de IA. Falta la revisión de Maxi. Tu entrega está registrada; este estado no significa que debas rehacerla."
        : "Tu entrega está registrada. Falta la revisión de Maxi; este estado no significa que debas rehacerla.")
      : "";
  }
  const entregaConfirmacion = document.getElementById("proyecto-entrega-confirmacion");
  const entregado = ["entregado", "revisado"].includes(data.estado);
  if (entregaConfirmacion) {
    entregaConfirmacion.hidden = !entregado;
    entregaConfirmacion.textContent = data.estado === "revisado" || conDevolucion
      ? "Entrega registrada y con devolución docente. Mejorarla después es opcional."
      : "Tu entrega quedó registrada en Gobernanza. Está pendiente de revisión docente. No necesitás volver a marcarla como entregada.";
  }
  const entregarButton = document.getElementById("btn-entregar-proyecto");
  if (entregarButton) { entregarButton.disabled = entregado; entregarButton.textContent = entregado ? "Entrega registrada" : "Marcar como entregado"; }
  const retro = document.getElementById("proyecto-retro");
  const pre = document.getElementById("proyecto-predevolucion-ia");
  if (pre) {
    pre.innerHTML = renderPredevolucionIA(data);
    pre.style.display = data.predevolucion_ia?.contenido ? "block" : "none";
  }
  if (retro) {
    retro.style.display = data.retro_docente ? "block" : "none";
    retro.innerHTML = data.retro_docente ? `<strong>Retroalimentación docente</strong><p>${escapeHtml(data.retro_docente).replace(/\n/g, "<br>")}</p>` : "";
  }
  const mensajes = data.mensajes || [];
  renderProyectoChat(mensajes.filter((m) => ["participante", "ia"].includes(m.remitente)));
  const mensajesDocente = mensajes.filter((m) => ["consulta_docente", "docente"].includes(m.remitente));
  renderProyectoChat(mensajesDocente, "proyecto-docente-chat");
  const estadoDocente = document.getElementById("proyecto-docente-estado");
  if (estadoDocente) {
    const ultimo = mensajesDocente[mensajesDocente.length - 1];
    const pendiente = ultimo?.remitente === "consulta_docente";
    estadoDocente.className = "project-teacher-status " + (pendiente ? "pending" : ultimo ? "answered" : "empty");
    estadoDocente.textContent = pendiente
      ? "Consulta enviada · pendiente de respuesta docente"
      : ultimo
        ? "Consulta respondida · podés continuar desde la devolución recibida"
        : "Todavía no enviaste consultas al docente";
  }
  renderProyectoSaveStatus();
  window.actualizarPasosIncubadora?.(data);
  if (data.id) cargarCertificacionR1(data.id);
}

async function cargarProyectoIA() {
  const chat = document.getElementById("proyecto-chat");
  if (chat && !state.proyectoIA) chat.innerHTML = `<div class="empty-state">Cargando proyecto...</div>`;
  try {
    const data = await apiFetch("/proyectos-ia/mio");
    renderProyectoIA(data);
    if (data.id && state.incubadoraVista === "personal") cargarMonitoreo(data.id);
    const adminPanel = document.getElementById("proyecto-admin-panel");
    if (adminPanel && state.currentUser?.rol === "admin") {
      adminPanel.style.display = state.incubadoraVista === "personal" ? "none" : "block";
      cargarProyectoIASupervision();
    }
  } catch (e) {
    if (chat) chat.innerHTML = `<div class="empty-state">No se pudo cargar el proyecto: ${escapeHtml(e.message)}</div>`;
  }
}

async function guardarProyectoIA(extra = {}) {
  const payload = {
    titulo: document.getElementById("proyecto-titulo")?.value.trim() || "",
    organismo_area: document.getElementById("proyecto-area")?.value.trim() || "",
    situacion: document.getElementById("proyecto-situacion")?.value.trim() || "",
    ...extra,
  };
  if (largoTexto(payload.situacion) > MAX_SITUACION_CHARS) {
    toast(`La situación tiene ${largoTexto(payload.situacion).toLocaleString("es-AR")} caracteres y el máximo es ${MAX_SITUACION_CHARS.toLocaleString("es-AR")}. No se guardó: acortala y volvé a intentar.`, true);
    return null;
  }
  try {
    const data = await apiFetch("/proyectos-ia/mio", { method: "PATCH", body: JSON.stringify(payload) });
    renderProyectoIA(data);
    const entregaLocal = document.getElementById("proyecto-entrega")?.value.trim() || "";
    if (!("entrega_final" in extra) && entregaLocal !== (data.entrega_final || "").trim()) {
      toast("Contexto guardado. Tu entrega final tiene cambios sin guardar: siguen en pantalla; guardalos con «Guardar borrador».");
    } else {
      toast("Proyecto guardado para este usuario");
    }
    return data;
  } catch (e) {
    toast("No se pudo guardar: " + e.message, true);
    return null;
  }
}

let enviandoMensajeProyectoIA = false;

async function enviarMensajeProyectoIA(mensajeForzado = null) {
  if (enviandoMensajeProyectoIA) return;
  const input = document.getElementById("proyecto-mensaje");
  const mensaje = mensajeForzado || input?.value.trim();
  if (!mensaje) return;
  if (largoTexto(mensaje) > MAX_MENSAJE_CHARS) {
    toast(`El mensaje tiene ${largoTexto(mensaje).toLocaleString("es-AR")} caracteres y el chat admite ${MAX_MENSAJE_CHARS.toLocaleString("es-AR")}. Para tu propuesta completa usá la entrega final (hasta ${MAX_ENTREGA_CHARS.toLocaleString("es-AR")}).`, true);
    return;
  }
  const borradorEnviado = input?.value || "";
  enviandoMensajeProyectoIA = true;
  const btnEnviar = document.getElementById("btn-enviar-proyecto");
  if (btnEnviar) btnEnviar.disabled = true;
  const chat = document.getElementById("proyecto-chat");
  if (chat) chat.insertAdjacentHTML("beforeend", `<div class="empty-state" data-proyecto-espera>La IA está pensando...</div>`);
  try {
    const data = await apiFetch("/proyectos-ia/mio/mensajes", { method: "POST", body: JSON.stringify({ mensaje }) });
    if (!mensajeForzado && input && input.value === borradorEnviado) input.value = "";
    renderProyectoIA(data);
    if (state.currentUser?.rol === "admin") cargarProyectoIASupervision();
    return data;
  } catch (e) {
    toast("No se pudo confirmar el envío. Tu texto sigue disponible. " + e.message, true);
    if (chat) chat.querySelector("[data-proyecto-espera]")?.remove();
    return null;
  } finally {
    enviandoMensajeProyectoIA = false;
    if (btnEnviar) btnEnviar.disabled = false;
  }
}


let enviandoConsultaDocenteProyectoIA = false;

async function consultarDocenteProyectoIA() {
  if (enviandoConsultaDocenteProyectoIA) return;
  const input = document.getElementById("proyecto-docente-consulta");
  const mensaje = input?.value.trim();
  if (!mensaje) return;
  if (largoTexto(mensaje) > MAX_MENSAJE_DOCENTE_CHARS) {
    toast(`La consulta tiene ${largoTexto(mensaje).toLocaleString("es-AR")} caracteres y el máximo es ${MAX_MENSAJE_DOCENTE_CHARS.toLocaleString("es-AR")}. No se envió: acortala y volvé a intentar.`, true);
    return;
  }
  const borradorEnviado = input.value;
  enviandoConsultaDocenteProyectoIA = true;
  const btnConsultar = document.getElementById("btn-consultar-docente");
  if (btnConsultar) btnConsultar.disabled = true;
  try {
    const data = await apiFetch("/proyectos-ia/mio/docente", { method: "POST", body: JSON.stringify({ mensaje }) });
    if (input.value === borradorEnviado) input.value = "";
    renderProyectoIA(data);
    if (state.currentUser?.rol === "admin") cargarProyectoIASupervision();
    toast("Consulta enviada al docente");
  } catch (e) {
    toast("No se pudo confirmar la consulta. Tu texto sigue disponible. " + e.message, true);
  } finally {
    enviandoConsultaDocenteProyectoIA = false;
    if (btnConsultar) btnConsultar.disabled = false;
  }
}

const MAX_ENTREGA_CHARS = 30000; // Igual que MAX_ENTREGA_CHARS en routers/proyectos_ia.py
const MAX_SITUACION_CHARS = 30000; // Igual que MAX_SITUACION_CHARS en routers/proyectos_ia.py
const MAX_MENSAJE_CHARS = 12000; // Igual que MAX_MENSAJE_CHARS (chat con el asistente) en routers/proyectos_ia.py
const MAX_MENSAJE_DOCENTE_CHARS = 30000; // Igual que MAX_MENSAJE_DOCENTE_CHARS (consultas al docente) en routers/proyectos_ia.py
// Cuenta caracteres como el servidor (len() de Python): un emoji o símbolo fuera del plano básico es 1, no 2.
function largoTexto(texto) { return Array.from(String(texto || "").trim()).length; }

function actualizarContadorTexto(areaId, contadorId, max, desde = 0) {
  const area = document.getElementById(areaId);
  const contador = document.getElementById(contadorId);
  if (!area || !contador) return;
  const largo = largoTexto(area.value);
  const excedido = largo > max;
  contador.textContent = largo < desde ? "" : `${largo.toLocaleString("es-AR")} de ${max.toLocaleString("es-AR")} caracteres`
    + (excedido ? ". Supera el máximo: acortalo o, si es tu propuesta, pegala en la entrega final." : ".");
  contador.style.color = excedido ? "#9a2e24" : "";
}
function actualizarContadoresProyecto() {
  actualizarContadorTexto("proyecto-situacion", "proyecto-situacion-contador", MAX_SITUACION_CHARS);
  actualizarContadorTexto("proyecto-mensaje", "proyecto-mensaje-contador", MAX_MENSAJE_CHARS, 8000);
  actualizarContadorTexto("proyecto-docente-consulta", "proyecto-docente-consulta-contador", MAX_MENSAJE_DOCENTE_CHARS, 2000);
}
document.addEventListener("input", (e) => {
  if (e.target && ["proyecto-situacion", "proyecto-mensaje", "proyecto-docente-consulta"].includes(e.target.id)) actualizarContadoresProyecto();
});

function actualizarContadorEntrega() {
  const area = document.getElementById("proyecto-entrega");
  const contador = document.getElementById("proyecto-entrega-contador");
  if (!area || !contador) return;
  const largo = largoTexto(area.value);
  const excedido = largo > MAX_ENTREGA_CHARS;
  contador.textContent = `${largo.toLocaleString("es-AR")} de ${MAX_ENTREGA_CHARS.toLocaleString("es-AR")} caracteres` + (excedido ? ". Supera el máximo: no se va a poder guardar hasta acortarla." : ".");
  contador.style.color = excedido ? "#9a2e24" : "";
}
document.addEventListener("input", (e) => { if (e.target && e.target.id === "proyecto-entrega") actualizarContadorEntrega(); });

async function guardarEntregaProyecto(entregar = false) {
  const entrega = document.getElementById("proyecto-entrega")?.value.trim() || "";
  if (largoTexto(entrega) > MAX_ENTREGA_CHARS) {
    toast(`La entrega tiene ${largoTexto(entrega).toLocaleString("es-AR")} caracteres y el máximo es ${MAX_ENTREGA_CHARS.toLocaleString("es-AR")}. No se guardó: acortala y volvé a intentar.`, true);
    return;
  }
  if (entregar && !entrega && !window.confirm("La entrega final está vacía. Si tu entrega es la conversación con la tutoría, podés continuar; si no, cancelá y pegá tu propuesta. ¿Marcar como entregado igual?")) return;
  const button = document.getElementById(entregar ? "btn-entregar-proyecto" : "btn-guardar-entrega");
  if (button?.disabled) return;
  if (button) button.disabled = true;
  const confirmacion = document.getElementById("proyecto-entrega-confirmacion");
  if (confirmacion) { confirmacion.hidden = false; confirmacion.textContent = "Guardando…"; }
  const data = await guardarProyectoIA({ entrega_final: entrega, estado: entregar ? "entregado" : undefined });
  if (button) button.disabled = entregar && ["entregado", "revisado"].includes(data?.estado);
  if (confirmacion && !data) { confirmacion.hidden = false; confirmacion.textContent = "No se pudo guardar. Tu texto sigue disponible; volvé a intentar."; }
  if (confirmacion && data && !entregar && !["entregado", "revisado"].includes(data.estado)) { confirmacion.hidden = false; confirmacion.textContent = "Borrador guardado. Todavía no lo marcaste como entregado."; }
  // Solo se confirma la entrega si el servidor respondió bien y el estado quedó persistido.
  if (entregar && data && data.estado === "entregado") toast("Entrega registrada · pendiente de revisión docente.");
}

function etiquetaParticipante(p) {
  const nombre = (p.nombre || "").trim();
  const email = (p.email || "").trim();
  if (!nombre || nombre.toLowerCase() === email.toLowerCase()) return email || "Participante";
  return nombre;
}


function renderProyectoCarteraDocente(data) {
  const el = document.getElementById("proyecto-cartera-docente");
  if (!el) return;
  if (!data) {
    el.innerHTML = "";
    return;
  }
  const resumen = data.resumen || {};
  const madurez = data.madurez || {};
  const brechas = Array.isArray(data.brechas) ? data.brechas.slice(0, 6) : [];
  const temas = Array.isArray(data.temas) ? data.temas.slice(0, 5) : [];
  const candidatos = Array.isArray(data.candidatos_implementacion) ? data.candidatos_implementacion.slice(0, 4) : [];
  const segunda = Array.isArray(data.segunda_vuelta) ? data.segunda_vuelta.slice(0, 4) : [];
  const chip = (label, total) => `<div><strong>${escapeHtml(String(total || 0))}</strong><span>${escapeHtml(label)}</span></div>`;
  const item = (p) => `
    <button type="button" class="project-portfolio-item" data-proyecto-id="${p.id}">
      <strong>${escapeHtml(p.titulo || p.email || "Proyecto")}</strong>
      <span>${escapeHtml(p.nombre && p.nombre !== p.email ? p.nombre : p.email || "Participante")} · ${escapeHtml(p.tema || "sin tema")} · ${escapeHtml(p.checkpoint?.completos || 0)}/${escapeHtml(p.checkpoint?.total || 10)}</span>
    </button>`;
  el.innerHTML = `
    <div class="project-portfolio-head">
      <div>
        <span class="section-kicker">Cartera docente</span>
        <h4>Base de proyectos implementables</h4>
        <p>Lectura agregada para pasar de conversaciones a propuestas, pilotos y próximos pasos.</p>
      </div>
    </div>
    <div class="project-portfolio-metrics">
      ${chip("proyectos", resumen.total)}
      ${chip("con contexto", resumen.con_contexto)}
      ${chip("entregas", resumen.con_entrega)}
      ${chip("segunda vuelta", resumen.necesitan_segunda_vuelta)}
      ${chip("implementables", resumen.implementables)}
      ${chip("defendibles", resumen.defendibles)}
    </div>
    <div class="project-portfolio-grid">
      <section>
        <h5>Madurez</h5>
        ${Object.entries(madurez).length ? Object.entries(madurez).map(([k, v]) => `<div class="learning-event-row"><span>${escapeHtml(k.replaceAll("_", " "))}</span><strong>${v}</strong></div>`).join("") : "<p class='hint'>Sin proyectos para clasificar.</p>"}
      </section>
      <section>
        <h5>Brechas que más frenan</h5>
        ${brechas.length ? brechas.map((b) => `<div class="learning-event-row"><span>${escapeHtml(String(b.clave).replaceAll("_", " "))}</span><strong>${b.total}</strong></div>`).join("") : "<p class='hint'>Sin brechas relevantes.</p>"}
      </section>
      <section>
        <h5>Temas frecuentes</h5>
        ${temas.length ? temas.map((t) => `<div class="learning-event-row"><span>${escapeHtml(t.nombre)}</span><strong>${t.total}</strong></div>`).join("") : "<p class='hint'>Sin temas todavía.</p>"}
      </section>
    </div>
    <div class="project-portfolio-grid two">
      <section>
        <h5>Candidatos a implementación</h5>
        ${candidatos.length ? candidatos.map(item).join("") : "<p class='hint'>Todavía no hay candidatos fuertes.</p>"}
      </section>
      <section>
        <h5>Segunda vuelta prioritaria</h5>
        ${segunda.length ? segunda.map(item).join("") : "<p class='hint'>No hay alertas fuertes.</p>"}
      </section>
    </div>`;
  el.querySelectorAll("[data-proyecto-id]").forEach((btn) => {
    btn.addEventListener("click", () => cargarProyectoIADetalle(Number(btn.dataset.proyectoId)));
  });
}

function renderProyectoEscuchaMetricas(data = {}) {
  const el = document.getElementById("proyecto-escucha-metricas");
  if (!el) return;
  const porcentaje = data.porcentaje_escuchado == null ? "sin votos" : `${data.porcentaje_escuchado}%`;
  el.innerHTML = `
    <strong>Escucha y acompañamiento</strong>
    <div><span>Respuestas valoradas</span><b>${escapeHtml(String(data.feedback_total || 0))}</b></div>
    <div><span>Se sintieron escuchados</span><b>${escapeHtml(porcentaje)}</b></div>
    <div><span>Bucles detectados</span><b>${escapeHtml(String(data.bucles_detectados || 0))}</b></div>
    <div><span>Puntos cerrados por alumnos</span><b>${escapeHtml(String(data.criterios_cerrados || 0))}</b></div>
    <div><span>Sin avance por 48 h</span><b>${escapeHtml(String(data.proyectos_estancados_48h || 0))}</b></div>
    <div class="${data.consultas_docente_pendientes ? "pending" : ""}"><span>Consultas docentes pendientes</span><b>${escapeHtml(String(data.consultas_docente_pendientes || 0))}</b></div>`;
}


function renderBitacoraNarrativa(bitacora) {
  if (!bitacora) return "";
  const items = [
    ["Idea inicial", bitacora.idea_inicial],
    ["Decisiones y ajustes declarados", bitacora.ajustes_con_ia],
    ["Consulta al docente", bitacora.consulta_docente],
    ["Intervención docente", bitacora.intervencion_docente],
    ["Propuesta actual", bitacora.propuesta_actual],
    ["Brecha pendiente", bitacora.brecha_pendiente],
  ];
  return `<div class="project-narrative-card">
    <div class="section-heading-row">
      <div>
        <span class="section-kicker">Bitácora narrativa</span>
        <h5>${escapeHtml(bitacora.potencial_implementacion || "proceso")}</h5>
        <p>${escapeHtml(bitacora.lectura || "Reconstrucción breve del aprendizaje del proyecto.")}</p>
      </div>
    </div>
    <div class="project-implementation-grid">
      ${items.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "Sin registro")}</strong></div>`).join("")}
    </div>
    <details class="project-hitos"><summary>Decisiones, consultas y devoluciones (${(bitacora.hitos || []).length})</summary>
      ${(bitacora.hitos || []).map(h => `<article><strong>${escapeHtml(h.tipo)} · ${fmtFecha(h.fecha)}</strong><small>Mensaje ${h.mensaje_id}</small><p>${escapeHtml(h.contenido)}</p></article>`).join("") || "Sin hitos explícitos registrados."}
    </details>
    <details class="project-hitos"><summary>Versiones de la propuesta (${(bitacora.versiones || []).length})</summary>
      ${(bitacora.versiones || []).map(v => `<article><strong>${fmtFecha(v.fecha)}</strong>${Object.entries(v.cambios).map(([campo, cambio]) => `<p><strong>${escapeHtml(campo)}</strong><br>Antes: ${escapeHtml(cambio.antes || "Sin contenido")}<br>Después: ${escapeHtml(cambio.despues || "Sin contenido")}</p>`).join("")}</article>`).join("") || "No hay cambios de contenido registrados con versiones."}
    </details>
  </div>`;
}

function renderSugerenciaDocente(sugerencia) {
  if (!sugerencia?.mensaje) return "";
  return `<div class="project-teacher-suggestion">
    <div>
      <span class="section-kicker">Devolución sugerida</span>
      <strong>${escapeHtml(sugerencia.proxima_accion_docente || "Orientar próxima vuelta")}</strong>
      <p>${escapeHtml(sugerencia.mensaje).replace(/\n/g, "<br>")}</p>
    </div>
    <button type="button" class="btn btn-secondary btn-mini" id="btn-usar-sugerencia-docente">Usar como mensaje</button>
  </div>`;
}

function renderProyectoIASupervision(lista) {
  const el = document.getElementById("proyectos-lista");
  if (!el) return;
  if (!lista.length) {
    el.innerHTML = `<div class="empty-state">Todavía no hay proyectos iniciados por participantes.</div>`;
    return;
  }
  el.innerHTML = lista.map((p) => {
    const etiqueta = etiquetaParticipante(p);
    const entrega = p.entrega_final ? '<span class="badge badge-ok">entrega</span>' : '<span class="badge badge-neutral">sin entrega</span>';
    const consulta = p.consulta_docente_pendiente
      ? '<span class="badge badge-warn">consulta pendiente de respuesta docente</span>'
      : p.consultas_docente ? '<span class="badge badge-ok">consulta respondida</span>' : '';
    return `
      <button type="button" class="project-list-item ${state.proyectoIASeleccionado === p.id ? "active" : ""}" data-proyecto-id="${p.id}">
        <strong>${escapeHtml(etiqueta)}</strong>
        ${etiqueta.toLowerCase() !== String(p.email || "").toLowerCase() ? `<span>${escapeHtml(p.email)}</span>` : ""}
        <small>${p.mensajes_chat_ia || 0} alumno→IA · ${p.mensajes_ia || 0} IA · ${p.interacciones_docente || 0} docente · ${estadoProyectoLabel(p.estado)} · ${fmtFecha(p.ultimo_movimiento)}</small>
        <span class="project-list-badges">${p.contexto ? '<span class="badge badge-ok">contexto</span>' : '<span class="badge badge-neutral">sin contexto</span>'}${p.mensajes_chat_ia ? '<span class="badge badge-ok">chat IA</span>' : '<span class="badge badge-neutral">sin chat</span>'}${p.diagnostico?.necesita_segunda_vuelta ? '<span class="badge badge-warn">segunda vuelta</span>' : '<span class="badge badge-ok">problema claro</span>'}${consulta}${entrega}</span>
      </button>`;
  }).join("");
  el.querySelectorAll("[data-proyecto-id]").forEach((btn) => {
    btn.addEventListener("click", () => cargarProyectoIADetalle(Number(btn.dataset.proyectoId)));
  });
}


function exportarCarteraProyectos() {
  window.location.href = "/api/proyectos-ia/cartera/export";
}

async function cargarProyectoIASupervision() {
  if (state.currentUser?.rol !== "admin") return;
  try {
    const [lista, cartera, escucha] = await Promise.all([
      apiFetch("/proyectos-ia"),
      apiFetch("/proyectos-ia/cartera"),
      apiFetch("/proyectos-ia/escucha/metricas"),
    ]);
    state.proyectosIASupervision = lista;
    state.proyectosIACartera = cartera;
    renderProyectoCarteraDocente(cartera);
    renderProyectoEscuchaMetricas(escucha);
    renderProyectoIASupervision(lista);
  } catch (e) {
    const el = document.getElementById("proyectos-lista");
    if (el) el.innerHTML = `<div class="empty-state">No se pudo cargar supervisión: ${escapeHtml(e.message)}</div>`;
  }
}

async function cargarProyectoIADetalle(id) {
  try {
    const data = await apiFetch(`/proyectos-ia/${id}`);
    state.proyectoIASeleccionado = id;
    renderProyectoIASupervision(state.proyectosIASupervision);
    const nombre = data.usuario?.nombre || "";
    const email = data.usuario?.email || "";
    const etiqueta = nombre && nombre.toLowerCase() !== email.toLowerCase() ? `${nombre} · ${email}` : email || "Participante";
    document.getElementById("proyecto-admin-titulo").textContent = etiqueta;
    const detalle = document.getElementById("proyecto-admin-detalle");
    detalle.classList.remove("empty-state");
    const mensajes = data.mensajes || [];
    const iaMensajes = mensajes.filter((m) => ["participante", "ia"].includes(m.remitente));
    const docenteMensajes = mensajes.filter((m) => ["consulta_docente", "docente"].includes(m.remitente));
    const diag = data.diagnostico || {};
    const conteos = data.conteos || {};
    const brechas = diag.brechas || [];
    const ficha = data.ficha_implementacion || {};
    const checkpoint = data.checkpoint || ficha.checkpoint || {};
    const fichaItems = [
      ["Problema", ficha.problema],
      ["Usuarios/área", ficha.usuarios],
      ["Evidencia", ficha.evidencia],
      ["Datos", ficha.datos],
      ["Flujo", ficha.flujo],
      ["Rol IA", ficha.rol_ia],
      ["Supervisión", ficha.supervision],
      ["Riesgos", ficha.riesgos],
      ["Indicador", ficha.indicador],
      ["Próximo paso", ficha.proximo_paso],
    ];
    detalle.innerHTML = `
      <div class="project-admin-summary">
        <div><span>Estado</span><strong>${estadoProyectoLabel(data.estado)}</strong></div>
        <div><span>Problema</span><strong>${diag.problema_definido ? "claro" : "a precisar"}</strong></div>
        <div><span>Evidencia</span><strong>${diag.evidencia ? "presente" : "falta"}</strong></div>
        <div><span>Indicador</span><strong>${diag.indicador ? "presente" : "falta"}</strong></div>
        <div><span>Chat IA</span><strong>${conteos.mensajes_chat_ia || 0} / ${conteos.mensajes_ia || 0}</strong></div>
        <div><span>Docente</span><strong>${conteos.interacciones_docente || docenteMensajes.length}</strong></div>
        <div><span>Entrega</span><strong>${data.entrega_final ? "cargada" : "pendiente"}</strong></div>
        <div><span>Lectura</span><strong>${escapeHtml(diag.estado_claridad || "sin lectura")}</strong></div>
        <div><span>Checkpoint</span><strong>${escapeHtml(String(checkpoint.completos || 0))}/${escapeHtml(String(checkpoint.total || 10))}</strong></div>
      </div>
      <div class="project-admin-diagnosis ${diag.necesita_segunda_vuelta ? "needs-work" : "ok"}">
        <strong>${diag.necesita_segunda_vuelta ? "Necesita segunda vuelta" : "Bien encaminado"}</strong>
        <span>${brechas.length ? "Trabajar: " + escapeHtml(brechas.join(", ")) : "El caso ya explicita los criterios principales para seguir avanzando."}</span>
      </div>
      ${renderProjectSkillChart(diag.habilidades)}
      ${renderBitacoraNarrativa(data.bitacora_narrativa)}
      ${data.predevolucion_ia?.contenido ? `<div class="project-feedback">${renderPredevolucionIA(data)}</div>` : ""}
      <div class="project-implementation-card">
        <div class="section-heading-row">
          <div>
            <span class="section-kicker">Ficha de implementación</span>
            <h5>${escapeHtml(checkpoint.madurez || "madurez a estimar")}</h5>
            <p>${escapeHtml(checkpoint.proximo_foco || "Definir el próximo paso implementable.")}</p>
          </div>
        </div>
        <div class="project-implementation-grid">
          ${fichaItems.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "A precisar")}</strong></div>`).join("")}
        </div>
      </div>
      <div class="project-admin-context project-admin-context-compact">
        <p><strong>Titulo:</strong> ${escapeHtml(data.titulo || "Sin definir")}</p>
        <p><strong>Area:</strong> ${escapeHtml(data.organismo_area || "Sin definir")}</p>
        <p><strong>Situacion:</strong> ${escapeHtml(data.situacion || "Sin definir")}</p>
      </div>
      <div class="project-admin-monitor-grid">
        <section>
          <h5>Alumno ↔ IA</h5>
          <div id="proyecto-admin-chat-ia" class="project-chat-log project-admin-chat-log"></div>
        </section>
        <section>
          <h5>Alumno ↔ Docente</h5>
          <div id="proyecto-admin-chat-docente" class="project-chat-log project-admin-chat-log project-teacher-chat-log"></div>
        </section>
      </div>
      <details class="project-admin-delivery" ${data.entrega_final ? "" : "open"}>
        <summary>Entrega final</summary>
        <div>${data.entrega_final ? escapeHtml(data.entrega_final).replace(/\n/g, "<br>") : "Sin entrega final"}</div>
      </details>
      <section class="project-admin-r1"><h5>Preparación para IA Responsable R-1</h5><div id="proyecto-admin-r1-panel" class="empty-state">Cargando protocolo…</div></section>
      ${renderSugerenciaDocente(data.sugerencia_docente)}
      <div class="aprendizaje-hallazgo-box">
        <div>
          <strong>Aprendizaje curado de Incubadora</strong>
          <span>Si algo de este proyecto se repite en otros, cristalizalo como criterio para futuras cohortes.</span>
        </div>
        <select id="incubadora-aprendizaje-tipo">
          <option value="error_recurrente">Error recurrente</option>
          <option value="brecha_formativa">Brecha formativa</option>
          <option value="criterio_validado">Criterio validado</option>
          <option value="criterio_descartado">Criterio descartado</option>
          <option value="ajuste_consigna">Ajuste de consigna o tutor IA</option>
        </select>
        <select id="incubadora-aprendizaje-tema">
          <option value="">Sin tema del rizoma</option>
          <option value="Trazabilidad documental">Trazabilidad documental</option>
          <option value="Calidad de datos y criterios">Calidad de datos y criterios</option>
          <option value="Supervisión humana">Supervisión humana</option>
          <option value="Automatización prudente">Automatización prudente</option>
          <option value="Riesgos, control y seguridad">Riesgos, control y seguridad</option>
          <option value="Atención y orientación">Atención y orientación</option>
        </select>
        <input type="text" id="incubadora-aprendizaje-titulo" placeholder="Título breve del aprendizaje" />
        <textarea id="incubadora-aprendizaje-contenido" placeholder="Qué se repite y qué criterio debería orientar futuros proyectos"></textarea>
        <button type="button" class="btn btn-secondary btn-mini" id="btn-registrar-aprendizaje-incubadora">Guardar aporte de calibración</button><p id="incubadora-calibracion-confirmacion" class="calibracion-confirmacion" role="status" hidden></p>
      </div>`;
    renderProyectoChat(iaMensajes, "proyecto-admin-chat-ia");
    renderProyectoChat(docenteMensajes, "proyecto-admin-chat-docente");
    document.getElementById("proyecto-docente-retro").value = data.retro_docente || "";
    document.getElementById("proyecto-docente-proyecto-estado").value = data.estado || "en_proceso";
    cargarCertificacionR1(data.id, "proyecto-admin-r1-panel");
    if (state.incubadoraVista === "docente") cargarMonitoreo(data.id);
    document.getElementById("btn-usar-sugerencia-docente")?.addEventListener("click", () => {
      const input = document.getElementById("proyecto-docente-msg");
      if (!input) return;
      input.value = data.sugerencia_docente?.mensaje || "";
      input.focus();
    });
  } catch (e) {
    toast("No se pudo abrir el proyecto: " + e.message, true);
  }
}

async function enviarMensajeDocenteProyecto() {
  if (!state.proyectoIASeleccionado) return toast("Seleccioná un participante", true);
  const input = document.getElementById("proyecto-docente-msg");
  const mensaje = input?.value.trim();
  if (!mensaje) return;
  try {
    await apiFetch(`/proyectos-ia/${state.proyectoIASeleccionado}/docente`, { method: "POST", body: JSON.stringify({ mensaje }) });
    input.value = "";
    await cargarProyectoIADetalle(state.proyectoIASeleccionado);
    toast("Mensaje docente enviado");
  } catch (e) {
    toast("No se pudo enviar: " + e.message, true);
  }
}

async function reiniciarProyectoIASeleccionado() {
  if (!state.proyectoIASeleccionado) return toast("Seleccioná un participante", true);
  const ok = confirm("Esto reinicia el contexto, la entrega y la conversación visible del proyecto seleccionado. Usalo solo si el participante lo pidió. ¿Continuar?");
  if (!ok) return;
  try {
    await apiFetch(`/proyectos-ia/${state.proyectoIASeleccionado}/reiniciar`, { method: "POST" });
    await cargarProyectoIADetalle(state.proyectoIASeleccionado);
    await cargarProyectoIASupervision();
    toast("Proyecto reiniciado");
  } catch (e) {
    toast("No se pudo reiniciar: " + e.message, true);
  }
}


async function registrarAprendizajeIncubadora() {
  if (!state.proyectoIASeleccionado) return toast("Seleccioná un participante", true);
  const tipo = document.getElementById("incubadora-aprendizaje-tipo")?.value || "error_recurrente";
  const tema = document.getElementById("incubadora-aprendizaje-tema")?.value || "";
  const titulo = document.getElementById("incubadora-aprendizaje-titulo")?.value.trim();
  const contenido = document.getElementById("incubadora-aprendizaje-contenido")?.value.trim();
  if (!titulo || !contenido) {
    toast("Completá título y aprendizaje antes de guardar", true);
    return;
  }
  const boton = document.getElementById("btn-registrar-aprendizaje-incubadora");
  if (boton?.disabled) return;
  const aviso = document.getElementById("incubadora-calibracion-confirmacion");
  if (boton) boton.disabled = true;
  if (aviso) { aviso.hidden = false; aviso.textContent = "Guardando aporte…"; }
  try {
    await apiFetch("/incubadora/aprendizaje", {
      method: "POST",
      body: JSON.stringify({
        tipo,
        titulo,
        contenido,
        tema,
        proyecto_id: state.proyectoIASeleccionado,
      }),
    });
    if (document.getElementById("incubadora-aprendizaje-titulo").value.trim() === titulo) document.getElementById("incubadora-aprendizaje-titulo").value = "";
    if (document.getElementById("incubadora-aprendizaje-contenido").value.trim() === contenido) document.getElementById("incubadora-aprendizaje-contenido").value = "";
    if (aviso) aviso.textContent = `Guardado: «${titulo}». Quedó como propuesta en la memoria compartida de calibración, pendiente de validación de administración. No cambia automáticamente el sistema. Para corregirlo, registrá un nuevo aporte que identifique el anterior.`;
    toast("Aporte de calibración guardado");
  } catch (e) {
    if (aviso) aviso.textContent = "No se pudo confirmar el registro. Conservamos el texto; revisá Calibración antes de reenviarlo para evitar duplicados. " + e.message;
    toast("No se pudo registrar el aprendizaje: " + e.message, true);
  } finally {
    if (boton) boton.disabled = false;
  }
}

async function guardarRetroProyecto() {
  if (!state.proyectoIASeleccionado) return toast("Seleccioná un participante", true);
  const retro_docente = document.getElementById("proyecto-docente-retro")?.value.trim() || "";
  const estado = document.getElementById("proyecto-docente-proyecto-estado")?.value || "en_proceso";
  try {
    await apiFetch(`/proyectos-ia/${state.proyectoIASeleccionado}/retro`, { method: "PATCH", body: JSON.stringify({ retro_docente, estado }) });
    await cargarProyectoIADetalle(state.proyectoIASeleccionado);
    await cargarProyectoIASupervision();
    toast("Retroalimentación guardada");
  } catch (e) {
    toast("No se pudo guardar retro: " + e.message, true);
  }
}

function monitoreoTipoLabel(tipo) {
  return { avance: "Avance", riesgo: "Riesgo", decision: "Decisión", indicador: "Indicador", aprendizaje: "Aprendizaje" }[tipo] || tipo;
}

function monitoreoEstadoBadge(estado) {
  return { abierto: "badge-neutral", en_curso: "badge-media", resuelto: "badge-ok", descartado: "badge-baja" }[estado] || "badge-neutral";
}

function renderMonitoreo(data) {
  state.monitoreo = data;
  const card = document.getElementById("proyecto-monitoreo-card");
  const habilitado = data.habilitado === true;
  if (card) {
    (state.incubadoraVista === "docente" ? document.getElementById("proyecto-admin-panel") : document.getElementById("paso-panel-opcional") || document.getElementById("incubadora-personal")).appendChild(card);
    card.style.display = "block";
    card.querySelector("h3").textContent = `Gobernanza Monitoreo · ${data.proyecto_titulo || "Proyecto"}`;
  }
  const formulario = document.getElementById("form-monitoreo");
  if (formulario) { formulario.hidden = !habilitado; formulario.querySelectorAll("input,textarea,select,button").forEach(el => el.disabled = !habilitado); }
  const resumen = document.getElementById("monitoreo-resumen");
  if (resumen) {
    const total = data.metricas?.total_registros || 0;
    const abiertos = data.metricas?.abiertos || 0;
    resumen.textContent = !habilitado ? `${contar(total, "registro histórico", "registros históricos")} · solo lectura` : total ? `${contar(total, "registro")} · ${contar(abiertos, "abierto")}` : "sin registros";
  }
  const estado = document.getElementById("monitoreo-estado-escucha");
  if (estado) {
    const abiertos = data.metricas?.abiertos || 0;
    estado.className = `project-listening-status ${data.metricas?.total_registros && !abiertos ? "ready" : ""}`;
    estado.innerHTML = !habilitado ? `<strong>En cartera</strong><span>${escapeHtml(data.alcance)}</span>` : `<strong>${abiertos ? "Seguimiento pendiente" : data.metricas?.total_registros ? "Seguimiento al día" : "Empezá cuando exista implementación real"}</strong><span>${escapeHtml(data.metricas?.lectura || "Registrá hechos y decisiones cuando el proyecto comience a operar.")}</span>`;
  }
  const lista = document.getElementById("monitoreo-lista");
  if (!lista) return;
  const registros = data.registros || [];
  if (!registros.length) {
    lista.innerHTML = `<div class="empty-state">Todavía no hay registros de monitoreo.</div>`;
    return;
  }
  lista.innerHTML = registros.slice().reverse().map((r) => `
    <div class="monitoreo-item">
      <div class="monitoreo-item-header">
        <span class="monitoreo-item-tipo">${escapeHtml(monitoreoTipoLabel(r.tipo))}${r.valor_indicador != null ? `: ${escapeHtml(String(r.valor_indicador))}` : ""}</span>
        <select ${habilitado ? "" : "disabled"} data-registro-id="${r.id}" class="monitoreo-estado-select ${monitoreoEstadoBadge(r.estado)}">
          <option value="abierto" ${r.estado === "abierto" ? "selected" : ""}>Abierto</option>
          <option value="en_curso" ${r.estado === "en_curso" ? "selected" : ""}>En curso</option>
          <option value="resuelto" ${r.estado === "resuelto" ? "selected" : ""}>Resuelto</option>
          <option value="descartado" ${r.estado === "descartado" ? "selected" : ""}>Descartado</option>
        </select>
      </div>
      <div class="monitoreo-item-titulo">${escapeHtml(r.titulo)}</div>
      <div class="monitoreo-item-contenido">${escapeHtml(r.contenido)}</div>
      <div class="monitoreo-item-fecha">${r.creado_en ? new Date(r.creado_en).toLocaleString() : ""}</div>
    </div>
  `).join("");
}

function proyectoMonitoreoActual() {
  return state.incubadoraVista === "docente" ? state.proyectoIASeleccionado : state.proyectoIA?.id;
}

async function cargarMonitoreo(proyectoId) {
  const solicitud = (state.monitoreoSolicitud || 0) + 1;
  state.monitoreoSolicitud = solicitud;
  state.monitoreo = null;
  const card = document.getElementById("proyecto-monitoreo-card");
  if (card) card.style.display = "none";
  document.getElementById("form-monitoreo")?.reset();
  if (!proyectoId) return;
  try {
    const data = await apiFetch(`/monitoreo/proyecto/${proyectoId}`);
    if (state.monitoreoSolicitud === solicitud && Number(proyectoMonitoreoActual()) === Number(proyectoId)) renderMonitoreo(data);
  } catch (e) {
    if (state.monitoreoSolicitud === solicitud) toast("No se pudo cargar Monitoreo: " + e.message, true);
  }
}

async function crearRegistroMonitoreo(evento) {
  evento.preventDefault();
  const proyectoId = proyectoMonitoreoActual();
  if (!proyectoId || !state.monitoreo?.habilitado || Number(state.monitoreo.proyecto_id) !== Number(proyectoId)) return;
  const tipo = document.getElementById("monitoreo-tipo")?.value;
  const titulo = document.getElementById("monitoreo-titulo")?.value.trim();
  const contenido = document.getElementById("monitoreo-contenido")?.value.trim();
  const valorRaw = document.getElementById("monitoreo-valor-indicador")?.value;
  if (!titulo || !contenido) {
    toast("Completá título y contenido", true);
    return;
  }
  const payload = { tipo, titulo, contenido, estado: "abierto" };
  if (tipo === "indicador" && valorRaw !== "") payload.valor_indicador = Number(valorRaw);
  try {
    const data = await apiFetch(`/monitoreo/proyecto/${proyectoId}`, { method: "POST", body: JSON.stringify(payload) });
    if (Number(proyectoMonitoreoActual()) === Number(proyectoId)) {
      renderMonitoreo(data);
      document.getElementById("form-monitoreo")?.reset();
    }
    toast("Registro agregado");
  } catch (e) {
    toast("No se pudo agregar el registro: " + e.message, true);
  }
}

async function cambiarEstadoRegistroMonitoreo(registroId, estado) {
  if (!state.monitoreo?.habilitado) return;
  try {
    await apiFetch(`/monitoreo/registros/${registroId}`, { method: "PATCH", body: JSON.stringify({ estado }) });
    cargarMonitoreo(proyectoMonitoreoActual());
    toast("Estado actualizado y registrado en la trazabilidad del proyecto");
  } catch (e) {
    toast("No se pudo actualizar el estado: " + e.message, true);
  }
}

document.getElementById("btn-guardar-proyecto")?.addEventListener("click", () => guardarProyectoIA());
document.getElementById("btn-recargar-proyecto")?.addEventListener("click", cargarProyectoIA);
document.getElementById("btn-probar-claridad")?.addEventListener("click", probarClaridadProblema);
document.getElementById("btn-enviar-proyecto")?.addEventListener("click", () => enviarMensajeProyectoIA());
document.querySelectorAll("[data-proyecto-control]").forEach((btn) => {
  btn.addEventListener("click", () => usarControlProyecto(btn.dataset.proyectoControl));
});
document.getElementById("btn-consultar-docente")?.addEventListener("click", consultarDocenteProyectoIA);
document.getElementById("proyecto-mensaje")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) enviarMensajeProyectoIA();
});
document.getElementById("btn-guardar-entrega")?.addEventListener("click", () => guardarEntregaProyecto(false));
document.getElementById("btn-entregar-proyecto")?.addEventListener("click", () => guardarEntregaProyecto(true));
document.getElementById("btn-recargar-supervision")?.addEventListener("click", cargarProyectoIASupervision);
document.getElementById("btn-exportar-cartera")?.addEventListener("click", exportarCarteraProyectos);
document.getElementById("btn-docente-proyecto")?.addEventListener("click", enviarMensajeDocenteProyecto);
document.getElementById("btn-retro-proyecto")?.addEventListener("click", guardarRetroProyecto);
document.getElementById("btn-reiniciar-proyecto")?.addEventListener("click", reiniciarProyectoIASeleccionado);
document.body.addEventListener("click", (e) => {
  if (e.target && e.target.id === "btn-registrar-aprendizaje-incubadora") registrarAprendizajeIncubadora();
});
document.getElementById("btn-copiar-proyecto-moodle")?.addEventListener("click", copiarResumenProyectoMoodle);
document.getElementById("form-monitoreo")?.addEventListener("submit", crearRegistroMonitoreo);
document.getElementById("monitoreo-tipo")?.addEventListener("change", (e) => {
  const campo = document.getElementById("monitoreo-valor-indicador");
  if (campo) campo.style.display = e.target.value === "indicador" ? "" : "none";
});
document.getElementById("monitoreo-lista")?.addEventListener("change", (e) => {
  if (e.target.classList.contains("monitoreo-estado-select")) {
    cambiarEstadoRegistroMonitoreo(e.target.dataset.registroId, e.target.value);
  }
});
["proyecto-titulo", "proyecto-area", "proyecto-situacion", "proyecto-entrega"].forEach((id) => {
  document.getElementById(id)?.addEventListener("input", () => {
    marcarProyectoDirty();
    renderProyectoClaridad(state.proyectoIA || {});
  });
});

// ---------- arranque ----------

function actualizarRotuloVotacion(estado) {
  const cerrada = Boolean(estado.segunda_vuelta?.cerrada);
  state.rotuloVotacion = cerrada ? "Resultados de la actividad" : "Segunda vuelta";
  document.querySelectorAll('.nav-btn[data-view="segunda-vuelta"] .nav-label, [data-nav-target="segunda-vuelta"]').forEach(el => el.textContent = state.rotuloVotacion);
  const titulo = document.querySelector('#view-segunda-vuelta .view-title');
  if (titulo) titulo.textContent = state.rotuloVotacion;
}
async function cargarRotuloVotacion() {
  try { actualizarRotuloVotacion(await apiFetch('/proyectos-ia/votos/segunda-vuelta/estado', { estadosEsperados: [409] })); }
  catch (_) { /* The voting view reports any loading failure. */ }
}
function configurarEspacioIncubadora(vista) {
  const docente = state.currentUser?.rol === 'admin';
  state.incubadoraVista = docente ? (vista || state.incubadoraVista || 'docente') : 'personal';
  cargarMonitoreo(proyectoMonitoreoActual());
  document.getElementById('incubadora-vistas').hidden = !docente;
  document.getElementById('incubadora-personal').hidden = state.incubadoraVista !== 'personal';
  document.getElementById('proyecto-admin-panel').style.display = docente && state.incubadoraVista === 'docente' ? 'block' : 'none';
  document.querySelectorAll('[data-incubadora-vista]').forEach(btn => btn.setAttribute('aria-pressed', String(btn.dataset.incubadoraVista === state.incubadoraVista)));
}
document.querySelectorAll('[data-incubadora-vista]').forEach(btn => btn.addEventListener('click', () => configurarEspacioIncubadora(btn.dataset.incubadoraVista)));
document.getElementById('btn-mi-devolucion').addEventListener('click', () => {
  const id = state.proyectoIA?.retro_docente ? 'proyecto-retro' : 'proyecto-predevolucion-ia';
  document.getElementById(id)?.scrollIntoView({block:'start', behavior:'smooth'});
});
document.getElementById('btn-elegir-ejemplo').addEventListener('click', () => {
  const ejemplos = document.getElementById('ejemplos-disponibles');
  ejemplos.open = true; ejemplos.scrollIntoView({block:'start', behavior:'smooth'});
});
document.getElementById('btn-elegir-informe').addEventListener('click', () => {
  document.getElementById('ejemplos-disponibles').open = false;
  document.getElementById('dropzone').scrollIntoView({block:'start', behavior:'smooth'});
});
function normalizarBusqueda(texto) { return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
function actualizarBusquedaCasos() { state.casoEnfocado = null; reiniciarPaginaCasos(); renderCasosProyectos(state.proyectoCasos); }
document.getElementById('buscar-casos').addEventListener('input', actualizarBusquedaCasos);
document.getElementById('solo-mi-caso').addEventListener('change', actualizarBusquedaCasos);
document.getElementById('estado-casos').addEventListener('change', actualizarBusquedaCasos);
document.getElementById('limpiar-casos').addEventListener('click', () => {
  document.getElementById('buscar-casos').value = '';
  document.getElementById('solo-mi-caso').checked = false;
  document.getElementById('estado-casos').value = '';
  state.proyectoCasosFiltro = ''; actualizarBusquedaCasos();
});
async function abrirCasoDesdeConexion(event) {
  const enlace = event.target.closest('[data-abrir-caso]');
  if (!enlace) return;
  state.casoEnfocado = Number(enlace.dataset.abrirCaso);
  state.proyectoCasosFiltro = '';
  state.casosLimite = null; // vuelve a la primera página
  document.getElementById('buscar-casos').value = '';
  document.getElementById('solo-mi-caso').checked = false;
  document.getElementById('estado-casos').value = '';
  mostrarVista('casos');
  await cargarCasosProyectos();
  const ficha = document.getElementById(`caso-compartido-${state.casoEnfocado}`);
  if (ficha) { ficha.querySelector('details').open = true; ficha.scrollIntoView({block:'start'}); }
}
document.getElementById('casos-rizoma-grid').addEventListener('click', abrirCasoDesdeConexion);
document.getElementById('view-sintesis').addEventListener('click', abrirCasoDesdeConexion);

Promise.all([cargarUsuario(), cargarAreas(), cargarMatrizLentes(), cargarEstadoModelos()]).then(navegarPorUrl);


function renderDeltaCorridas(d) {
  if (d?.estado !== 'comparado') return `<p>${escapeHtml(d?.motivo || 'Sin corrida base registrada.')}</p>`;
  const c = d.conteos || {};
  const igual = v => v == null ? 'no registrado' : v ? 'sí' : 'no';
  return `<p>Base #${Number(d.base?.informe_id)}: ${Number(c.persistentes || 0)} persistentes · ${Number(c.nuevos || 0)} nuevos · ${Number(c.desaparecidos || 0)} desaparecidos · ${Number(c.cambiaron_prioridad || 0)} cambiaron de prioridad.</p>
    <p>Mismo Excel: ${igual(d.mismo_excel)}. Mismos datos procesados: ${igual(d.mismos_datos)}. Mismo motor: ${igual(d.base?.version_motor && d.actual?.version_motor ? d.base.version_motor === d.actual.version_motor : null)}. Mismo código: ${igual(d.base?.version_codigo && d.actual?.version_codigo ? d.base.version_codigo === d.actual.version_codigo : null)}. Mismas opciones: ${igual(d.mismas_opciones)}.</p>
    <details><summary>Versiones y evidencia</summary><p>Base: ${escapeHtml(d.base?.version_motor)} · ${escapeHtml(d.base?.version_codigo)}</p><p>Actual: ${escapeHtml(d.actual?.version_motor)} · ${escapeHtml(d.actual?.version_codigo)}</p><p>${escapeHtml(d.advertencia)}</p></details>`;
}

function renderCasosRevision(r, delta) {
  const caso = c => {
    const h=c.primary_finding, e=h.evidencia || {};
    const vis = Array.isArray(e.visibilidad_origen) ? e.visibilidad_origen.join(', ') : (e.visibilidad_origen || '');
    return `<div class="hallazgo sev-${escapeHtml(c.prioridad)}"><strong>${escapeHtml(c.prioridad.toUpperCase())} · ${escapeHtml(e.hoja || nombreLenteLegible(h.lente))} ${escapeHtml(e.celda || '')}</strong>${vis ? ` <small>(${escapeHtml(vis)})</small>` : ''}
      ${quePaso(h)}<p>${escapeHtml(h.descripcion_es || h.descripcion)}</p>${c.ejes ? `<p class="ejes-prioridad"><small>${escapeHtml(textoEjes(c.ejes))}</small></p>` : ''}${botonOrigenHallazgo(h)}<small>${Number(c.cantidad_senales)} observación(es) agrupadas${c.vinculos?.length ? ' (' + escapeHtml(c.vinculos.join(', ')) + ')' : ''}.</small><details><summary>Cómo se agruparon</summary><p>${escapeHtml(c.criterio)}</p><small>Referencia técnica: ${escapeHtml(c.root_cause_id)}</small></details>
      ${c.related_findings.length ? `<details><summary>Efectos asociados (${c.related_findings.length})</summary>${c.related_findings.map(h => `<p>${escapeHtml(h.descripcion)}</p>`).join('')}</details>` : ''}</div>`;
  };
  return `<section class="revision-casos"><h3>${Number(r.casos_revision)} casos de revisión</h3><p>${Number(r.senales_control)} señales de control agrupadas; ${Number(r.senales_contexto)} variaciones temporales separadas como contexto.</p><p>${escapeHtml(r.aclaracion)}</p>
    <h4>Comparación entre corridas</h4><div data-delta>${renderDeltaCorridas(delta)}</div>
    <label>Informe base <input type="number" min="1" data-base-id style="max-width:8rem" /></label><button type="button" class="btn btn-secondary btn-mini" data-comparar-base data-informe="${Number(r.informe_id)}">Comparar</button>
    ${r.casos.slice(0,12).map(caso).join('')}${r.casos.length>12 ? `<details><summary>Ver los otros ${r.casos.length-12} casos</summary>${r.casos.slice(12).map(caso).join('')}</details>` : ''}
    ${r.notas?.length ? `<details><summary>Cruces entre archivos: notas de alcance (${r.notas.length})</summary><ul>${r.notas.map(h=>`<li>${escapeHtml(h.descripcion)}</li>`).join('')}</ul><small>Describen qué se comparó y qué no; no son señales de error.</small></details>` : ''}
    ${r.contexto.length ? `<details><summary>Variaciones por período, hoja y cuadro (${r.contexto.length} grupos)</summary>${r.contexto.map(g=>`<details><summary>${escapeHtml(g.periodo)} · ${escapeHtml(g.hoja || 'Archivo')} · cuadro ${escapeHtml(String(g.cuadro || '—'))}: ${Number(g.cantidad)} señales</summary><ul>${g.referencias.map(h=>`<li>${escapeHtml(h.descripcion)}</li>`).join('')}</ul><small>Hasta cinco referencias; detalle íntegro en el anexo.</small></details>`).join('')}</details>` : ''}</section>`;
}
