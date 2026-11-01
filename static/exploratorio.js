(function () {
  const PISTA = {
    preguntas_no_formuladas: { nombre: "Pregunta no formulada", clase: "pregunta" },
    correlaciones_no_declaradas: { nombre: "Correlación no declarada", clase: "correlacion" },
  };

  const $rotulo = document.getElementById("rotuloTexto");
  const $informeId = document.getElementById("informeId");
  const $btnCargar = document.getElementById("btnCargar");
  const $btnGenerar = document.getElementById("btnGenerar");
  const $estado = document.getElementById("estado");
  const $lista = document.getElementById("lista");

  function fechaLegible(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return "";
    }
  }

  function destacarFrases(texto) {
    return texto
      .replace(/fase experimental/i, "<strong>$&</strong>")
      .replace(/hipotesis no validada|hip[oó]tesis no validada/i, "<strong>$&</strong>");
  }

  function tarjetaHipotesis(h) {
    const info = PISTA[h.tipo_pista] || { nombre: h.tipo_pista, clase: "" };
    const tarjeta = document.createElement("div");
    tarjeta.className = "tarjeta " + info.clase;

    const fila = document.createElement("div");
    fila.className = "etiqueta-fila";
    const etiqueta = document.createElement("span");
    etiqueta.className = "etiqueta";
    const punto = document.createElement("span");
    punto.className = "punto";
    etiqueta.append(punto, document.createTextNode(info.nombre || ""));
    const noValidada = document.createElement("span");
    noValidada.className = "no-validada";
    noValidada.textContent = "No validada";
    fila.append(etiqueta, noValidada);

    const texto = document.createElement("p");
    texto.className = "texto";
    texto.textContent = h.texto_hipotesis;

    const meta = document.createElement("div");
    meta.className = "meta";
    const spanModelo = document.createElement("span");
    spanModelo.textContent = h.modelo || "modelo no informado";
    meta.appendChild(spanModelo);
    if (h.corrida != null) {
      const spanCorrida = document.createElement("span");
      spanCorrida.textContent = "corrida " + h.corrida;
      meta.appendChild(spanCorrida);
    }
    if (h.creado_en) {
      const spanFecha = document.createElement("span");
      spanFecha.textContent = fechaLegible(h.creado_en);
      meta.appendChild(spanFecha);
    }
    tarjeta.append(fila, texto, meta);
    return tarjeta;
  }

  function bloqueAvisos(clase, titulo, items) {
    const caja = document.createElement("div");
    caja.className = clase;
    const t = document.createElement("strong");
    t.textContent = titulo;
    const ul = document.createElement("ul");
    for (const x of items) {
      const li = document.createElement("li");
      li.textContent = String(x);
      ul.appendChild(li);
    }
    caja.append(t, ul);
    return caja;
  }

  function render(payload) {
    if (payload.rotulo_experimental) $rotulo.innerHTML = destacarFrases(payload.rotulo_experimental);
    $lista.innerHTML = "";

    // Lo que la generación descartó o resolvió por plantilla va antes que las hipótesis.
    if (payload.avisos && payload.avisos.length) {
      $lista.appendChild(bloqueAvisos("avisos", "Avisos de esta generación", payload.avisos));
    }

    const corridas = Array.isArray(payload.corridas) ? payload.corridas : null;
    if (corridas && corridas.length) {
      // Cada corrida por separado: dos generaciones no se mezclan en una lista.
      for (const c of corridas) {
        const titulo = document.createElement("h3");
        titulo.className = "corrida";
        const cantidad = Number(c.cantidad ?? (c.hipotesis || []).length);
        titulo.textContent = `Corrida ${c.corrida}` + (c.creado_en ? ` · ${fechaLegible(c.creado_en)}` : "")
          + ` · ${cantidad} ${cantidad === 1 ? "hipótesis" : "hipótesis"}`;
        $lista.appendChild(titulo);
        for (const h of c.hipotesis || []) $lista.appendChild(tarjetaHipotesis({ ...h, corrida: h.corrida ?? c.corrida }));
      }
    } else if (!payload.hipotesis || payload.hipotesis.length === 0) {
      const vacio = document.createElement("div");
      vacio.className = "vacio";
      vacio.textContent = payload.avisos && payload.avisos.length
        ? "Esta generación no guardó hipótesis; ver los avisos."
        : 'Sin hipótesis exploratorias para este informe todavía. Probá "Generar nuevas".';
      $lista.appendChild(vacio);
    } else {
      for (const h of payload.hipotesis) $lista.appendChild(tarjetaHipotesis(h));
    }

    if (payload.errores && payload.errores.length) {
      const errores = document.createElement("div");
      errores.className = "errores";
      errores.textContent = payload.errores.join(" · ");
      $lista.appendChild(errores);
    }
  }

  function setEstado(texto, esError) {
    $estado.textContent = texto;
    $estado.classList.toggle("error", !!esError);
  }

  async function cargar() {
    const id = $informeId.value;
    if (!id) return;
    setEstado("Cargando…");
    try {
      const resp = await fetch(`/api/exploratorio/informes/${id}`);
      if (!resp.ok) throw new Error(`${resp.status}`);
      render(await resp.json());
      setEstado("");
    } catch (err) {
      setEstado("No se pudo cargar: " + err.message, true);
    }
  }

  async function generar() {
    const id = $informeId.value;
    if (!id) return;
    $btnGenerar.disabled = true;
    setEstado("Generando hipótesis exploratorias… puede tardar unos segundos.");
    try {
      const resp = await fetch(`/api/exploratorio/informes/${id}/generar`, { method: "POST" });
      if (!resp.ok) throw new Error(`${resp.status}`);
      render(await resp.json());
      setEstado("");
    } catch (err) {
      setEstado("No se pudo generar: " + err.message, true);
    } finally {
      $btnGenerar.disabled = false;
    }
  }

  $btnCargar.addEventListener("click", cargar);
  $btnGenerar.addEventListener("click", generar);
  $informeId.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") cargar();
  });
})();
