# Controles antes de publicar Gobernanza

- Antes de publicar cambios, ejecutar `venv/bin/python scripts/verificar_calidad.py` sobre la versión exacta a desplegar. El comando usa una copia temporal sin base ni credenciales de producción.
- No publicar si falla. No reducir controles ni modificar casos esperados sólo para obtener un resultado verde.
- Para correcciones en lectura de Excel, fórmulas, lentes o reportes, conservar un caso de regresión que reproduzca el problema y un control que confirme que los errores reales siguen siendo detectados.
- El empaquetador comprueba la regresión Excel automáticamente. Una copia manual por SSH también requiere la suite completa antes del despliegue, respaldo y verificación posterior.
- Consultar `docs/operacion/CONTROL-CALIDAD.md` para el alcance y los límites de estas comprobaciones.
