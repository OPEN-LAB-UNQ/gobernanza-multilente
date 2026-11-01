(function () {
  const boton = document.querySelector(".nav-toggle");
  const nav = document.getElementById("nav-principal");
  if (!boton || !nav) return;

  const cerrar = () => {
    nav.classList.remove("is-open");
    boton.setAttribute("aria-expanded", "false");
  };

  boton.addEventListener("click", () => {
    const abierto = nav.classList.toggle("is-open");
    boton.setAttribute("aria-expanded", String(abierto));
  });

  nav.querySelectorAll("a").forEach((a) => a.addEventListener("click", cerrar));

  document.addEventListener("click", (ev) => {
    if (!nav.classList.contains("is-open")) return;
    if (nav.contains(ev.target) || boton.contains(ev.target)) return;
    cerrar();
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 1320) cerrar();
  });
})();
