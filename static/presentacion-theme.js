const estilo = new URLSearchParams(window.location.search).get("estilo");
if (estilo === "2") document.body.classList.add("theme-editorial");
if (estilo === "3") document.body.classList.add("theme-bold");

const esDetalle = window.location.pathname.replace(/\/+$/, "") === "/detalle";
document.body.classList.add(esDetalle ? "page-detail" : "page-landing");

if (esDetalle) {
  if (new URLSearchParams(window.location.search).get("imprimir") === "1") {
    window.addEventListener("load", () => window.setTimeout(() => window.print(), 250));
  }
}
