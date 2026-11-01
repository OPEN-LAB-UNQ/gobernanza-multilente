# Exploración semántica del Excel (motor 0.8.21)

La carga XLSX/XLSM conserva un inventario estructurado de nombres de hoja,
títulos/subtítulos/notas, unidades, fuentes y etiquetas de indicadores/categorías,
con archivo, hoja y coordenada. Se usan etiquetas saneadas y filas de estructura;
no se recuperan filas no interpretadas ni columnas personales excluidas. Las
fórmulas y los textos de más de 1200 caracteres se excluyen con cobertura parcial.
El inventario almacena hasta 12000 elementos; los límites se declaran.

Se proponen relaciones entre bloques de distintas hojas con al menos 50% de
coincidencia de categorías. Son candidatos a comparación, no equivalencia
certificada. El modelo debe revisar tema, población, unidad y alcance; una
variación legítima no constituye un error. El máximo de relaciones es 2000.

Los modelos seleccionados y habilitados reciben ese contexto incluso sin señales
numéricas. No se agrega otro proveedor ni una segunda llamada por defecto.
Se respeta el presupuesto de cada proveedor; se incorporan referencias por
rondas entre bloques relacionados y se declaran elementos/bloques enviados,
omisiones y fallos. Un libro grande puede recibir exploración parcial. Se
mantiene el máximo de dos intentos ante una salida inválida. Claude sigue sujeto
a la suspensión configurada.

La respuesta ampliada admite hallazgos de jurisdicción, población, unidad,
fuente, título/filas y taxonomía, con al menos dos referencias existentes y una
ubicación de celda, explicación y alternativa. El servidor reconstruye las citas
originales saneadas; no admite coordenadas aportadas libremente por la IA.
La validación de referencias no demuestra que la interpretación sea correcta.

Se guardan en InterpretacionModelo, cobertura.exploracion_semantica y el
manifiesto de ejecución. Son hallazgos exploratorios independientes, separados
de Hallazgo y de los contadores/resultados determinísticos. La pantalla, el PDF,
el Markdown y el comprobante incluyen una sección propia con evidencia
comparativa y revisión humana pendiente. El resultado mecánico no cambia por
una hipótesis de IA. Las cargas históricas sin inventario requieren recargar el
Excel: no se reconstruye contenido que ya no está almacenado.

Las regresiones prueban los seis tipos y que sus textos alterados y contrapartes
lleguen al modelo, ejecución con cero hallazgos mecánicos, rechazo de referencias
inventadas, suspensión de proveedores, saneamiento, cobertura parcial, persistencia
y PDF. Estos tests de contrato no equivalen a una tasa de detección de IA; las
sondas con proveedores reales se registran aparte y pueden variar entre modelos.
