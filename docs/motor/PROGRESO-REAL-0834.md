# Progreso real — 0.8.34

Se elimina la duración mínima artificial de 12 segundos, su temporizador y el mensaje ficticio de consolidación posterior a recibir el resultado. La pantalla presenta la devolución en cuanto recibe el informe listo.

Se mantiene el sondeo real de trabajos pendientes/procesando cada 4,5 segundos; no es una duración mínima. El tiempo de cálculo real no se modifica. El error de un trabajo se presenta sin espera artificial.

La calibración reprodujo además una carrera: una respuesta tardía podía reemplazar el informe que el usuario acababa de abrir. Ahora sólo actualiza el detalle si sigue seleccionado el informe solicitado. Cuatro pruebas de comportamiento protegen disponibilidad inmediata, sondeo real, error y cambio de informe.
