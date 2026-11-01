# Política de seguridad

## Versiones con soporte

Sólo la última versión publicada recibe correcciones de seguridad.

| Versión | Soporte |
|---|---|
| La última publicada (hoy, 0.10.x) | Sí |
| Anteriores | No |

## Cómo reportar una vulnerabilidad

Si encontrás una vulnerabilidad, **no abras un *issue* público**. Escribí a
<maximilianoperez1981@gmail.com> con el asunto «Seguridad · Gobernanza» e incluí:

- qué encontraste y en qué versión (aparece en la ficha técnica y en el comprobante de cada informe);
- los pasos para reproducirlo, con datos sintéticos;
- el impacto que estimás.

Vamos a acusar recibo, revisar el reporte y contarte qué vamos a hacer. La corrección se publica en una
versión nueva y queda registrada en [`HISTORIA.md`](HISTORIA.md).

## Pautas para probar

- No pruebes ataques contra la instancia piloto (`gobernanza.entornodepruebas.com.ar`): la usan personas
  reales. Para probar, instalá tu propia copia con la [guía de instalación](docs/operacion/INSTALACION.md).
- No accedas a datos de otras personas ni los modifiques, y no cargues datos personales: la herramienta
  está pensada para datos agregados.
- No hagas pruebas de denegación de servicio.

## Prácticas del proyecto

- Las dependencias están fijadas en [`requirements.txt`](requirements.txt). Al 01/11/2026 no tienen avisos
  de seguridad conocidos en la base [OSV](https://osv.dev).
- Las claves y contraseñas van en variables de entorno, con [`.env.example`](.env.example) como modelo, y
  no en el código.
- Las pruebas usan datos sintéticos; la copia pública no incluye datos de personas ni planillas oficiales.
