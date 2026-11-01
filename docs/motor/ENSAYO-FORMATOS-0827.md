# Nuevos formatos y total antes de componentes — motor 0.8.27

La ampliación automática incorpora 54 casos: nueve familias, tres semillas y un
par correcto/alterado por combinación. Familias: años como texto, números con
separador decimal español, formato monetario, título combinado, hoja oculta,
total antes de componentes, vacío inesperado, texto en serie y fórmula desplazada.

La primera corrida falló en tres casos: no se encontraba una conciliación rota
cuando un total sin sangría encabezaba el cuadro. Los otros 51 casos pasaron.

La corrección considera los componentes posteriores al total inicial, hasta el
siguiente total, tomando un solo nivel. Conserva las tolerancias y la exigencia
de corroboración en otros períodos. No supone una suma sólo por el rótulo.

Los casos ahora forman parte de pytest y de la barrera Excel del empaquetador.
Se agregan controles de niveles/límites, ausencia de corroboración y dos pruebas
de extremo a extremo (carga, cola, resultado) con el libro correcto y el alterado.

El generador es `scripts/ensayo_formatos.py`. Debe ejecutarse en la copia aislada,
sin base ni credenciales productivas, como las demás campañas de calidad.
Estos ejemplos sintéticos amplían la cobertura; no certifican exactitud universal.
