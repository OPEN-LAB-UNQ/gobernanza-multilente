"""Origen de archivos y vínculo con el objeto saneado, sin conservar los bytes brutos."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any


def huella(valor: Any) -> str:
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def registrar(archivos, datos, reporte, usuario_id, tipos=None, anterior=None):
    """Metadatos de origen inmutables; el vínculo de reingreso debe ser explícito."""
    previo = ((getattr(anterior, "saneamiento", None) or {}).get("proveniencia") or {})
    fuentes_previas = {f["nombre_original"]: f for f in previo.get("fuentes", [])}
    fuentes = []
    for indice, (nombre, bruto) in enumerate(archivos):
        origen_previo = fuentes_previas.get(nombre, {})
        fuentes.append({
            "id": str(uuid.uuid4()), "nombre_original": nombre,
            "sha256_bruto": hashlib.sha256(bruto).hexdigest(), "tamano_bytes": len(bruto),
            "mime": (tipos or {}).get(nombre), "usuario_id": usuario_id,
            "ingresado_en": dt.datetime.now(dt.timezone.utc).isoformat(),
            "version": int(origen_previo.get("version", 0)) + 1,
            "fuente_anterior_id": origen_previo.get("id"), "orden_carga": indice + 1,
        })
    return {
        "fuentes": fuentes, "informe_anterior_id": getattr(anterior, "id", None),
        "sha256_procesado": huella(datos),
        "transformaciones": [
            {"etapa": "extraccion", "detalle": "Lectura de tablas/texto y normalización de columnas"},
            {"etapa": "seleccion_series", "detalle": reporte.get("normalizacion_series", {})},
            {"etapa": "sanitizacion", "detalle": reporte.get("etapa_sanitizacion", {})},
        ],
        "almacena_archivo_bruto": False,
    }


def evidencia_origen(evidencia, informe):
    """Solo atribuye una fuente exacta cuando el localizador permite resolverla."""
    p = (getattr(informe, "saneamiento", None) or {}).get("proveniencia") or {}
    fuentes = p.get("fuentes", [])
    archivo = evidencia.get("archivo") or evidencia.get("archivo_origen")
    # 'filas' puede representar registros, filas Excel o loci agregados: no adivinar su base.
    nombres = {str(archivo)} if archivo else set()
    seleccion = [f for f in fuentes if f["nombre_original"] in nombres] if nombres else fuentes
    exacta = bool(seleccion) and (len(seleccion) == len(nombres) if nombres else len(fuentes) == 1)
    return {
        "informe_id": getattr(informe, "id", None),
        "fuente_ids": [f["id"] for f in seleccion],
        "estado": "identificada" if exacta else "archivo_no_resuelto" if fuentes else "origen_historico_no_registrado",
        "sha256_procesado": p.get("sha256_procesado"),
        "transformaciones": p.get("transformaciones", []),
    }
