// Video de la presentación: el reproductor de YouTube (modo de privacidad mejorada) se crea recién cuando la persona
// aprieta «Reproducir el video». Hasta entonces la página no se conecta con YouTube (ver /privacidad#cookies).
(function () {
  document.querySelectorAll('.video-play[data-yt]').forEach(function (boton) {
    boton.addEventListener('click', function () {
      var iframe = document.createElement('iframe');
      iframe.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(boton.dataset.yt) + '?rel=0&autoplay=1';
      iframe.title = boton.dataset.titulo || 'Video';
      // El sitio manda Referrer-Policy same-origin y YouTube necesita el origen para reproducir.
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      iframe.allowFullscreen = true;
      boton.replaceWith(iframe);
      iframe.focus();
    });
  });
})();
