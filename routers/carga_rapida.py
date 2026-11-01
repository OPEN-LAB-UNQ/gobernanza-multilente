"""Flujo simplificado: subir hasta 4 archivos, apretar un botón, recibir el
informe. Sin dar de alta un área ni escribir JSON a mano -- el área y el
período se resuelven solos salvo que se indiquen explícitamente."""
from __future__ import annotations

import datetime
import json
import logging
import re
from copy import deepcopy
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

import models
import schemas
from core.auth import get_current_user
from database import get_db
from routers.informes import MODELOS_TRIANGULACION_VALIDOS
from services import actividad as actividad_svc
from services import ambito as ambito_svc
from services import (
    carga_archivos,
    cuota_ia,
    excel_cobertura,
    formula_integridad,
    pdf_controles,
    perfilado,
    proveniencia,
)
from services import interpretacion_previa as interpretacion_svc
from services import jobs as jobs_svc
from services import sanitizacion as sanitizacion_svc

router = APIRouter(tags=["carga-rapida"])
logger = logging.getLogger(__name__)

MAX_ARCHIVOS = 4
MAX_BYTES_POR_ARCHIVO = 30 * 1024 * 1024  # nginx admite 128 MB por carga: los cuatro archivos con su tope
ALCANCES_SERIES = {"auto", "nivel_general", "principales", "todas"}
MODOS_USO_MULTILENTE = {"revision_final", "informe_en_construccion"}
# Rápida: sólo las cuentas, sin IA ni confirmación. Profunda: interpretación previa con IA y confirmación humana.
MODOS_REVISION = {"rapida", "profunda"}
MAX_ORIENTACION_ANALISIS = 1500
AREA_GENERICA_CODIGO = "GENERAL"
AREA_GENERICA_NOMBRE = "General"


def _archivo_grande(nombre: Optional[str]) -> HTTPException:
    return HTTPException(422, f"'{nombre}' supera el máximo permitido de {MAX_BYTES_POR_ARCHIVO // (1024 * 1024)} MB")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ORIGENES_LECTURA_REVISADA = {"revision_pdf", "revision_ocr"}
CODIGO_REVISION_LECTURA = "requiere_revision_lectura"


def _aviso_revision_lectura(revisar: list[str], todos: list[str]) -> dict:
    """Detalle del 422 cuando llega un PDF o una imagen a la carga directa.

    No se analiza nada de la carga, ni siquiera los Excel/CSV que vengan junto: la persona revisa
    primero la lectura de esos archivos, o los quita y analiza el resto.
    """
    return {
        "codigo": CODIGO_REVISION_LECTURA,
        "archivos": revisar,
        "otros_archivos": [n for n in todos if n not in revisar],
        "mensaje": carga_archivos.MENSAJE_REVISION_LECTURA,
        "url": carga_archivos.URL_REVISION_LECTURA,
    }


def _lectura_revisada(origen: str | None, archivo_original: str | None, leidos: list[tuple[str, bytes]]) -> dict | None:
    """Registro de que la tabla viene de la revisión de lectura, confirmada por una persona."""
    origen = (origen or "").strip()
    if not origen:
        return None
    if origen not in ORIGENES_LECTURA_REVISADA:
        raise HTTPException(422, "origen_lectura debe ser revision_pdf o revision_ocr")
    if len(leidos) != 1 or carga_archivos._extension(leidos[0][0]) != "csv":
        raise HTTPException(422, "una tabla revisada se carga sola, como un único CSV")
    nombre = re.sub(r"[\x00-\x1f\x7f]", "", str(archivo_original or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()[:200]
    if not nombre:
        raise HTTPException(422, "indicá archivo_original: el nombre del documento del que se leyó la tabla")
    return {
        "origen": origen,
        "archivo_original": nombre,
        "archivo_revisado": leidos[0][0],
        "revisada_por_persona": True,
        "leyenda": f"Tabla leída {'con OCR ' if origen == 'revision_ocr' else ''}de {nombre} y revisada por una persona "
                   "antes de analizar",
    }



MOTIVOS_DE_LECTURA = ("Columna sin rótulo", "Período vacío", "Hay más de un número")


def _celda_a1(fila: int, columna: int) -> str:
    """Celda de la tabla revisada como la mostraría una planilla: el encabezado es la fila 1 (fila -1)."""
    from openpyxl.utils import get_column_letter

    return f"{get_column_letter(columna + 1)}{fila + 2}"


def _celdas_marcadas_revision(leidos: list[tuple[str, bytes]]) -> dict:
    """Las mismas marcas que la pantalla de revisión, recalculadas sobre la tabla confirmada.

    Si la persona confirmó con celdas marcadas (más de un número en la celda, formato ambiguo,
    rótulo repetido), el informe lo dice al comienzo: el análisis corre igual, pero esos valores
    pueden estar mal leídos. No depende de lo que informe el navegador.
    """
    import csv
    import io

    from services.ocr_local import celdas_dudosas

    try:
        texto = leidos[0][1].decode("utf-8-sig", errors="replace")
        primera = texto.splitlines()[0] if texto else ""
        # La revisión exporta con «;» en formato argentino y con «,» en el inglés.
        separador = ";" if primera.count(";") > primera.count(",") else ","
        filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
        if len(filas) < 2:
            return {}
        dudosas = celdas_dudosas(filas[0], filas[1:])
    except Exception:  # noqa: BLE001 — la marca no puede impedir el análisis
        return {}
    rotulos_genericos = [h for h in filas[0] if re.fullmatch(r"\s*(columna\s*\d+|concepto)\s*", str(h), re.I)]
    motivos = list(dict.fromkeys(str(d.get("motivo") or "").split(":")[0] for d in dudosas if d.get("motivo")))
    if rotulos_genericos and not any(m.startswith("Columna sin rótulo") for m in motivos):
        motivos.append("columnas con rótulo genérico puesto en la revisión (" + ", ".join(rotulos_genericos[:3]) + ")")
    encabezado = [str(h).strip() for h in filas[0]]
    repetidos = []
    for h in encabezado:
        base = h.rsplit(" · ", 1)[1] if " · " in h else None
        m = re.fullmatch(r"(.+) \((\d+)\)", h)
        if m:
            base = m.group(1)
        if base and base != h and base in encabezado and base not in repetidos:
            repetidos.append(base)
    if repetidos:
        motivos.append("rótulo de columna repetido en la lectura (" + ", ".join(f"«{r}»" for r in repetidos[:3])
                       + "): no se sabe qué columna es cuál")
    cantidad = len(dudosas) + (len(rotulos_genericos) if rotulos_genericos else 0) + len(repetidos)
    if not cantidad:
        return {}
    salida = {"celdas_marcadas": cantidad, "motivos_marcadas": motivos}
    # Las celdas que la lectura pudo haber armado mal (no las que señalan un error del original, como un
    # total que no suma o un rótulo repetido): una señal sólo sobre ellas no llega al área como alta.
    de_lectura = [_celda_a1(d["fila"], d["columna"]) for d in dudosas
                  if str(d.get("motivo") or "").startswith(MOTIVOS_DE_LECTURA)]
    de_lectura += [_celda_a1(-1, j) for j, h in enumerate(filas[0]) if h in rotulos_genericos]
    if de_lectura:
        salida["celdas_lectura"] = sorted(set(de_lectura))
    return salida


def _cifras_revision(valor: str | None, leidos: list[tuple[str, bytes]]) -> dict:
    """Cifras del texto del PDF contra las de la tabla confirmada.

    Si la lectura dejó cifras afuera (un signo que no se reconoció, una fila perdida) o la tabla trae
    cifras que el texto no tiene (un cuadro impreso de costado, leído desarmado), el informe lo dice
    al comienzo aunque no se sepa por qué falló la lectura.
    """
    import csv
    import io
    import json

    from services import cobertura_cifras

    if not valor:
        return {}
    try:
        dato = json.loads(valor)
        filas_texto = [str(x) for x in (dato.get("filas") or [])][:5000]
        todas = [str(x) for x in (dato.get("todas") or filas_texto)][:20000]
        texto = leidos[0][1].decode("utf-8-sig", errors="replace")
        primera = texto.splitlines()[0] if texto else ""
        separador = ";" if primera.count(";") > primera.count(",") else ","
        filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
        if not filas or not filas_texto:
            fuera = str(dato.get("fuera_del_texto") or "").strip()
            return {"cifras": {"fuera_del_texto": fuera[:300]}} if fuera else {}
        # Sólo el cuerpo: una fila de datos tomada como encabezado no se analiza.
        comp = cobertura_cifras.comparar(filas_texto, cobertura_cifras.cifras_tabla([], filas[1:]), todas)
        palabras = {str(x) for x in (dato.get("palabras") or [])}
    except Exception:  # noqa: BLE001 — el conteo no puede impedir el análisis
        return {}
    comp["declarar_faltan"] = cobertura_cifras.declarable(comp["faltan"], comp["en_original"])
    comp["declarar_ajenas"] = cobertura_cifras.declarable(comp["ajenas"], comp["en_lectura"])
    if comp["declarar_ajenas"]:
        comp["celdas_ajenas"] = [_celda_a1(i, j) for i, j in cobertura_cifras.celdas_ajenas(filas[1:], todas)][:500]
    fuera = str(dato.get("fuera_del_texto") or "").strip()
    if fuera:
        comp["fuera_del_texto"] = fuera[:300]
    if palabras:
        # Rótulos (encabezado y primera columna) con palabras que el texto del PDF no tiene: la
        # lectura los mezcló («Rodado Msaquinaria») o se escribieron a mano en la revisión.
        genericas = {"concepto", "columna"}
        rotulos = [str(c) for c in filas[0]] + [str(f[0]) for f in filas[1:] if f]
        distintos = []
        for rotulo in rotulos:
            ajenas = [w for w in re.findall(r"[^\W\d_]{3,}", rotulo.lower()) if w not in palabras and w not in genericas]
            if ajenas and rotulo not in distintos:
                distintos.append(rotulo)
        if distintos:
            comp["rotulos_distintos"] = distintos[:4]
            comp["rotulos_distintos_n"] = len(distintos)
    return {"cifras": comp}



def _marcar_lectura_dudosa(hallazgos: list, lectura_revisada: dict) -> None:
    """Una señal cuyas celdas están todas entre las que el comienzo del informe declara como posiblemente
    mal leídas (cifras que el texto del PDF no tiene, un período vacío, más de un número en la celda) puede
    venir de la lectura y no del original: se marca para que no llegue al área como prioridad alta sin
    verificar antes la lectura. No se borra."""
    from services.casos_revision import referencias

    dudosas = set(lectura_revisada.get("celdas_lectura") or []) | set(
        (lectura_revisada.get("cifras") or {}).get("celdas_ajenas") or [])
    if not dudosas:
        return
    for h in hallazgos:
        e = h.get("evidencia") if isinstance(h, dict) else None
        if not isinstance(e, dict):
            continue
        celdas = {str(r).rsplit("!", 1)[-1].replace("$", "") for r in referencias(e)}
        if celdas and celdas <= dudosas:
            e["lectura_dudosa"] = True


def _derivados_revision(valor: str | None) -> list[str]:
    """Nombres de archivos de la misma carga que se derivaron a la revisión de lectura."""
    nombres = []
    for nombre in str(valor or "").split("\n"):
        limpio = re.sub(r"[\x00-\x1f\x7f]", "", nombre.replace("\\", "/").rsplit("/", 1)[-1]).strip()[:200]
        if limpio and limpio not in nombres:
            nombres.append(limpio)
    return nombres[:20]


def _limpiar_email_notificaciones(valor: str | None) -> str | None:
    email = str(valor or "").strip().lower()
    if not email:
        return None
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "correo de notificaciones inválido")
    return email


def _limpiar_orientacion_analisis(valor: str | None) -> str | None:
    """Normaliza la pregunta opcional sin convertirla en una instrucción técnica.

    La orientación se conserva como contexto trazable. No reemplaza el barrido
    abierto ni permite modificar las reglas, lentes o guardrails del análisis.
    """
    orientacion = " ".join(str(valor or "").split())
    if not orientacion:
        return None
    if len(orientacion) > MAX_ORIENTACION_ANALISIS:
        raise HTTPException(
            422,
            f"la orientación del análisis no puede superar {MAX_ORIENTACION_ANALISIS} caracteres",
        )
    # La pregunta viaja a los proveedores de triangulación: pasa por la misma
    # redacción que el texto libre de la tabla.
    return sanitizacion_svc.redactar_texto_libre(orientacion)


def _email_usuario_valido(usuario: models.Usuario) -> str | None:
    email = str(usuario.email or "").strip().lower()
    return email if EMAIL_RE.match(email) else None


def _area_generica(db: Session) -> models.Area:
    area = db.query(models.Area).filter(models.Area.codigo == AREA_GENERICA_CODIGO).first()
    if area:
        return area
    area = models.Area(nombre=AREA_GENERICA_NOMBRE, codigo=AREA_GENERICA_CODIGO)
    db.add(area)
    db.flush()
    return area



def _parseables_fecha(datos: list[dict], col: str) -> int:
    return sum(1 for fila in datos if perfilado.fecha(fila.get(col)) is not None)


def _detectar_tabla_larga(datos: list[dict]) -> dict:
    if len(datos) < 10:
        return {}
    perfiles = perfilado.perfilar(datos)
    temporales = perfilado.columnas_temporales(perfiles)
    nums = perfilado.columnas_numericas(datos)
    if not temporales or not nums:
        return {}

    tcol = max(temporales, key=lambda c: _parseables_fecha(datos, c))
    periodos = {str(fila.get(tcol) or "").strip() for fila in datos if perfilado.fecha(fila.get(tcol)) is not None}
    if len(periodos) < 5:
        return {}

    columnas_num = set(nums)
    candidatos = []
    total = max(len(datos), 1)
    columnas = sorted({c for fila in datos for c in fila.keys()})
    for col in columnas:
        if col == tcol or col in columnas_num:
            continue
        valores = [str(fila.get(col) or "").strip() for fila in datos]
        no_vacios = [v for v in valores if v]
        unicos = sorted(set(no_vacios))
        if len(no_vacios) / total < 0.7:
            continue
        if 2 <= len(unicos) <= min(800, max(3, total // 2)) and total >= len(periodos) * min(len(unicos), 3):
            candidatos.append((len(unicos), col, unicos))
    if not candidatos:
        return {}

    candidatos.sort(key=lambda item: item[0])
    _, dcol, categorias = candidatos[0]
    return {
        "formato": "largo",
        "columna_periodo": tcol,
        "columna_dimension": dcol,
        "columnas_valor": nums,
        "periodos_detectados": len(periodos),
        "series_detectadas": len(categorias),
        "categorias_muestra": categorias[:8],
    }


def _es_nivel_general(valor: object) -> bool:
    norm = perfilado.normalizar_texto(valor).replace(" ", "_")
    return bool(
        norm in {"total", "total_general", "nivel_general", "ng_nivel_general"}
        or "nivel_general" in norm
        or norm.startswith("ng_")
    )


def _es_apertura_principal(valor: object) -> bool:
    norm = perfilado.normalizar_texto(valor).replace(" ", "_")
    if _es_nivel_general(norm):
        return True
    if re.match(r"^[a-z]_[a-z]", norm):
        return True
    if re.match(r"^\d{1,2}_[a-z]", norm):
        return True
    return False


def _aplicar_alcance_series(datos: list[dict], alcance: str) -> tuple[list[dict], dict]:
    alcance = alcance if alcance in ALCANCES_SERIES else "todas"
    meta = _detectar_tabla_larga(datos)
    if not meta:
        return datos, {"alcance_solicitado": alcance, "formato": "ancho_o_simple"}

    dcol = meta["columna_dimension"]
    solicitado = alcance
    if alcance == "auto":
        alcance = "principales" if meta["series_detectadas"] > 40 else "todas"

    if alcance == "todas":
        filtrados = datos
    elif alcance == "nivel_general":
        filtrados = [fila for fila in datos if _es_nivel_general(fila.get(dcol))]
    else:
        filtrados = [fila for fila in datos if _es_apertura_principal(fila.get(dcol))]

    fallback = False
    if not filtrados:
        filtrados = datos
        alcance = "todas"
        fallback = True

    categorias = sorted({str(fila.get(dcol) or "").strip() for fila in filtrados if str(fila.get(dcol) or "").strip()})
    meta.update({
        "alcance_solicitado": solicitado,
        "alcance_aplicado": alcance,
        "fallback_sin_coincidencias": fallback,
        "filas_entrada": len(datos),
        "filas_analizadas": len(filtrados),
        "series_analizadas": len(categorias),
        "categorias_analizadas_muestra": categorias[:12],
    })
    return filtrados, meta



def _int_meta(valor: object) -> int | None:
    try:
        return int(float(str(valor)))
    except (TypeError, ValueError):
        return None


def _bool_meta(valor: object) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor or "").lower() in {"1", "true", "si", "sí", "yes"}


def _cuadros_sin_separar(filas_pdf: list[dict]) -> tuple[int, int, int, int]:
    """Cuadros cuyas celdas quedaron con varios números juntos, y cuántas filas involucran.

    Un encabezado de dos niveles o columnas muy juntas hacen que el texto de tres columnas caiga en
    una sola celda. Esas filas se leyeron, pero no son una tabla: contarlas como filas revisables
    sería declarar una cobertura que no existe.
    """
    cuadros: dict[tuple, list[dict]] = {}
    for fila in filas_pdf:
        clave = (fila.get("archivo_origen"), fila.get("pagina_pdf"), fila.get("tabla_pdf"))
        cuadros.setdefault(clave, []).append(fila)
    sin_separar = 0
    sin_rotulos = 0
    filas_afectadas = 0
    for filas in cuadros.values():
        malas = [f for f in filas if carga_archivos.fila_sin_separar(f)]
        if malas and len(malas) >= 0.5 * len(filas):
            sin_separar += 1
            filas_afectadas += len(filas)
        elif carga_archivos.rotulos_poco_confiables(filas[0]):
            sin_rotulos += 1
            filas_afectadas += len(filas)
    return len(cuadros), sin_separar, sin_rotulos, filas_afectadas


def _resumen_pdf(datos: list[dict], limite_paginas_pdf: int, lectura: list[dict] | None = None) -> dict:
    filas_pdf = [
        fila for fila in datos
        if str(fila.get("archivo_origen") or "").lower().endswith(".pdf")
        or str(fila.get("extraccion_pdf") or "").lower() in {"tabla", "texto_por_pagina"}
    ]
    if not filas_pdf:
        return {}

    archivos = sorted({str(fila.get("archivo_origen") or "PDF") for fila in filas_pdf})
    # Páginas por archivo y luego la suma: dos PDF de 100 páginas son 200 páginas leídas, no 100.
    por_archivo: dict[str, dict] = {}
    for fila in filas_pdf:
        nombre = str(fila.get("archivo_origen") or "PDF")
        d = por_archivo.setdefault(nombre, {"archivo": nombre, "paginas_documento": None,
                                            "paginas_analizadas": None, "truncado_por_paginas": False,
                                            "solo_texto": True})
        for clave, origen in (("paginas_documento", "paginas_documento"), ("paginas_analizadas", "paginas_pdf_analizadas")):
            v = _int_meta(fila.get(origen))
            if v is not None:
                d[clave] = max(d[clave] or 0, v)
        d["truncado_por_paginas"] = d["truncado_por_paginas"] or _bool_meta(fila.get("pdf_truncado_por_paginas"))
        if str(fila.get("extraccion_pdf") or "") != "texto_por_pagina":
            d["solo_texto"] = False
    paginas_documento = [d["paginas_documento"] for d in por_archivo.values() if d["paginas_documento"] is not None]
    paginas_analizadas = [d["paginas_analizadas"] for d in por_archivo.values() if d["paginas_analizadas"] is not None]
    avisos = []
    for d in por_archivo.values():
        if d["truncado_por_paginas"]:
            avisos.append(carga_archivos.aviso_truncado_pdf(
                d["archivo"], d["paginas_documento"], d["paginas_analizadas"], limite_paginas_pdf, d.pop("solo_texto")))
        else:
            d.pop("solo_texto")
    descartados = []
    sin_texto = 0
    for info in lectura or []:
        if info.get("archivo") in por_archivo:
            if info.get("paginas_sin_texto"):
                por_archivo[info["archivo"]]["paginas_sin_texto"] = list(info["paginas_sin_texto"])
                sin_texto += len(info["paginas_sin_texto"])
            descartados.extend({"archivo": info["archivo"], **b} for b in info.get("bloques_descartados") or [])
            avisos.extend(a for a in info.get("avisos", []) if a not in avisos and "páginas" not in a)
    modos = sorted({
        str(fila.get("extraccion_pdf") or "").strip()
        for fila in filas_pdf
        if str(fila.get("extraccion_pdf") or "").strip()
    })
    truncado = any(_bool_meta(fila.get("pdf_truncado_por_paginas")) for fila in filas_pdf)

    cuadros, sin_separar, sin_rotulos, filas_no_revisables = _cuadros_sin_separar(filas_pdf)
    return {
        "archivos": archivos,
        "cantidad_archivos": len(archivos),
        "filas_pdf": len(filas_pdf),
        "filas_pdf_utiles": len(filas_pdf) - filas_no_revisables,
        "cuadros_pdf": cuadros,
        "cuadros_pdf_sin_separar": sin_separar,
        "cuadros_pdf_sin_rotulos": sin_rotulos,
        "modos_extraccion": modos,
        "paginas_documento": sum(paginas_documento) if paginas_documento else None,
        "paginas_analizadas": sum(paginas_analizadas) if paginas_analizadas else None,
        # Páginas dentro del rango analizado que no tienen texto (escaneadas): no se leyeron.
        "paginas_sin_texto": sin_texto,
        "limite_paginas_pdf": limite_paginas_pdf,
        "truncado_por_paginas": truncado,
        "por_archivo": list(por_archivo.values()),
        "bloques_descartados": descartados,
        "avisos": avisos,
    }


def _inferir_dominio(datos: list[dict], dominio: str, ambito: str = ambito_svc.PUBLICO) -> str:
    """Solo infiere cuando el llamador no eligio dominio explicitamente
    ("auto", el default). Un dominio explicito (incluido "general" elegido
    a proposito desde la UI) gana siempre sobre la inferencia. En una
    organización nunca se infiere el dominio presupuestario público: sus
    rótulos ("presupuesto vigente", "pagado") no implican ese régimen."""
    if dominio != "auto":
        return dominio
    if not datos:
        return "general"
    columnas = " ".join(str(c).lower() for fila in datos for c in fila.keys())
    claves = ["credito", "crédito", "sancionado", "vigente", "definitivo", "devengado", "pagado", "compromiso", "presupuesto"]
    if ambito == ambito_svc.PUBLICO and sum(1 for clave in claves if clave in columnas) >= 2:
        return "presupuestario"
    claves_servicios = ["consultas", "resueltas", "pendientes", "satisfaccion", "satisfacción", "atencion", "atención", "canal", "tiempo_resolucion"]
    if sum(1 for clave in claves_servicios if clave in columnas) >= 2:
        return "servicios_atencion"
    return "general"


def _fechas_a_texto(valor: Any) -> Any:
    """Las celdas con fecha de un Excel (series mensuales) se guardan como texto ISO: JSONB no acepta datetime."""
    if isinstance(valor, dict):
        return {k: _fechas_a_texto(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_fechas_a_texto(v) for v in valor]
    if isinstance(valor, datetime.datetime):
        return valor.date().isoformat() if valor.time() == datetime.time() else valor.isoformat()
    if isinstance(valor, (datetime.date, datetime.time)):
        return valor.isoformat()
    return valor


@router.post("/analisis-rapido", response_model=Union[schemas.EnqueueAnalisisOut, schemas.InterpretacionPreviaOut])
async def analisis_rapido(
    archivos: list[UploadFile] = File(...),
    area_id: Optional[int] = Form(None),
    periodo: Optional[str] = Form(None),
    dominio: str = Form("auto"),
    revisar_formulas_excel: bool = Form(False),
    inferir_patrones_calculo: bool = Form(False),
    revisar_metodo_calculo: bool = Form(False),
    alcance_series: str = Form("todas"),
    modo_uso_multilente: str = Form("informe_en_construccion"),
    ambito: str = Form(ambito_svc.PUBLICO),
    orientacion_analisis: Optional[str] = Form(None),
    limite_paginas_pdf: int = Form(carga_archivos.DEFAULT_LIMITE_PAGINAS_PDF),
    modelos: list[str] = Form(default=[]),
    notify_email: Optional[str] = Form(None),
    guardar_notify_email: bool = Form(False),
    notificar: bool = Form(True),
    contexto_validacion: Optional[str] = Form(None),
    informe_anterior_id: Optional[int] = Form(None),
    origen_lectura: Optional[str] = Form(None),
    derivados_revision: Optional[str] = Form(None),
    cifras_original: Optional[str] = Form(None),
    archivo_original: Optional[str] = Form(None),
    interpretacion_accion: str = Form("preparar"),
    interpretacion_id: Optional[int] = Form(None),
    interpretacion_revision: Optional[int] = Form(None),
    interpretacion_correcciones: Optional[str] = Form(None),
    # Rápida por defecto: la pantalla manda siempre el modo; quien llama a la API sin indicarlo recibe la revisión
    # sin IA ni confirmación.
    modo_revision: str = Form("rapida"),
    # «Es una prueba (no cuenta para las mediciones)»: lo marca quien carga; la medición excluye esos informes.
    es_prueba: bool = Form(False),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    if usuario.rol == "lector":
        raise HTTPException(403, "el rol lector no puede cargar informes")
    if not archivos:
        raise HTTPException(422, "subí al menos un archivo")
    if len(archivos) > MAX_ARCHIVOS:
        raise HTTPException(422, f"máximo {MAX_ARCHIVOS} archivos por carga")
    if modo_revision not in MODOS_REVISION:
        raise HTTPException(422, "modo_revision debe ser rapida o profunda")
    # La revisión rápida no tiene interpretación que confirmar ni releer: sólo se prepara la carga.
    rapida = modo_revision == "rapida"
    if rapida and (interpretacion_accion != "preparar" or interpretacion_id):
        raise HTTPException(422, "La revisión rápida no usa interpretación previa: para confirmar o releer, pedí la revisión profunda.")
    if interpretacion_accion not in {"preparar", "confirmar", "detallada"}:
        raise HTTPException(422, "Acción de interpretación desconocida")
    if interpretacion_accion != "preparar" and not interpretacion_id:
        raise HTTPException(422, "Primero prepará la interpretación del archivo")
    if len({a.filename for a in archivos}) != len(archivos):
        raise HTTPException(422, "Los archivos de una carga deben tener nombres diferentes")

    leidos: list[tuple[str, bytes]] = []
    originales: list[tuple[str, bytes]] = []
    estrictos: set[str] = set()
    recortes: dict[str, list[str]] = {}
    # Un archivo que supera el tope se rechaza sin cargarlo entero en memoria: por su tamaño, que Starlette conoce al
    # recibirlo, o leyendo como mucho un byte más que el tope.
    for archivo in archivos:
        if (archivo.size or 0) > MAX_BYTES_POR_ARCHIVO:
            raise _archivo_grande(archivo.filename)
    for archivo in archivos:
        contenido = await archivo.read(MAX_BYTES_POR_ARCHIVO + 1)
        if len(contenido) > MAX_BYTES_POR_ARCHIVO:
            raise _archivo_grande(archivo.filename)
        originales.append((archivo.filename or "archivo", contenido))
        # Un libro Open XML estricto se convierte a .xlsx común una sola vez, a la entrada: así lo leen
        # igual la lectura y los controles que vuelven a abrir el archivo.
        transicional = carga_archivos.libro_transicional(contenido)
        if transicional is not contenido:
            estrictos.add(archivo.filename or "archivo")
        # Un libro que se rechazaría sólo por filas o columnas con formato se recorta al bloque con datos, también
        # una sola vez y a la entrada; el informe dice qué se recortó.
        transicional, avisos_recorte = await run_in_threadpool(
            carga_archivos.recortar_rango_inflado, archivo.filename or "archivo", transicional)
        if avisos_recorte:
            recortes[archivo.filename or "archivo"] = avisos_recorte
        # Un libro con más celdas de las que entran en la memoria del análisis se rechaza antes de leerlo,
        # con el motivo, en vez de dejar al servicio sin memoria a mitad del análisis.
        motivo = carga_archivos.motivo_libro_demasiado_grande(archivo.filename or "archivo", transicional)
        if motivo:
            raise HTTPException(422, motivo)
        leidos.append((archivo.filename or "archivo", transicional))

    # Los PDF y las imágenes no se analizan directo: pasan antes por la revisión de lectura.
    revisar = [nombre for nombre, contenido in leidos if carga_archivos.requiere_revision_lectura(nombre, contenido)]
    if revisar:
        raise HTTPException(422, detail=_aviso_revision_lectura(revisar, [nombre for nombre, _ in leidos]))
    lectura_revisada = _lectura_revisada(origen_lectura, archivo_original, leidos)

    if limite_paginas_pdf < carga_archivos.MIN_PAGINAS_PDF or limite_paginas_pdf > carga_archivos.MAX_PAGINAS_PDF:
        raise HTTPException(422, f"limite_paginas_pdf debe estar entre {carga_archivos.MIN_PAGINAS_PDF} y {carga_archivos.MAX_PAGINAS_PDF}")

    desconocidos = [m for m in modelos if m not in MODELOS_TRIANGULACION_VALIDOS]
    if desconocidos:
        raise HTTPException(
            422,
            f"modelos desconocidos: {', '.join(desconocidos)}; válidos: {', '.join(sorted(MODELOS_TRIANGULACION_VALIDOS))}",
        )
    if modo_uso_multilente not in MODOS_USO_MULTILENTE:
        raise HTTPException(422, 'modo_uso_multilente debe ser revision_final o informe_en_construccion')
    if ambito not in ambito_svc.AMBITOS:
        raise HTTPException(422, "ambito debe ser publico u organizacion")
    orientacion_limpia = _limpiar_orientacion_analisis(orientacion_analisis)
    if not rapida:
        # La rápida no llama a la IA: no consume el cupo diario de análisis con IA.
        cuota_ia.verificar_analisis(db, usuario)
    try:
        contexto = schemas.ContextoValidacion.model_validate_json(contexto_validacion) if contexto_validacion else schemas.ContextoValidacion()
    except ValueError:
        raise HTTPException(422, "contexto_validacion debe ser un contrato JSON válido")
    modelos_elegidos = modelos or None
    notify_email_limpio = _limpiar_email_notificaciones(notify_email)
    opciones_interpretacion = dict(area_id=area_id, periodo=periodo, dominio=dominio, ambito=ambito,
        alcance_series=alcance_series, revisar_formulas_excel=revisar_formulas_excel,
        inferir_patrones_calculo=inferir_patrones_calculo, revisar_metodo_calculo=revisar_metodo_calculo,
        orientacion=orientacion_limpia, modo=modo_uso_multilente, contexto=contexto.model_dump(),
        anterior=informe_anterior_id, origen_lectura=origen_lectura, archivo_original=archivo_original,
        derivados_revision=derivados_revision, cifras_original=cifras_original, limite_paginas_pdf=limite_paginas_pdf)

    def _procesar() -> schemas.EnqueueAnalisisOut:
        borrador = None
        previa = None
        base_borrador = None
        if interpretacion_id:
            borrador = db.get(models.Informe, interpretacion_id)
            if not borrador or borrador.usuario_id != usuario.id:
                raise HTTPException(404, "Interpretación no disponible")
            previa = (borrador.saneamiento or {}).get(interpretacion_svc.CAMPO)
            base_borrador = deepcopy(borrador.saneamiento)
            if not previa or borrador.devolucion or previa.get("estado") != "pendiente_confirmacion":
                raise HTTPException(409, "Esta interpretación ya se utilizó. Prepará una nueva carga.")
            if previa.get("revision") != interpretacion_revision:
                raise HTTPException(409, "La interpretación cambió; revisá la versión actual antes de confirmar.")
        try:
            datos, cobertura_excel, lectura_archivos = carga_archivos.parse_archivos_con_lectura(
                leidos, limite_paginas_pdf=limite_paginas_pdf
            )
            for a in lectura_archivos:
                if a.get("archivo") in estrictos:
                    a.setdefault("avisos", []).insert(0, f"«{a['archivo']}»: {carga_archivos.AVISO_ESTRICTO}")
                if a.get("archivo") in recortes:
                    a.setdefault("avisos", []).extend(recortes[a["archivo"]])
            # Un archivo que no se pudo leer queda declarado y fuera de los análisis siguientes,
            # que vuelven a abrir los archivos.
            # Filas tal como se leyeron (con página y cuadro de origen en los PDF), antes de normalizar.
            datos_leidos = [dict(f) for f in datos]
            fallidos = {a["archivo"] for a in lectura_archivos if a.get("estado") == "fallido"}
            leidos_ok = [(nombre, contenido) for nombre, contenido in leidos if nombre not in fallidos]
            if alcance_series not in ALCANCES_SERIES:
                raise HTTPException(422, "alcance_series debe ser auto, nivel_general, principales o todas")
            if cobertura_excel:
                datos_saneados, reporte_excel, normalizacion_series = excel_cobertura.preparar(
                    datos, cobertura_excel, lambda filas: _aplicar_alcance_series(filas, alcance_series), sanitizacion_svc.sanear)
            else:
                datos, normalizacion_series = _aplicar_alcance_series(datos, alcance_series)
                datos_saneados, reporte_excel = sanitizacion_svc.sanear(datos)
            if not datos_saneados or not any(datos_saneados):
                hojas = (cobertura_excel or {}).get("hojas") or []
                if hojas and all(h.get("estado") == "sin_datos" and not h.get("no_revisada") for h in hojas):
                    raise HTTPException(422, "SIN_ANALISIS_NUMERICO: El archivo contiene texto o referencias sin una tabla cuantitativa. No hay controles numéricos aplicables.")
                raise HTTPException(422, "No quedaron datos agregados para interpretar: " + carga_archivos.motivo_sin_datos(lectura_archivos, cobertura_excel))
            # Esta fase sólo prepara datos. Ningún control sustantivo se ejecuta antes de confirmar.
            from services import lector_mapa
            reporte_excel["archivos_origen"] = [n for n, _ in leidos]
            reporte_excel["lectura_archivos"] = lectura_archivos
            reporte_excel["avisos_lectura"] = carga_archivos.avisos_lectura(lectura_archivos)
            try:
                reporte_excel["grillas_lectura"] = lector_mapa.grillas(leidos_ok)
            except Exception:
                raise HTTPException(503, "No se pudo preparar la representación para la interpretación previa. No se ejecutaron controles; conservá los archivos y reintentá.")
            datos_saneados = _fechas_a_texto(datos_saneados)
            anterior_previo = db.get(models.Informe, informe_anterior_id) if informe_anterior_id else None
            if informe_anterior_id and (not anterior_previo or (usuario.rol != "admin" and anterior_previo.usuario_id != usuario.id)):
                raise HTTPException(404, "informe anterior no disponible")
            reporte_excel["contexto_validacion"] = contexto.model_dump()
            if anterior_previo and not contexto.esquema_esperado:
                from services.validez import esquema
                reporte_excel["contexto_validacion"]["esquema_esperado"] = esquema(anterior_previo.datos or [])
            reporte_excel["proveniencia"] = proveniencia.registrar(originales, datos_saneados, reporte_excel, usuario.id,
                {a.filename: a.content_type for a in archivos}, anterior_previo)
            if not rapida and interpretacion_accion in {"preparar", "detallada"}:
                if previa and (previa.get("archivos") != interpretacion_svc.archivos_huella(originales)
                               or previa.get("opciones_huella") != interpretacion_svc.huella(opciones_interpretacion)):
                    raise HTTPException(409, "Cambió el archivo o las opciones: prepará una nueva interpretación.")
                cuota_ia.reservar_interpretacion(db, usuario, detallada=interpretacion_accion == "detallada", informe_id=interpretacion_id)
                interpretacion = interpretacion_svc.lectura_pendiente(datos_saneados, originales,
                    opciones_interpretacion, usuario.id, anterior=previa)
                reporte_excel[interpretacion_svc.CAMPO] = interpretacion
                reporte_excel["opciones_tecnicas"] = opciones_interpretacion
                if area_id is not None:
                    area = db.get(models.Area, area_id)
                    if not area:
                        raise HTTPException(404, "área no encontrada")
                else:
                    area = _area_generica(db)
                if borrador is None:
                    borrador = models.Informe(area_id=area.id,
                        periodo=periodo or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m"),
                        dominio="general", modo="intraarea", usuario_id=usuario.id, creado_por=usuario.email,
                        datos=datos_saneados, saneamiento=_fechas_a_texto(reporte_excel))
                    db.add(borrador)
                else:
                    # Compare-and-swap: una relectura concurrente no pisa una confirmación.
                    viejo = base_borrador
                    actualizados = db.query(models.Informe).filter(models.Informe.id == borrador.id,
                        models.Informe.saneamiento == viejo).update(
                        {models.Informe.saneamiento: _fechas_a_texto(reporte_excel)}, synchronize_session=False)
                    if actualizados != 1:
                        db.rollback()
                        raise HTTPException(409, "La interpretación cambió en otra solicitud.")
                db.flush()
                db.refresh(borrador)
                job_lectura = jobs_svc.enqueue_interpretacion(db, borrador, usuario, opciones_interpretacion,
                    detallada=interpretacion_accion == "detallada")
                return schemas.InterpretacionPreviaOut(informe_id=borrador.id, estado="interpretando",
                    interpretacion=interpretacion_svc.publico(interpretacion), job=schemas.AnalysisJobOut.model_validate(job_lectura))
            if rapida:
                # Sin IA ni confirmación: la interpretación se registra sola, con el plan aritmético, y queda la traza.
                interpretacion = interpretacion_svc.revision_rapida(datos_saneados, reporte_excel, originales,
                    opciones_interpretacion, usuario.id)
            else:
                try:
                    correcciones = json.loads(interpretacion_correcciones) if interpretacion_correcciones else {}
                except (ValueError, TypeError):
                    raise HTTPException(422, "Las modificaciones deben ser un objeto JSON válido")
                interpretacion = interpretacion_svc.confirmar(previa, usuario_id=usuario.id,
                    revision=interpretacion_revision, leidos=originales, datos=datos_saneados,
                    opciones=opciones_interpretacion, correcciones=correcciones)
                # Reclamo atómico dentro de la misma transacción. Fallar revierte el reclamo;
                # confirmar dos veces no produce dos análisis ni dos conjuntos de controles.
                viejo = base_borrador
                actualizados = db.query(models.Informe).filter(models.Informe.id == borrador.id,
                    models.Informe.saneamiento == viejo).update(
                    {models.Informe.saneamiento: {**viejo, interpretacion_svc.CAMPO: interpretacion}}, synchronize_session=False)
                if actualizados != 1:
                    db.rollback()
                    raise HTTPException(409, "Otra solicitud ya modificó o confirmó esta interpretación.")
            interpretacion_svc.declarar(interpretacion)
            formula_hallazgos = (
                formula_integridad.analizar_archivos(
                    leidos_ok,
                    detectar_formulas=revisar_formulas_excel,
                    inferir_patrones=inferir_patrones_calculo,
                )
                if revisar_formulas_excel or inferir_patrones_calculo
                else []
            )
            matematico_hallazgos = (
                formula_integridad.analizar_matematico_archivos(leidos_ok)
                if revisar_metodo_calculo
                else []
            )
            matematico_hallazgos.extend(pdf_controles.analizar(datos))
            # Una contradicción entre el texto destacado y la tabla del mismo
            # documento es coherencia interna (Ajedrecista), no pertinencia del
            # método estadístico (Matemático).
            formula_hallazgos.extend(pdf_controles.analizar_coherencia_visual(leidos_ok, datos))
        except HTTPException:
            raise
        except carga_archivos.ArchivoNoSoportado as e:
            raise HTTPException(422, str(e))
        except Exception:  # noqa: BLE001 — errores de parseo (excel corrupto, csv mal formado, etc.)
            logger.exception("no se pudo leer un archivo subido")
            raise HTTPException(422, "No se pudo leer alguno de los archivos: puede estar dañado o tener un formato "
                                     "que no reconocemos. Probá guardarlo de nuevo como .xlsx o .csv.")

        if not datos:
            raise HTTPException(422, "los archivos no tienen filas con datos: "
                                     + carga_archivos.motivo_sin_datos(lectura_archivos, cobertura_excel))

        if cobertura_excel:
            reporte = reporte_excel
        else:
            datos_saneados, reporte = sanitizacion_svc.sanear(datos)
        reporte[interpretacion_svc.CAMPO] = interpretacion
        # También el CSV conserva el material de la lectura previa aunque el lector antiguo esté apagado.
        reporte["grillas_lectura"] = reporte_excel["grillas_lectura"]
        if cobertura_excel:
            from services import controles_excel
            reporte["controles_tabulares"] = controles_excel.analizar(leidos_ok, datos_saneados, reporte["excel"])
            reporte["excel"]["lectura"] = controles_excel.cobertura_lectura(leidos_ok, datos_saneados, reporte["excel"])
            reporte["version_controles_tabulares"] = 2
            reporte["estructura_revision"] = reporte["excel"].pop("estructura_revision", {})
            from services import semantica_excel
            reporte["contexto_semantico"] = semantica_excel.extraer(leidos_ok, datos_saneados, reporte["excel"])
        # La lectura ya ocurrió antes de confirmar. El motor sólo verificará esas propuestas.
        # Tablas de CSV y de PDF con texto: los mismos controles por celda que un Excel.
        from services.controles_excel import tablas_planas
        planos, resumen_planos = tablas_planas.analizar(
            leidos_ok, datos_leidos, lectura_archivos,
            lambda filas: _aplicar_alcance_series(filas, alcance_series), sanitizacion_svc.sanear)
        if resumen_planos:
            reporte["controles_tablas_planas"] = resumen_planos
            reporte.setdefault("controles_tabulares", []).extend(planos)
            estructuras = [r.get("estructura") or {} for r in resumen_planos]
            if cobertura_excel:
                # Carga mixta: los cierres de las tablas de CSV o PDF se suman a los del Excel.
                er = reporte.setdefault("estructura_revision", {})
                # Aparte de los del Excel: si el Excel no pudo comprobar sus totales, se sigue diciendo por qué.
                er["cierres_planos"] = sum(int(e.get("cantidad_cierres") or 0) + int(e.get("cierres_columna") or 0)
                                           for e in estructuras)
                er["cierres_verificados"] = list(er.get("cierres_verificados") or []) + [
                    x for e in estructuras for x in (e.get("cierres_verificados") or [])]
                er["cierres_sin_comprobar"] = ((er.get("cierres_sin_comprobar") or [])
                                               + [x for e in estructuras for x in (e.get("cierres_sin_comprobar") or [])])[:30]
                for clave in ("totales_separados", "jerarquia_sin_comprobar", "totales_aparentes_sin_comprobar"):
                    extra = [x for e in estructuras for x in (e.get(clave) or [])]
                    if extra:
                        er[clave] = ((er.get(clave) or []) + extra)[:30]
            else:
                # Sin Excel, la estructura de totales sale de las tablas de CSV o PDF: así el informe dice
                # cuántos cierres comprobó o por qué no pudo comprobar ninguno.
                cierres = sum(int(e.get("cantidad_cierres") or 0) for e in estructuras)
                reporte["estructura_revision"] = {
                    "version": 1, "origen": "tablas_planas", "cantidad_cierres": cierres,
                    "cierres_columna": sum(int(e.get("cierres_columna") or 0) for e in estructuras),
                    "relaciones_candidatas": sum(int(e.get("relaciones_candidatas") or 0) for e in estructuras),
                    "motivo_sin_cierres": None if cierres else next(
                        (e["motivo_sin_cierres"] for e in estructuras if e.get("motivo_sin_cierres")), None),
                    "cierres_sin_comprobar": [x for e in estructuras for x in (e.get("cierres_sin_comprobar") or [])][:30],
                    "totales_separados": [x for e in estructuras for x in (e.get("totales_separados") or [])][:30],
                    "jerarquia_sin_comprobar": [x for e in estructuras for x in (e.get("jerarquia_sin_comprobar") or [])][:30],
                    "totales_aparentes_sin_comprobar": [
                        x for e in estructuras for x in (e.get("totales_aparentes_sin_comprobar") or [])][:30],
                }
        reporte["opciones_tecnicas"] = {
            "revisar_formulas_excel": revisar_formulas_excel,
            "inferir_patrones_calculo": inferir_patrones_calculo,
            "revisar_metodo_calculo": revisar_metodo_calculo,
            "alcance_series": alcance_series,
            "modo_uso_multilente": modo_uso_multilente,
            "ambito": ambito,
            "orientacion_analisis": orientacion_limpia,
            "limite_paginas_pdf": limite_paginas_pdf,
        }
        pdf_meta = _resumen_pdf(datos, limite_paginas_pdf, lectura_archivos)
        if pdf_meta:
            reporte["pdf"] = pdf_meta
        # Lectura por archivo (tipo de lectura, formato numérico, celdas no interpretables,
        # filas de nota, fallos) y sus avisos en texto, para que el informe los muestre.
        reporte["lectura_archivos"] = lectura_archivos
        reporte["avisos_lectura"] = carga_archivos.avisos_lectura(lectura_archivos)
        try:
            from services import cobertura_cifras

            # Cifras del archivo original que no llegaron a los datos analizados, por archivo. Una tabla de la
            # revisión de lectura se compara con el texto del PDF (cifras_original), no consigo misma.
            if not lectura_revisada:
                reporte["cobertura_cifras"] = cobertura_cifras.por_archivo(
                    leidos_ok, datos_leidos, (cobertura_excel or {}).get("hojas"))
        except Exception:  # noqa: BLE001 — el conteo no puede impedir el análisis
            logger.exception("no se pudo contar las cifras del original")
        # Si la persona no declara período se usa el mes de carga: el informe no debe presentarlo como declarado.
        reporte["periodo_declarado"] = bool((periodo or "").strip())
        reporte["normalizacion_series"] = normalizacion_series
        reporte["modo_uso_multilente"] = modo_uso_multilente
        reporte["ambito"] = ambito
        reporte["orientacion_analisis"] = orientacion_limpia
        reporte["archivos_origen"] = [nombre for nombre, _ in leidos]
        # Qué revisión fue, para el informe, la pantalla y el historial.
        reporte["modo_revision"] = modo_revision
        if es_prueba:
            reporte["es_prueba"] = True  # fuera de las mediciones (scripts/indicador_valor.py)
        if rapida:
            reporte["revision_rapida"] = {"sin_ia": True, "no_corrieron": interpretacion_svc.no_corrieron_rapida(len(leidos)),
                                          "presupuesto": any(u["plan"].get("presupuesto") for u in interpretacion["cuadros"])}
        if lectura_revisada:
            lectura_revisada["usuario_id"] = usuario.id
            lectura_revisada.update(_celdas_marcadas_revision(leidos))
            lectura_revisada.update(_cifras_revision(cifras_original, leidos))
            reporte["lectura_revisada"] = lectura_revisada
            _marcar_lectura_dudosa(reporte.get("controles_tabulares") or [], lectura_revisada)
        derivados = _derivados_revision(derivados_revision)
        if derivados:
            reporte["derivados_revision_lectura"] = derivados
        reporte["origen_excel"] = {}  # Las coordenadas de Excel están en cada cuadro de reporte["excel"].
        anterior = db.get(models.Informe, informe_anterior_id) if informe_anterior_id else None
        if informe_anterior_id and (not anterior or (usuario.rol != "admin" and anterior.usuario_id != usuario.id)):
            raise HTTPException(404, "informe anterior no disponible")
        reporte["contexto_validacion"] = contexto.model_dump()
        if anterior and not contexto.esquema_esperado:
            from services.validez import esquema
            reporte["contexto_validacion"]["esquema_esperado"] = esquema(anterior.datos or [])
        reporte["proveniencia"] = proveniencia.registrar(
            originales, datos_saneados, reporte, usuario.id,
            {a.filename: a.content_type for a in archivos}, anterior,
        )
        if formula_hallazgos:
            reporte["formula_hallazgos"] = formula_hallazgos
        if matematico_hallazgos:
            reporte["matematico_hallazgos"] = matematico_hallazgos
        if not datos_saneados or not datos_saneados[0]:
            raise HTTPException(
                422,
                "Todas las columnas identifican actores o documentos individuales "
                f"({', '.join(reporte['columnas_excluidas'])}). No hay ninguna columna de "
                "alcance agregado para analizar.",
            )

        if area_id is not None:
            area = db.get(models.Area, area_id)
            if not area:
                raise HTTPException(404, "área no encontrada")
        else:
            area = _area_generica(db)

        if guardar_notify_email:
            usuario.email_notificaciones = notify_email_limpio
            db.add(usuario)

        email_destino = (notify_email_limpio or usuario.email_notificaciones or _email_usuario_valido(usuario)) if notificar else None

        informe = borrador
        if informe is None:
            # Revisión rápida: no hubo borrador de interpretación; el informe se crea acá.
            informe = models.Informe(area_id=area.id,
                periodo=periodo or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m"),
                dominio="general", modo="intraarea", usuario_id=usuario.id, creado_por=usuario.email)
        informe.datos = _fechas_a_texto(datos_saneados)
        informe.saneamiento = _fechas_a_texto(reporte)
        dominios = {interpretacion_svc.dominio(u) for u in interpretacion["cuadros"]}
        informe.dominio = next(iter(dominios)) if len(dominios) == 1 else "general"
        db.add(informe)
        db.commit()
        db.refresh(informe)

        job = jobs_svc.enqueue_analysis(db, informe, usuario, [] if rapida else modelos_elegidos, notify_email=email_destino,
                                        modo_revision=modo_revision)
        actividad_svc.registrar(
            db,
            usuario=usuario,
            modulo="multilente",
            accion="analisis_rapido_encolado",
            resumen="Carga rapida de informe y solicitud de analisis",
            informe_id=informe.id,
            metadata={
                "archivos": len(leidos),
                "filas": len(datos_saneados),
                "dominio": informe.dominio,
                "modo_revision": modo_revision,
                "es_prueba": bool(es_prueba),
                "modelos": [] if rapida else (modelos_elegidos or []),
                "job_id": job.id,
                "alcance_series": alcance_series,
                "orientacion_analisis": bool(orientacion_limpia),
                "lectura_revisada": (lectura_revisada or {}).get("origen"),
            },
        )
        db.commit()
        return schemas.EnqueueAnalisisOut(informe_id=informe.id, job=schemas.AnalysisJobOut.model_validate(job))

    def _con_contexto():
        with interpretacion_svc.contexto(None):
            try:
                return _procesar()
            except Exception:
                db.rollback()
                raise
    return await run_in_threadpool(_con_contexto)


@router.get("/interpretacion-previa/{informe_id}")
def obtener_interpretacion_previa(informe_id: int, db: Session = Depends(get_db), usuario: models.Usuario = Depends(get_current_user)):
    informe = db.get(models.Informe, informe_id)
    if not informe or (informe.usuario_id != usuario.id and usuario.rol != "admin"):
        raise HTTPException(404, "Interpretación no disponible")
    r = (informe.saneamiento or {}).get(interpretacion_svc.CAMPO)
    if not r:
        raise HTTPException(409, "No hay una interpretación previa preparada")
    job = jobs_svc.latest_job(db, informe.id)
    if r.get("estado") == "interpretando" and job and job.estado == "error":
        cancelada = bool((job.resultado or {}).get("cancelada"))
        return {"informe_id": informe.id, "estado": "error", "cancelada": cancelada,
                "error": jobs_svc.LECTURA_CANCELADA if cancelada else "La lectura previa no se completó. No se ejecutaron controles; volvé a preparar la carga."}
    salida = {"informe_id": informe.id, "estado": r["estado"], "interpretacion": interpretacion_svc.publico(r)}
    if r.get("estado") == "interpretando" and job:
        salida["avance"] = (job.resultado or {}).get("avance_lectura")  # cuadros leídos de cuántos
    return salida


@router.post("/interpretacion-previa/{informe_id}/cancelar")
def cancelar_interpretacion_previa(informe_id: int, db: Session = Depends(get_db), usuario: models.Usuario = Depends(get_current_user)):
    """Quien pidió la lectura (o administración) la cancela: la lectura en curso se detiene en el próximo cuadro
    leído, no se ejecutan controles y el trabajo no se retoma al reiniciar."""
    informe = db.get(models.Informe, informe_id)
    if not informe or (informe.usuario_id != usuario.id and usuario.rol != "admin"):
        raise HTTPException(404, "Interpretación no disponible")
    r = (informe.saneamiento or {}).get(interpretacion_svc.CAMPO) or {}
    job = jobs_svc.latest_job(db, informe.id)
    if r.get("estado") != "interpretando" or not job or job.estado not in jobs_svc.ESTADOS_ABIERTOS:
        raise HTTPException(409, "No hay una lectura en curso para cancelar")
    job.estado = "error"
    job.error = jobs_svc.LECTURA_CANCELADA
    job.finalizado_en = jobs_svc._now()
    job.resultado = dict(job.resultado or {}, cancelada=True)
    db.commit()
    return {"informe_id": informe.id, "estado": "cancelada"}
