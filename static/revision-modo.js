/* Revisión rápida y revisión profunda: qué revisión fue cada informe y los archivos de una rápida,
   que se conservan en esta pestaña para pasar a la profunda sin volver a elegirlos. */
(() => {
  "use strict";
  const NOMBRES = { rapida: "Revisión rápida", profunda: "Revisión profunda" };
  // Informes de esta pestaña: id → FormData con los mismos archivos (File) y opciones de la carga.
  // No se guarda en el navegador ni en el servidor: al recargar la página se pierde, y se pide elegirlos de nuevo.
  const cargas = new Map();

  function copia(form) {
    const nueva = new FormData();
    for (const [k, v] of form.entries()) nueva.append(k, v);
    return nueva;
  }
  // Un informe anterior a las dos revisiones (sin el campo) fue una revisión profunda.
  function modo(fuente) {
    const valor = fuente && typeof fuente === "object" ? (fuente.modo_revision ?? fuente.saneamiento?.modo_revision) : fuente;
    return valor === "rapida" ? "rapida" : "profunda";
  }
  window.RevisionModo = {
    modo,
    nombre: (fuente) => NOMBRES[modo(fuente)],
    guardar(informeId, form) { cargas.set(Number(informeId), copia(form)); },
    // Los mismos archivos y opciones, pidiendo la revisión profunda; null si ya no están en esta pestaña.
    paraProfunda(informeId) {
      const form = cargas.get(Number(informeId));
      if (!form) return null;
      const nueva = copia(form);
      nueva.set("modo_revision", "profunda");
      return nueva;
    },
  };
})();
