(function () {
  const toc = document.querySelector(".faq-toc");
  const list = document.querySelector(".faq-body .faq-list");
  if (!toc || !list) return;

  const detallesPorId = {};
  list.querySelectorAll(":scope > details").forEach((detalle) => {
    const resumen = detalle.querySelector(":scope > summary");
    if (resumen && resumen.id) detallesPorId[resumen.id] = detalle;
  });

  function activar(id, mover) {
    if (!detallesPorId[id]) return;
    Object.entries(detallesPorId).forEach(([clave, detalle]) => {
      detalle.open = clave === id;
    });
    toc.querySelectorAll("a").forEach((enlace) => {
      enlace.classList.toggle("is-active", enlace.getAttribute("href") === "#" + id);
    });
    if (mover) detallesPorId[id].scrollIntoView({ behavior: "smooth", block: "start" });
  }

  toc.querySelectorAll("a").forEach((enlace) => {
    enlace.addEventListener("click", (evento) => {
      const id = enlace.getAttribute("href").slice(1);
      if (!detallesPorId[id]) return;
      evento.preventDefault();
      history.replaceState(null, "", "#" + id);
      activar(id, true);
      enlace.blur();
    });
  });

  // Conserva enlaces anteriores a secciones ahora incluidas en una respuesta.
  function abrirDestino() {
    const id = (window.location.hash || "").slice(1);
    const destino = document.getElementById(id);
    const entrada = Object.entries(detallesPorId).find(([clave, detalle]) =>
      clave === id || (destino && detalle.contains(destino)));
    if (!entrada) return;
    activar(entrada[0], false);
    if (destino) destino.scrollIntoView({ behavior: "auto", block: "start" });
  }

  list.addEventListener("toggle", (evento) => {
    const detalle = evento.target;
    if (detalle.parentElement !== list || !detalle.open) return;
    const id = detalle.querySelector(":scope > summary")?.id;
    if (id) activar(id, false);
  }, true);
  activar("faq-para-que-sirve", false);
  abrirDestino();
  window.addEventListener("hashchange", abrirDestino);
})();
