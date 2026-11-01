// Charla en filminas. En pantallas anchas se muestra una por vez y se pasa con transición, como en una
// presentación: flechas, Av Pág, espacio, la rueda del mouse o los botones de abajo. En el celular quedan
// una debajo de otra, para leer con el dedo.
(function () {
  var filminas = Array.prototype.slice.call(document.querySelectorAll('.filmina, .filmina-pie'));
  var contador = document.getElementById('filmina-contador');
  var encabezado = document.querySelector('.site-header');
  var botones = document.getElementById('filmina-botones');
  if (!filminas.length) return;
  var ancho = window.matchMedia('(min-width: 761px)');
  var indice = 0;
  var bloqueo = 0;

  function ajustar() {
    var alto = encabezado ? encabezado.getBoundingClientRect().height : 0;
    document.documentElement.style.setProperty('--alto-encabezado', alto + 'px');
  }

  function modo() {
    return document.body.classList.contains('modo-filminas');
  }

  // Vista previa de la filmina que sigue, chiquita abajo a la izquierda (la tecla P la oculta o la muestra).
  var proxima = document.getElementById('filmina-proxima');
  var oculta = false;
  try { oculta = localStorage.getItem('charla-proxima') === 'oculta'; } catch (e) { /* sin almacenamiento */ }

  function vistaPrevia() {
    if (!proxima) return;
    var lienzo = proxima.querySelector('.filmina-proxima-lienzo');
    var rotulo = proxima.querySelector('.filmina-proxima-rotulo');
    lienzo.innerHTML = '';
    proxima.hidden = oculta || !modo();
    if (proxima.hidden) return;
    var siguiente = filminas[indice + 1];
    if (!siguiente) {
      rotulo.textContent = 'Fin de la charla';
      lienzo.style.height = '0px';
      return;
    }
    var alto = encabezado ? encabezado.getBoundingClientRect().height : 0;
    var w = window.innerWidth, h = Math.max(200, window.innerHeight - alto);
    var escala = 240 / w;
    var copia = siguiente.cloneNode(true);
    copia.removeAttribute('id');
    Array.prototype.forEach.call(copia.querySelectorAll('[id]'), function (n) { n.removeAttribute('id'); });
    copia.classList.add('activa');
    copia.classList.remove('pasada');
    copia.setAttribute('aria-hidden', 'true');
    copia.style.cssText = 'position:absolute;top:0;left:0;right:auto;bottom:auto;width:' + w + 'px;height:' + h +
      'px;transform:none;transition:none;opacity:1;visibility:visible;overflow:hidden;background:' +
      getComputedStyle(siguiente).backgroundColor;
    var marco = document.createElement('div');
    marco.style.cssText = 'position:relative;width:' + w + 'px;height:' + h + 'px;transform:scale(' + escala + ');transform-origin:0 0;';
    marco.appendChild(copia);
    lienzo.style.height = Math.round(h * escala) + 'px';
    lienzo.appendChild(marco);
    var titulo = siguiente.querySelector('h1, h2');
    rotulo.textContent = 'Sigue: ' + (titulo ? titulo.textContent.trim() : (indice + 2));
  }

  function mostrar(i, sinHistoria) {
    indice = Math.max(0, Math.min(filminas.length - 1, i));
    filminas.forEach(function (f, k) {
      f.classList.toggle('activa', k === indice);
      f.classList.toggle('pasada', k < indice);
      f.setAttribute('aria-hidden', k === indice ? 'false' : 'true');
    });
    if (contador) contador.textContent = (indice + 1) + ' / ' + filminas.length;
    if (!sinHistoria && window.history && history.replaceState) history.replaceState(null, '', '#f' + (indice + 1));
    vistaPrevia();
  }

  function activar() {
    ajustar();
    if (ancho.matches) {
      document.body.classList.add('modo-filminas');
      var m = /^#f(\d+)$/.exec(location.hash);
      mostrar(m ? parseInt(m[1], 10) - 1 : indice, true);
    } else {
      document.body.classList.remove('modo-filminas');
      filminas.forEach(function (f) { f.classList.remove('activa', 'pasada'); f.removeAttribute('aria-hidden'); });
      vistaPrevia();
    }
  }

  function avanzar(paso) {
    if (!modo()) return;
    mostrar(indice + paso);
  }

  // En la fase de captura: las flechas pasan de filmina aunque el foco haya quedado en un enlace o un botón.
  window.addEventListener('keydown', function (e) {
    if (!modo()) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (t && /^(SUMMARY|BUTTON|A)$/.test(t.tagName) && (e.key === ' ' || e.key === 'Enter')) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'p' || e.key === 'P') {
      oculta = !oculta;
      try { localStorage.setItem('charla-proxima', oculta ? 'oculta' : 'visible'); } catch (err) { /* sin almacenamiento */ }
      vistaPrevia();
      return;
    }
    if (['ArrowDown', 'ArrowRight', 'PageDown', ' '].indexOf(e.key) >= 0 && !e.shiftKey) {
      e.preventDefault();
      avanzar(1);
    } else if (['ArrowUp', 'ArrowLeft', 'PageUp'].indexOf(e.key) >= 0 || (e.key === ' ' && e.shiftKey)) {
      e.preventDefault();
      avanzar(-1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      mostrar(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      mostrar(filminas.length - 1);
    }
  }, true);

  // La rueda pasa de a una filmina; si la filmina tiene más contenido (el texto completo), primero lo recorre.
  window.addEventListener('wheel', function (e) {
    if (!modo() || Math.abs(e.deltaY) < 12) return;
    var f = filminas[indice];
    var abajo = e.deltaY > 0;
    var resto = abajo ? f.scrollHeight - f.clientHeight - f.scrollTop : f.scrollTop;
    if (resto > 2) return;
    e.preventDefault();
    var ahora = Date.now();
    if (ahora < bloqueo) return;
    bloqueo = ahora + 650;
    avanzar(abajo ? 1 : -1);
  }, { passive: false });

  if (botones) {
    botones.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (b) avanzar(b.getAttribute('data-paso') === '-1' ? -1 : 1);
    });
  }

  window.addEventListener('resize', activar);
  activar();
})();
