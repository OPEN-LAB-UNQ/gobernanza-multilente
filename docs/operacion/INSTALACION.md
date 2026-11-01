# Instalación desde cero

Probada el 11/10/2026 sobre una base PostgreSQL 15 vacía, con Python 3.9, a
partir de un clon limpio del repositorio: análisis de un ejemplo, comprobante
en PDF e inicio de una revisión B-1 v1.2 con sus 11 controles.

## Requisitos

- Python 3.11 o posterior (en producción, Python 3.12 desde la versión 0.10.64).
- PostgreSQL 15 (no requiere extensiones).
- Opcional: `tesseract` con los idiomas `spa` y `eng`, para leer PDF escaneados
  e imágenes en el propio servidor. Sin él, esas lecturas se declaran como no
  realizadas; Excel y CSV no lo necesitan.
- HTTPS delante de la aplicación (por ejemplo, nginx). La cookie de sesión es
  `Secure`: por HTTP solo funciona entrando por `localhost`.

## Pasos

1. Crear la base y su usuario:

   ```sql
   CREATE USER gobernanza WITH PASSWORD '...';
   CREATE DATABASE gobernanza OWNER gobernanza;
   ```

2. Instalar dependencias:

   ```bash
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```

3. Configurar: copiar `.env.example` a `.env` y completar como mínimo
   `DATABASE_URL`, `SECRET_KEY`, `GOBERNANZA_PASSWORD`, `ADMIN_EMAIL` y
   `PUBLIC_BASE_URL`. Las claves de modelos de lenguaje son opcionales: sin
   ellas, los controles automáticos y el comprobante funcionan igual.

4. Preparar la base:

   ```bash
   venv/bin/python scripts/inicializar_base.py
   ```

   En una base vacía crea las tablas, carga las definiciones de los
   protocolos B-1 y R-1 (`sql/datos_referencia_protocolos.json`) y marca la
   última migración. En una base existente aplica las migraciones pendientes.
   No usar `alembic upgrade head` en una base vacía: la primera migración se
   generó sobre una base que ya existía y falla.

5. Iniciar:

   ```bash
   venv/bin/uvicorn main:app --host 127.0.0.1 --port 6163
   ```

   Al primer arranque se crea la cuenta de administración con `ADMIN_EMAIL` y
   `ADMIN_PASSWORD` (o `GOBERNANZA_PASSWORD` si falta). Para producción, ver la
   unidad de ejemplo en `systemd/gobernanza.service`.

## Pruebas

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest -q
```

## Opcional en producción

- Respaldo diario de la base: ver `RESTAURACION-BACKUP.md`.
- Alertas por correo y vigilancia de la cola de análisis:
  `scripts/alerta_errores.py` (cada 10 minutos) y `scripts/vigilar_cola.py`
  (cada 2 minutos), por cron.
