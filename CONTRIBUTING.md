# Cómo contribuir

Gracias por tu interés en Gobernanza Multilente e Incubadora. Estas pautas buscan que cada cambio mantenga lo que
la herramienta promete: decir siempre qué no revisó, no alarmar sin motivo y encontrar una parte
razonable de los errores comunes.

## Informar un fallo

Abrí un *issue* con:

- qué hiciste, qué esperabas y qué pasó;
- la versión (aparece en la ficha técnica y en el comprobante del informe);
- si es posible, **un archivo de ejemplo que reproduzca el problema**. Usá datos sintéticos o públicos:
  **nunca subas datos personales ni información reservada**. Si el archivo original no puede compartirse,
  describí su estructura (hojas, encabezados, formato de los números) o armá uno equivalente.

Las fallas de lectura en silencio (una parte del archivo que se leyó mal y el informe no lo dijo) son
las más importantes: tienen prioridad.

## Proponer un cambio

1. Hacé un *fork* y una rama con un nombre descriptivo.
2. Si corregís la lectura de archivos, las fórmulas, las lentes o los informes, **agregá un caso de
   regresión** que reproduzca el problema y una prueba que confirme que los errores reales se siguen
   detectando.
3. Corré la suite completa y el control de calidad:

   ```bash
   venv/bin/pip install -r requirements-dev.txt
   venv/bin/python -m pytest
   venv/bin/python scripts/verificar_calidad.py
   ```

4. Abrí un *pull request* explicando qué cambia, por qué y cómo lo verificaste.

## Reglas que no se negocian

- **No se reducen controles ni se modifican casos esperados para obtener un resultado verde.** Si una
  prueba falla, se corrige el código o se discute el caso, con su motivo.
- Las planillas de regresión de `tests/fixtures/` y sus huellas se conservan; no se reemplazan en silencio.
- Las comprobaciones las hacen reglas reproducibles. Un modelo de lenguaje puede ayudar a interpretar,
  pero no decide ni calcula.
- Todo lo que no se pudo leer o controlar se declara al comienzo del informe, con su motivo.
- Los cambios en los criterios de uso o en su medición se documentan antes de medir, nunca después.

## Estilo

- Código en Python 3.11 o posterior, verificado con `ruff` (configuración en `pyproject.toml`).
- Nombres, comentarios y mensajes al usuario en español, en lenguaje llano.
- Cada versión registra sus cambios en `HISTORIA.md`.

## Conducta

La participación en el proyecto se rige por el [código de conducta](CODE_OF_CONDUCT.md).
