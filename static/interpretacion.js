/* Confirmación previa compartida por la carga, los ejemplos y la revisión de PDF. */
(() => {
  "use strict";
  const nombres = {
    universidad: "universidad", organismo_publico: "organismo público", organizacion: "organización",
    otra: "otra institución", desconocida: "institución sin determinar", empresa: "empresa",
    presupuesto: "presupuesto", pagos: "registro de pagos", estadistica: "estadística", matricula: "matrícula",
    personal: "personal", servicios: "servicios", inventario: "inventario", otro: "otro", desconocido: "sin clasificar",
    publico: "público", privado: "privado", no_determinado: "sin determinar",
    importe: "importe", cantidad: "cantidad", porcentaje: "porcentaje", indice: "índice",
    periodo_serie: "período de una serie agregada", fecha_operacion: "fecha de una operación",
    identificador: "identificador", categoria: "categoría",
    serie_filas: "serie con períodos en filas", serie_columnas: "serie con períodos en columnas",
    operaciones: "operaciones individuales", ninguno: "sin eje temporal",
  };
  const etiqueta = (valor) => nombres[valor] || valor;
  function elemento(tag, texto, padre) {
    const el = document.createElement(tag);
    if (texto != null) el.textContent = texto;
    if (padre) padre.append(el);
    return el;
  }
  function copia(form) {
    const nueva = new FormData();
    for (const [k, v] of form.entries()) nueva.append(k, v);
    return nueva;
  }
  async function enviar(form) {
    const avance = typeof document.getElementById === "function" ? document.getElementById("interpretacion-avance") : null;
    if (avance) avance.textContent = "";
    const resp = await fetch("/api/analisis-rapido", { method: "POST", body: form });
    const dato = await resp.json();
    if (!resp.ok) {
      const e = new Error(typeof dato.detail === "string" ? dato.detail : dato.detail?.mensaje || "No se pudo preparar el informe.");
      e.detalle = dato.detail;
      throw e;
    }
    return dato;
  }
  // Consultas seguidas que pueden fallar (reinicio del servicio, red) antes de abandonar la espera: unos 30 s.
  const REINTENTOS_LECTURA = 20;
  function mostrarAvance(avance) {
    // Un libro grande tiene cientos de cuadros: se muestra cuántos ya leyeron los modelos.
    const nodo = typeof document.getElementById === "function" ? document.getElementById("interpretacion-avance") : null;
    if (!nodo || !avance || !avance.total) return;
    nodo.textContent = `Cuadros leídos: ${Number(avance.leidos) || 0} de ${Number(avance.total)}`
      + (avance.hoja ? ` (última hoja leída: ${avance.hoja})` : "")
      + ". Los cuadros iguales en varias hojas se leen una sola vez.";
  }
  function cancelacion(mensaje) {
    const e = new Error(mensaje || "Lectura cancelada. No se ejecutaron controles; podés volver a cargar el archivo.");
    e.cancelada = true;
    return e;
  }
  async function esperarLectura(dato) {
    let cancelada = false;
    const id = Number(dato.informe_id);
    // «Cancelar lectura»: el servidor deja de pedir lecturas a los modelos y la espera termina sin analizar.
    const boton = typeof document.getElementById === "function" ? document.getElementById("interpretacion-cancelar") : null;
    if (boton && dato.estado === "interpretando") {
      boton.disabled = false;
      boton.onclick = async () => {
        boton.disabled = true;
        cancelada = true;
        try {
          await fetch(`/api/interpretacion-previa/${id}/cancelar`, { method: "POST" });
        } catch (e) {
          // Sin respuesta igual se deja de esperar; el servidor descarta la lectura si llega a confirmarse.
        }
      };
    }
    try {
      return await seguirLectura(dato, () => cancelada);
    } finally {
      if (boton) boton.onclick = null;
    }
  }
  async function seguirLectura(dato, cancelada) {
    let fallas = 0;
    mostrarAvance(dato.avance);
    while (dato.estado === "interpretando") {
      await new Promise(resolve => setTimeout(resolve, 1500));
      if (cancelada()) throw cancelacion();
      let respuesta = null;
      try {
        respuesta = await fetch(`/api/interpretacion-previa/${Number(dato.informe_id)}`, { cache: "no-store" });
      } catch (e) {
        respuesta = null;
      }
      if (cancelada()) throw cancelacion();
      if (!respuesta || !respuesta.ok) {
        // Un corte breve no abandona la espera: el trabajo sigue en el servidor. Un 4xx o un corte largo, sí.
        fallas += 1;
        const definitivo = respuesta && respuesta.status < 500 && respuesta.status !== 429;
        if (definitivo || fallas >= REINTENTOS_LECTURA) {
          throw new Error("No se pudo consultar la lectura previa. El trabajo queda guardado; conservá los originales para retomarlo.");
        }
        continue;
      }
      fallas = 0;
      dato = await respuesta.json();
      mostrarAvance(dato.avance);
    }
    if (dato.estado === "error") {
      if (dato.cancelada) throw cancelacion(dato.error);
      throw new Error(dato.error || "La lectura no se completó; no se ejecutaron controles.");
    }
    return dato;
  }
  function seleccionar(padre, rotulo, opciones, valor) {
    const label = elemento("label", rotulo + " ", padre);
    label.style.display = "block";
    label.style.margin = "10px 0";
    const select = elemento("select", null, label);
    select.setAttribute("aria-label", rotulo);
    for (const v of opciones) {
      const option = elemento("option", etiqueta(v), select);
      option.value = v;
    }
    select.value = valor;
    return select;
  }
  window.prepararYConfirmarInforme = async (form, solicitud = enviar) => {
    const original = copia(form); // Retiene exactamente los archivos y opciones de esta carga.
    let dato = await esperarLectura(await solicitud(copia(original)));
    if (dato.estado !== "pendiente_confirmacion") throw new Error("El servidor no devolvió la interpretación previa esperada.");
    const dialog = elemento("dialog");
    dialog.style.cssText = "width:min(850px,90vw);max-height:88vh;overflow:auto;overflow-wrap:anywhere;box-sizing:border-box;border:1px solid #94a3b8;border-radius:12px;padding:24px;color:#172536;background:white";
    document.body.append(dialog);
    return new Promise((resolve, reject) => {
      let ocupado = false;
      const cerrar = () => { dialog.close(); dialog.remove(); };
      const cancelar = () => {
        if (ocupado) return;
        cerrar(); reject(new Error("Carga pendiente de confirmación. Los controles no se ejecutaron."));
      };
      dialog.addEventListener("cancel", (e) => { e.preventDefault(); cancelar(); });
      function render() {
        dialog.replaceChildren();
        const r = dato.interpretacion;
        const cuadros = r.cuadros || [];
        const titulo = elemento("h2", "Confirmá qué contiene el informe", dialog);
        titulo.id = "interpretacion-titulo";
        dialog.setAttribute("aria-labelledby", titulo.id);
        const tipos = [...new Set(cuadros.map((u) => u.propuesta.tipo))];
        const instituciones = [...new Set(cuadros.map((u) => u.propuesta.institucion))];
        elemento("p", tipos.length === 1 && instituciones.length === 1
          ? `Interpretamos que subiste un informe de ${etiqueta(tipos[0])} de una ${etiqueta(instituciones[0])}. ¿Es correcto?`
          : "El archivo contiene cuadros de distintos tipos. Revisá la interpretación de cada uno antes de analizar.", dialog);
        elemento("p", "La IA propone, las reglas comprueban, la persona decide. La IA propone qué contiene el documento; tu confirmación orienta y suma controles, y las cuentas se hacen siempre, con los datos originales.", dialog);
        const controles = new Map();
        const editores = [];
        const atencion = (u) => u.lecturas_validas < 2 || u.propuesta.tipo === "desconocido" || u.propuesta.eje === "no_determinado"
          || Object.keys(u.por_analogia || {}).length > 0 || Object.values(u.estado_lectoras || {}).some((e) => e.error);
        // Con muchos cuadros, un resumen por tipo; el detalle de cada uno queda plegado, salvo los que piden revisión.
        let plegados = null;
        if (cuadros.length > 3) {
          const grupos = new Map();
          for (const u of cuadros) {
            const clave = `${etiqueta(u.propuesta.tipo)} · ${etiqueta(u.propuesta.institucion)} · régimen ${etiqueta(u.propuesta.regimen)}`;
            grupos.set(clave, (grupos.get(clave) || 0) + 1);
          }
          const hojas = new Set(cuadros.map((u) => `${u.archivo}\u0000${u.hoja}`)).size;
          const dudosos = cuadros.filter(atencion).length;
          elemento("p", `${cuadros.length} cuadros en ${hojas} ${hojas === 1 ? "hoja" : "hojas"}${dudosos ? `; ${dudosos} ${dudosos === 1 ? "necesita" : "necesitan"} tu revisión y ${dudosos === 1 ? "se muestra" : "se muestran"} abajo` : ""}:`, dialog);
          const resumen = elemento("ul", null, dialog);
          for (const [clave, n] of grupos) elemento("li", `${n} ${n === 1 ? "cuadro" : "cuadros"}: ${clave}`, resumen);
          plegados = elemento("details", null, dialog);
          elemento("summary", `Ver los ${cuadros.length} cuadros uno por uno`, plegados);
        }
        for (const u of cuadros) {
          const card = elemento("section", null, plegados && !atencion(u) ? plegados : dialog);
          card.style.cssText = "border-top:1px solid #cbd5e1;margin-top:16px;padding-top:12px";
          elemento("h3", `${u.archivo} · ${u.hoja || "Tabla"} · cuadro ${u.bloque}`, card);
          elemento("p", `${etiqueta(u.propuesta.tipo)} · ${etiqueta(u.propuesta.institucion)} · régimen ${etiqueta(u.propuesta.regimen)}`, card);
          elemento("p", u.propuesta.descripcion, card);
          if (u.lecturas_validas < 2 || u.propuesta.tipo === "desconocido") {
            elemento("p", "No hubo acuerdo suficiente para clasificar este cuadro. Podés modificarlo o pedir otra lectura. Si confirmás sin clasificar, sus controles semánticos quedarán pendientes.", card);
          }
          for (const [campo, a] of Object.entries(u.por_analogia || {})) {
            elemento("p", `Sin acuerdo en «${campo}» para este cuadro: se tomó «${etiqueta(a.valor)}», lo que acordaron ${a.cuadros} cuadros con los mismos encabezados en otras hojas y propuso al menos una lectora de este. Revisalo.`, card);
          }
          for (const [lectora, estado] of Object.entries(u.estado_lectoras || {})) {
            if (estado.error) elemento("p", `${lectora}: ${estado.error}.${estado.reintento_esquema ? " Se intentó corregir el formato de la respuesta." : ""}`, card);
          }
          const c = u.cobertura || {};
          elemento("p", `Lectura ${c.modo || "inicial"}: ${c.filas_presentadas || 0} de ${c.filas_total || 0} filas y ${c.notas_presentadas || 0} de ${c.notas_total || 0} notas presentadas a los modelos. Cifras ocultas.${c.parcial ? " Alcance parcial declarado." : ""}`, card);
          const editor = elemento("fieldset", null, card);
          editor.hidden = true; editores.push(editor);
          elemento("legend", "Modificar interpretación", editor);
          const campos = {
            institucion: seleccionar(editor, "Institución", r.catalogos.instituciones, u.propuesta.institucion),
            regimen: seleccionar(editor, "Régimen", r.catalogos.regimenes, u.propuesta.regimen),
            tipo: seleccionar(editor, "Contenido del cuadro", r.catalogos.tipos, u.propuesta.tipo),
            eje: seleccionar(editor, "Organización temporal", r.catalogos.ejes, u.propuesta.eje),
            roles: {},
          };
          const detalle = elemento("details", null, editor);
          elemento("summary", "Revisar el significado de las columnas", detalle);
          for (const col of u.columnas) campos.roles[col] = seleccionar(detalle, col, r.catalogos.roles, u.propuesta.roles[col] || "otro");
          controles.set(u.id, campos);
        }
        const estado = elemento("p", "Todavía no se ejecutaron controles.", dialog);
        estado.setAttribute("role", "status"); estado.setAttribute("aria-live", "polite");
        const botones = elemento("div", null, dialog);
        botones.style.cssText = "display:flex;flex-wrap:wrap;gap:10px;margin-top:16px;background:white;padding:12px 0";
        const si = elemento("button", "Sí, analizar", botones);
        const modificar = elemento("button", "No, modificar", botones);
        const mas = elemento("button", "Reanalizar con más detalle", botones);
        const salir = elemento("button", "Volver sin analizar", botones);
        for (const b of [si, modificar, mas, salir]) {
          b.type = "button";
          b.style.cssText = "font:inherit;padding:10px 14px;border:1px solid #94a3b8;border-radius:7px;background:white;color:#172536;cursor:pointer";
        }
        si.style.cssText += ";background:#ae1930;color:white;border-color:#ae1930";
        modificar.onclick = () => {
          if (plegados) plegados.open = true;
          editores.forEach((e) => { e.hidden = false; });
          si.textContent = "Confirmar cambios y analizar";
          editores[0]?.querySelector("select")?.focus();
        };
        salir.onclick = cancelar;
        async function accion(detallada) {
          if (ocupado) return;
          ocupado = true;
          dialog.querySelectorAll("button, select").forEach((el) => { el.disabled = true; });
          estado.textContent = detallada ? "Releyendo con más filas y contexto. Después deberás confirmar la nueva interpretación…" : "Confirmando interpretación y preparando los controles seleccionados…";
          try {
            const siguiente = copia(original);
            siguiente.set("interpretacion_accion", detallada ? "detallada" : "confirmar");
            siguiente.set("interpretacion_id", String(dato.informe_id));
            siguiente.set("interpretacion_revision", String(r.revision));
            if (!detallada) {
              const cambios = {};
              for (const u of cuadros) {
                const campos = controles.get(u.id), cambio = {};
                for (const k of ["tipo", "institucion", "regimen", "eje"]) if (campos[k].value !== u.propuesta[k]) cambio[k] = campos[k].value;
                const roles = Object.fromEntries(Object.entries(campos.roles).map(([k, el]) => [k, el.value]));
                if (Object.keys(roles).some((k) => roles[k] !== u.propuesta.roles[k])) cambio.roles = roles;
                if (Object.keys(cambio).length) cambios[u.id] = cambio;
              }
              siguiente.set("interpretacion_correcciones", JSON.stringify(cambios));
            }
            const nuevo = await esperarLectura(await solicitud(siguiente));
            if (detallada) {
              if (nuevo.estado !== "pendiente_confirmacion") throw new Error("La relectura no devolvió una propuesta para confirmar.");
              dato = nuevo; ocupado = false; render();
            } else {
              if (!nuevo.job) throw new Error("La confirmación no produjo un análisis. Conservá esta carga para reintentar.");
              cerrar(); resolve(nuevo);
            }
          } catch (e) {
            ocupado = false;
            estado.textContent = e.message;
            dialog.querySelectorAll("button, select").forEach((el) => { el.disabled = false; });
          }
        }
        si.onclick = () => accion(false);
        mas.onclick = () => accion(true);
      }
      render(); dialog.showModal();
    });
  };
})();
