# Errores visibles — 0.8.32

Aviso persistente en aplicación principal, lector OCR y demo pública. Se instala antes de los scripts de las pantallas. Captura errores HTTP de peticiones API del mismo origen, conexión, JSON inválido, tiempo de espera (180 segundos), promesas rechazadas, errores JavaScript y scripts que no cargan. Los avisos permanecen hasta cierre explícito. Las notificaciones de error de la aplicación principal usan el mismo panel; los éxitos siguen siendo temporales.

No reintenta solicitudes automáticamente, no recarga ni limpia formularios. Un timeout puede ocurrir después de que el servidor guarde; el mensaje pide verificar antes de repetir. Cancelaciones explícitas del llamador se respetan sin falso aviso. No muestra trazas internas ni parámetros de URL. Los textos se insertan como texto, no HTML.

OCR conserva el resultado anterior si la nueva respuesta no contiene páginas, reactiva el botón de lectura al fallar y muestra cobertura parcial explícitamente. Los errores de exportación también usan aviso persistente.

Alcance: requiere que el navegador pueda cargar la página y el script de avisos. Una caída total de red antes de recibir HTML, un cierre del navegador o fallos no emitidos por la aplicación quedan fuera de este mecanismo. Las páginas independientes no incluidas conservan sus mensajes propios.
