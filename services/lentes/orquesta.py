"""Orquesta: coherencia sistémica.

Evalúa relaciones entre magnitudes agregadas: primero dentro del propio
informe si trae una serie temporal suficiente, y luego contra el historial
del área cuando existe.
"""
from __future__ import annotations

import re
from typing import Any

from services import perfilado

from .util import columnas_numericas, correlacion, suma_por_columna

UMBRAL_CORRELACION = 0.6
MAX_HALLAZGOS_OPERATIVOS = 2
MAX_HALLAZGOS_FISICO_FINANCIEROS = 2
ORIGEN_KEYS = ("archivo_origen", "fuente_archivo", "nombre_archivo")
META_KEYS = {
    "archivo_origen", "fuente_archivo", "nombre_archivo", "hoja", "hoja_origen",
    "pagina", "pagina_pdf", "pagina_pdf_impresa", "tabla_pdf", "fila_tabla_pdf",
    "extraccion_pdf", "tipo_documento",
}


def _col_por_patron(columnas: list[str], patron: str) -> str | None:
    rx = re.compile(patron, re.I)
    for col in columnas:
        if rx.search(perfilado.normalizar_texto(col)):
            return col
    return None


def _col_por_patrones(columnas: list[str], patrones: list[str]) -> str | None:
    for patron in patrones:
        col = _col_por_patron(columnas, patron)
        if col:
            return col
    return None


def _valor(fila: dict[str, Any], col: str | None) -> float | None:
    if not col:
        return None
    return perfilado.numero(fila.get(col))


def _archivo_origen(fila: dict[str, Any]) -> str | None:
    for key in ORIGEN_KEYS:
        valor = str(fila.get(key) or "").strip()
        if valor:
            return valor
    return None


# Columnas que describen al documento y no son conceptos ni importes.
_META_DOCUMENTO = META_KEYS | {
    "periodo", "entidad", "moneda", "unidad", "escala", "ejercicio", "fecha", "fecha_cierre", "cuit", "organismo",
}
_NOMBRE_CONCEPTO = re.compile(r"^(?:concepto|cuenta|rubro|descripcion|detalle|partida|item|denominacion|nombre)", re.I)
_ANIO_COLUMNA = re.compile(r"^(?:ejercicio\s*|periodo\s*|ano\s*|anio\s*)?((?:19|20)\d{2})$")
# Contenido típico de cada estado: el tipo se reconoce por lo que dice el documento, no por su nombre.
_FIRMAS_ESTADO = {
    "flujo_caja": (
        r"saldo (?:inicial|final)", r"\bflujo", r"actividades (?:operativas|de inversion|de financiacion)",
        r"variacion neta del efectivo", r"efectivo al (?:inicio|cierre)", r"(?:aumento|disminucion) neta del efectivo",
    ),
    "estado_resultados": (
        r"^ventas", r"ingresos por (?:ventas|servicios)", r"costo de (?:ventas|los servicios)",
        r"gastos de (?:administracion|comercializacion)", r"resultado (?:neto|bruto|operativo)", r"utilidad (?:neta|bruta)",
        r"(?:ganancia|perdida) neta", r"impuesto a las ganancias",
    ),
    "situacion_patrimonial": (
        r"\bactivo", r"\bpasivo", r"patrimonio neto", r"caja y bancos", r"^creditos", r"bienes de uso", r"^deudas",
        r"capital social", r"resultados no asignados", r"disponibilidades", r"^inversiones", r"efectivo y equivalentes",
    ),
}


def _tipo_por_nombre(nombre_archivo: str) -> str | None:
    nombre = perfilado.normalizar_texto(nombre_archivo)
    nombre_sin_ext = re.sub(r"\.[a-z0-9]+$", "", nombre)
    if re.search(r"flujo.*(?:caja|efectivo)|cash.*flow|\befe\b", nombre_sin_ext):
        return "flujo_caja"
    if re.search(r"situacion.*patrimonial|estado.*patrimonial|balance|\besp\b|\bbg\b", nombre_sin_ext):
        return "situacion_patrimonial"
    if re.search(r"estado.*resultad|resultados?|income|\ber\b|\beerr\b", nombre_sin_ext):
        return "estado_resultados"
    return None


def _columna_concepto(filas: list[dict[str, Any]]) -> str | None:
    """La columna que nombra el concepto de cada fila (no la concatenación de todos sus textos)."""
    columnas: list[str] = []
    for fila in filas:
        for key in fila:
            if key not in columnas:
                columnas.append(key)
    candidatas = []
    for col in columnas:
        if perfilado.normalizar_texto(col) in _META_DOCUMENTO or col in _META_DOCUMENTO:
            continue
        valores = [fila.get(col) for fila in filas if fila.get(col) is not None and str(fila.get(col)).strip()]
        textos = [v for v in valores if perfilado.numero(v) is None]
        if not textos or len(textos) < 0.6 * len(filas):
            continue
        if len(filas) > 1 and len({perfilado.normalizar_texto(v) for v in textos}) < 2:
            continue  # un texto constante describe al documento, no a la fila
        candidatas.append(col)
    for col in candidatas:
        if _NOMBRE_CONCEPTO.search(perfilado.normalizar_texto(col)):
            return col
    return candidatas[0] if candidatas else None


def _rotulo_concepto(fila: dict[str, Any], columna: str | None) -> str:
    return perfilado.normalizar_texto(fila.get(columna)) if columna else ""


def _texto_fila(fila: dict[str, Any]) -> str:
    """Compatibilidad: textos de la fila sin metadatos (ya no se usa para reconocer conceptos)."""
    partes = [
        str(valor)
        for key, valor in fila.items()
        if key not in _META_DOCUMENTO and valor is not None and perfilado.numero(valor) is None
    ]
    return perfilado.normalizar_texto(" ".join(partes))


def _periodo_declarado(filas: list[dict[str, Any]]) -> int | None:
    valores = {str(fila.get("periodo") or fila.get("ejercicio") or "").strip() for fila in filas} - {""}
    if len(valores) == 1:
        m = re.search(r"(?:19|20)\d{2}", valores.pop())
        return int(m.group(0)) if m else None
    return None


def _columna_valor(filas: list[dict[str, Any]], concepto: str | None) -> tuple[str | None, str | None]:
    """Columna del importe del período. En estados comparativos, la del período y no la anterior."""
    columnas: list[str] = []
    for fila in filas:
        for key in fila:
            if key not in columnas and key != concepto and key not in _META_DOCUMENTO:
                columnas.append(key)
    numericas = [c for c in columnas if any(perfilado.numero(fila.get(c)) is not None for fila in filas)]
    por_anio = {}
    for c in numericas:
        m = _ANIO_COLUMNA.match(perfilado.normalizar_texto(c).strip())
        if m:
            por_anio[int(m.group(1))] = c
    if por_anio:
        declarado = _periodo_declarado(filas)
        anio = declarado if declarado in por_anio else max(por_anio)
        return por_anio[anio], str(anio)
    numericas = [c for c in numericas if not re.search(r"anio|año|mes|periodo|fecha", perfilado.normalizar_texto(c))]
    for c in numericas:
        if re.search(r"saldo|monto|importe|valor|total|actual|cierre", perfilado.normalizar_texto(c)):
            return c, None
    return (numericas[0], None) if numericas else (None, None)


def _tipo_estado_contable(nombre_archivo: str, filas: list[dict[str, Any]] | None = None) -> str | None:
    """Tipo de estado por su contenido; el nombre del archivo sólo desempata o suple la falta de rótulos."""
    por_nombre = _tipo_por_nombre(nombre_archivo)
    if filas:
        concepto = _columna_concepto(filas)
        rotulos = [_rotulo_concepto(f, concepto) for f in filas]
        puntajes = {
            tipo: sum(any(re.search(p, r) for p in patrones) for r in rotulos if r)
            for tipo, patrones in _FIRMAS_ESTADO.items()
        }
        mejor = max(puntajes.values()) if puntajes else 0
        ganadores = [t for t, v in puntajes.items() if v == mejor and v > 0]
        if len(ganadores) == 1:
            return ganadores[0]
        if por_nombre in ganadores:
            return por_nombre
    return por_nombre


def _buscar_concepto(
    filas: list[dict[str, Any]],
    patrones: tuple[str, ...],
    excluir: tuple[str, ...] = (),
) -> tuple[float, str, str] | None:
    """Primer patrón (en orden de preferencia) que coincide con el rótulo de concepto de una fila."""
    concepto = _columna_concepto(filas)
    columna, _ = _columna_valor(filas, concepto)
    if not concepto or not columna:
        return None
    for patron in patrones:
        for fila in filas:
            texto = _rotulo_concepto(fila, concepto)
            if not texto or any(re.search(x, texto) for x in excluir):
                continue
            if not re.search(patron, texto):
                continue
            numero = perfilado.numero(fila.get(columna))
            if numero is not None:
                return numero, texto, columna
    return None


def _diferencia_material(valor_a: float, valor_b: float) -> bool:
    tolerancia = max(0.01, max(abs(valor_a), abs(valor_b), 1.0) * 0.005)
    return abs(valor_a - valor_b) > tolerancia


def _hallazgo_conciliacion_contable(
    regla: str,
    descripcion: str,
    archivo_a: str,
    dato_a: tuple[float, str, str],
    archivo_b: str,
    dato_b: tuple[float, str, str],
    tipos: dict[str, str] | None = None,
) -> dict | None:
    from services.controles_excel.comun import es_numero

    valor_a, concepto_a, columna_a = dato_a
    valor_b, concepto_b, columna_b = dato_b
    if not _diferencia_material(valor_a, valor_b):
        return None
    return {
        "modo": "coherencia_interdocumental",
        "descripcion": (
            f"La conciliación entre '{archivo_a}' y '{archivo_b}' no cierra: {descripcion}. "
            f"Los valores comparados son {es_numero(valor_a)} («{concepto_a}», columna {columna_a}) y "
            f"{es_numero(valor_b)} («{concepto_b}», columna {columna_b}). Conviene validar período, moneda, escala, "
            "criterio contable y asientos de conciliación antes de continuar."
        ),
        "severidad": "alta",
        "evidencia": {
            "regla": regla,
            "fuente_relacion": "conciliacion_interdocumental_explicita",
            "archivos": [archivo_a, archivo_b],
            "valores": {archivo_a: valor_a, archivo_b: valor_b},
            "conceptos": {archivo_a: concepto_a, archivo_b: concepto_b},
            "columnas": [columna_a, columna_b],
            "tipos_estado": tipos or {},
            "diferencia": round(valor_a - valor_b, 2),
            "diferencia_absoluta": round(abs(valor_a - valor_b), 2),
            "no_es_auditoria_contable": True,
        },
    }


# «Resultado del ejercicio» sin ancla tomaba «Resultado del ejercicio anterior»: el concepto se ancla
# al rótulo completo y se excluyen los resultados de otros ejercicios.
_RESULTADO_EJERCICIO = (
    r"^resultados? (?:neto |final )?del ejercicio(?: \(.*\))?$",
    r"^(?:utilidad|ganancia|perdida) (?:neta )?del ejercicio(?: \(.*\))?$",
    r"^(?:utilidad|ganancia|perdida) neta(?: \(.*\))?$",
)
_OTRO_EJERCICIO = (r"anterior", r"anteriores", r"no asignad", r"acumulad", r"ejercicios? previo")
_EFECTIVO_PATRIMONIAL = (
    r"^efectivo y equivalentes(?: de efectivo)?\b",
    r"^(?:caja y bancos|disponibilidades)\b",
    r"^efectivo\b",
    r"^caja\b",
)
_EFECTIVO_EXCLUIDO = (r"restringid", r"garantia", r"no disponible", r"embargad", r"afectad")
_EFECTIVO_FINAL = (r"saldo final.*(?:efectivo|caja)", r"(?:efectivo|caja).*(?:al cierre|final)", r"^saldo final$")


def _coherencia_interdocumental(datos: list[dict[str, Any]]) -> list[dict]:
    por_archivo: dict[str, list[dict[str, Any]]] = {}
    for fila in datos:
        archivo = _archivo_origen(fila)
        if archivo:
            por_archivo.setdefault(archivo, []).append(fila)
    if len(por_archivo) < 2:
        return []

    por_tipo: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for archivo, filas in por_archivo.items():
        tipo = _tipo_estado_contable(archivo, filas)
        if tipo and tipo not in por_tipo:
            por_tipo[tipo] = (archivo, filas)
    tipos = {archivo: tipo for tipo, (archivo, _) in por_tipo.items()}

    hallazgos: list[dict] = []
    patrimonial = por_tipo.get("situacion_patrimonial")
    flujo = por_tipo.get("flujo_caja")
    resultados = por_tipo.get("estado_resultados")

    if patrimonial and flujo:
        dato_patrimonial = _buscar_concepto(patrimonial[1], _EFECTIVO_PATRIMONIAL, _EFECTIVO_EXCLUIDO)
        dato_flujo = _buscar_concepto(flujo[1], _EFECTIVO_FINAL, (r"inicial",))
        if dato_patrimonial and dato_flujo:
            hallazgo = _hallazgo_conciliacion_contable(
                "efectivo_final_concilia_con_estado_patrimonial",
                "el efectivo final del flujo debe coincidir con disponibilidades del estado patrimonial",
                patrimonial[0], dato_patrimonial, flujo[0], dato_flujo, tipos,
            )
            if hallazgo:
                hallazgos.append(hallazgo)

    if patrimonial and resultados:
        dato_patrimonial = _buscar_concepto(patrimonial[1], _RESULTADO_EJERCICIO, _OTRO_EJERCICIO)
        dato_resultados = _buscar_concepto(resultados[1], _RESULTADO_EJERCICIO, _OTRO_EJERCICIO)
        if dato_patrimonial and dato_resultados:
            hallazgo = _hallazgo_conciliacion_contable(
                "resultado_concilia_con_patrimonio",
                "el resultado del ejercicio debe reflejarse de manera compatible en el patrimonio neto",
                patrimonial[0], dato_patrimonial, resultados[0], dato_resultados, tipos,
            )
            if hallazgo:
                hallazgos.append(hallazgo)
    return hallazgos


def _variacion(prev: float | None, actual: float | None) -> float | None:
    if prev is None or actual is None or abs(prev) < 0.0001:
        return None
    return (actual - prev) / abs(prev)


def _fmt_pct(valor: float | None) -> str:
    return "s/d" if valor is None else f"{valor * 100:+.1f}%"


def _columna_temporal_parseable(datos: list[dict[str, Any]]) -> str | None:
    perfiles = perfilado.perfilar(datos)
    temporales = perfilado.columnas_temporales(perfiles)
    if not temporales:
        return None
    def parseables(col: str) -> int:
        return sum(1 for fila in datos if perfilado.fecha(fila.get(col)) is not None)
    mejor = max(temporales, key=parseables)
    return mejor if parseables(mejor) >= 2 else None


def _filas_ordenadas(datos: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    tcol = _columna_temporal_parseable(datos)
    if not tcol:
        return [(f"fila {i + 1}", fila) for i, fila in enumerate(datos)]
    filas = []
    for i, fila in enumerate(datos):
        fecha = perfilado.fecha(fila.get(tcol))
        if fecha is not None:
            filas.append((fecha, str(fila.get(tcol)), fila))
    filas.sort(key=lambda item: item[0])
    return [(label, fila) for _, label, fila in filas]


def _coherencia_operativa(datos: list[dict[str, Any]]) -> list[dict]:
    if len(datos) < 5:
        return []
    columnas = sorted({c for fila in datos for c in fila.keys()})
    demanda = _col_por_patron(columnas, r"turnos?_otorg|solicitud|demanda|casos?")
    personal = _col_por_patrones(columnas, [
        r"^personal(?:_|$)|^dotacion(?:_|$)|^agentes(?:_|$)|^staff(?:_|$)",
        r"personal_disponible|personal_total|cantidad_personal|plantel",
    ])
    espera = _col_por_patron(columnas, r"espera|demora|tiempo.*promedio")
    reclamos = _col_por_patron(columnas, r"reclamos?|quejas?")
    encuestas = _col_por_patron(columnas, r"encuestas?.*respond|respondidas?|respuestas?")
    satisfaccion = _col_por_patrones(columnas, [
        r"satisfaccion_promedio_simple|promedio_simple.*satisf|satisfaccion_simple",
        r"^satisfaccion$|^satis$|satisfaccion_promedio",
        r"satisfaccion|satis",
    ])

    ordenadas = _filas_ordenadas(datos)
    hallazgos: list[dict] = []
    for i in range(1, len(ordenadas)):
        periodo_previo, prev = ordenadas[i - 1]
        periodo, actual = ordenadas[i]
        demanda_var = _variacion(_valor(prev, demanda), _valor(actual, demanda))
        personal_var = _variacion(_valor(prev, personal), _valor(actual, personal))
        espera_var = _variacion(_valor(prev, espera), _valor(actual, espera))
        reclamos_var = _variacion(_valor(prev, reclamos), _valor(actual, reclamos))
        encuestas_var = _variacion(_valor(prev, encuestas), _valor(actual, encuestas))
        satisfaccion_var = _variacion(_valor(prev, satisfaccion), _valor(actual, satisfaccion))

        if (
            demanda and personal and espera
            and demanda_var is not None and demanda_var > 0.02
            and personal_var is not None and personal_var <= 0.02
            and espera_var is not None and espera_var < -0.20
        ):
            extra = ""
            if reclamos_var is not None and reclamos_var > 0.05:
                extra = f" y los reclamos suben {_fmt_pct(reclamos_var)}"
            hallazgos.append({
                "modo": "coherencia_operativa",
                "descripcion": (
                    f"En {periodo}, la demanda ({demanda}) sube {_fmt_pct(demanda_var)}, "
                    f"el personal ({personal}) cambia {_fmt_pct(personal_var)} y el tiempo de espera ({espera}) baja {_fmt_pct(espera_var)}{extra}. "
                    "La combinación puede ser válida, pero pide explicar si hubo cambio de medición, canal, prioridad de atención, refuerzo no registrado o carga parcial."
                ),
                "severidad": "media",
                "evidencia": {
                    "regla": "coherencia_operativa_espera",
                    "fuente_relacion": "heuristica_operativa_por_encabezados",
                    "no_es_causalidad": True,
                    "periodo_previo": periodo_previo,
                    "periodo": periodo,
                    "columnas": [c for c in [demanda, personal, espera, reclamos] if c],
                    "variaciones_pct": {
                        demanda: round(demanda_var * 100, 2),
                        personal: round(personal_var * 100, 2),
                        espera: round(espera_var * 100, 2),
                        **({reclamos: round(reclamos_var * 100, 2)} if reclamos and reclamos_var is not None else {}),
                    },
                },
            })

        if (
            satisfaccion and reclamos and encuestas
            and satisfaccion_var is not None and satisfaccion_var > 0.15
            and reclamos_var is not None and reclamos_var > 0.10
            and encuestas_var is not None and encuestas_var < -0.25
        ):
            hallazgos.append({
                "modo": "coherencia_operativa",
                "descripcion": (
                    f"En {periodo}, la satisfacción ({satisfaccion}) sube {_fmt_pct(satisfaccion_var)} mientras "
                    f"los reclamos ({reclamos}) suben {_fmt_pct(reclamos_var)} y las encuestas respondidas ({encuestas}) bajan {_fmt_pct(encuestas_var)}. "
                    "Conviene validar composición de la muestra, canal de encuesta o cambio de criterio antes de leer la mejora como desempeño real."
                ),
                "severidad": "media",
                "evidencia": {
                    "regla": "coherencia_operativa_satisfaccion",
                    "fuente_relacion": "heuristica_operativa_por_encabezados",
                    "no_es_causalidad": True,
                    "periodo_previo": periodo_previo,
                    "periodo": periodo,
                    "columnas": [satisfaccion, reclamos, encuestas],
                    "variaciones_pct": {
                        satisfaccion: round(satisfaccion_var * 100, 2),
                        reclamos: round(reclamos_var * 100, 2),
                        encuestas: round(encuestas_var * 100, 2),
                    },
                },
            })
        if len(hallazgos) >= MAX_HALLAZGOS_OPERATIVOS:
            return hallazgos
    return hallazgos


def _es_porcentaje(col: str, valores: list[float]) -> bool:
    """Porcentaje por el nombre, o por valores en [0, 100] con decimales y sin rol de importe.

    Antes bastaba con que todos los valores fueran ≤ 100: un conteo chico de unidades
    («Producción» = 40, 55, 80) se promediaba como si fuera un porcentaje.
    """
    norm = perfilado.normalizar_texto(col)
    if re.search(r"pct|porcentaje|por[_\s]ciento|%|(?<![a-z])tasa(?![a-z])|participacion", norm):
        return True
    no_nulos = [v for v in valores if v is not None]
    if not no_nulos or not all(0 <= v <= 100 for v in no_nulos):
        return False
    if re.search(r"avance|cumplimiento", norm):
        return True
    if perfilado.inferir_rol(col, no_nulos) == "importe":
        return False
    return any(not float(v).is_integer() for v in no_nulos)


def _promedio_o_suma(valores: list[float], como_porcentaje: bool) -> float:
    if como_porcentaje:
        return sum(valores) / len(valores)
    return sum(valores)


def _dimension_principal(datos: list[dict[str, Any]], perfiles: list[dict[str, Any]]) -> str | None:
    candidatas = []
    for perfil in perfiles:
        nombre = perfil.get("name")
        if not nombre or perfil.get("dtype") == "numero" or perfil.get("role") == "identificador":
            continue
        if perfil.get("role") in {"dimension", "texto"}:
            candidatas.append(nombre)
    preferidas = sorted(
        candidatas,
        key=lambda col: (
            0 if re.search(r"region|jurisdiccion|area|programa|rubro|categoria|sector", perfilado.normalizar_texto(col)) else 1,
            col,
        ),
    )
    for col in preferidas:
        valores = {str(fila.get(col)).strip() for fila in datos if str(fila.get(col) or "").strip()}
        if 2 <= len(valores) <= min(30, max(len(datos) // 2, 2)):
            return col
    return None


def _periodo_texto(valor: Any) -> str:
    return str(valor).strip() if valor is not None and str(valor).strip() else "periodo sin etiqueta"


def _coherencia_fisico_financiera(datos: list[dict[str, Any]]) -> list[dict]:
    if len(datos) < 4:
        return []
    perfiles = perfilado.perfilar(datos)
    tcol = _columna_temporal_parseable(datos)
    if not tcol:
        return []

    columnas = sorted({c for fila in datos for c in fila.keys()})
    fisica = _col_por_patrones(columnas, [
        r"avance.*fisic",
        r"meta.*ejecut",
        r"unidad.*ejecut",
        r"produccion",
        r"cantidad.*ejecut",
        r"cumplimiento.*meta",
        r"resultado.*fisic",
    ])
    financiera = _col_por_patrones(columnas, [
        r"avance.*financ",
        r"ejecucion.*financ",
        r"devengado",
        r"pagado",
        r"gasto.*ejecut",
        r"monto.*ejecut",
        r"inversion.*ejecut",
        r"credito.*vigente",
    ])
    if not fisica or not financiera:
        return []

    dimension = _dimension_principal(datos, perfiles)
    valores_fisicos = [perfilado.numero(fila.get(fisica)) for fila in datos]
    valores_financieros = [perfilado.numero(fila.get(financiera)) for fila in datos]
    fisica_pct = _es_porcentaje(fisica, [v for v in valores_fisicos if v is not None])
    financiera_pct = _es_porcentaje(financiera, [v for v in valores_financieros if v is not None])

    buckets: dict[tuple[str, Any], dict[str, Any]] = {}
    for fila in datos:
        fecha = perfilado.fecha(fila.get(tcol))
        vf = perfilado.numero(fila.get(fisica))
        vn = perfilado.numero(fila.get(financiera))
        if fecha is None or vf is None or vn is None:
            continue
        serie = str(fila.get(dimension)).strip() if dimension else "total"
        key = (serie or "sin dimension", fecha)
        bucket = buckets.setdefault(key, {"fisica": [], "financiera": [], "periodo": _periodo_texto(fila.get(tcol))})
        bucket["fisica"].append(vf)
        bucket["financiera"].append(vn)

    series: dict[str, list[tuple[Any, str, float, float]]] = {}
    for (serie, fecha), bucket in buckets.items():
        series.setdefault(serie, []).append((
            fecha,
            bucket["periodo"],
            _promedio_o_suma(bucket["fisica"], fisica_pct),
            _promedio_o_suma(bucket["financiera"], financiera_pct),
        ))

    hallazgos: list[dict] = []
    for serie, puntos in series.items():
        puntos.sort(key=lambda item: item[0])
        if len(puntos) < 3:
            continue
        for i in range(1, len(puntos)):
            _, periodo_previo, fis_prev, fin_prev = puntos[i - 1]
            _, periodo, fis_act, fin_act = puntos[i]
            delta_fis: float | None
            delta_fin: float | None
            if fisica_pct:
                delta_fis = fis_act - fis_prev
            else:
                var_fis = _variacion(fis_prev, fis_act)
                delta_fis = None if var_fis is None else var_fis * 100
            if financiera_pct:
                delta_fin = fin_act - fin_prev
            else:
                var_fin = _variacion(fin_prev, fin_act)
                delta_fin = None if var_fin is None else var_fin * 100
            if delta_fis is None or delta_fin is None:
                continue

            fin_mueve = abs(delta_fin) >= 20 if financiera_pct else abs(delta_fin) >= 35
            fis_estable = abs(delta_fis) <= 5 if fisica_pct else abs(delta_fis) <= 8
            fis_mueve = abs(delta_fis) >= 20 if fisica_pct else abs(delta_fis) >= 35
            fin_estable = abs(delta_fin) <= 5 if financiera_pct else abs(delta_fin) <= 8
            if not ((fin_mueve and fis_estable) or (fis_mueve and fin_estable)):
                continue

            foco = f" para '{serie}'" if dimension and serie != "total" else ""
            hallazgos.append({
                "modo": "coherencia_fisico_financiera",
                "descripcion": (
                    f"En {periodo}{foco}, '{financiera}' cambia {delta_fin:+.1f}"
                    f"{' puntos porcentuales' if financiera_pct else '%'} y '{fisica}' cambia {delta_fis:+.1f}"
                    f"{' puntos porcentuales' if fisica_pct else '%'}. "
                    "La diferencia puede estar justificada, pero conviene pedir contexto sobre criterio de medición, avance físico pendiente de registro, devengamiento o cambio de cobertura."
                ),
                "severidad": "media",
                "evidencia": {
                    "regla": "coherencia_fisico_financiera_agregada",
                    "fuente_relacion": "heuristica_por_encabezados_y_serie_temporal",
                    "no_es_causalidad": True,
                    "dimension": dimension,
                    "serie": serie if dimension else None,
                    "periodo_previo": periodo_previo,
                    "periodo": periodo,
                    "columnas": [financiera, fisica],
                    "variaciones": {
                        financiera: round(delta_fin, 2),
                        fisica: round(delta_fis, 2),
                    },
                    "unidad_variacion": "puntos_porcentuales" if fisica_pct or financiera_pct else "porcentaje",
                    "valores_previos": {financiera: fin_prev, fisica: fis_prev},
                    "valores_actuales": {financiera: fin_act, fisica: fis_act},
                    "criterio_seleccion": (
                        f"Cambio absoluto financiero ≥ {20 if financiera_pct else 35} {'puntos porcentuales' if financiera_pct else '%'} "
                        f"y físico ≤ {5 if fisica_pct else 8} {'puntos porcentuales' if fisica_pct else '%'}; "
                        f"o físico ≥ {20 if fisica_pct else 35} {'puntos porcentuales' if fisica_pct else '%'} "
                        f"y financiero ≤ {5 if financiera_pct else 8} {'puntos porcentuales' if financiera_pct else '%'}"
                    ),
                    "cierre_serie": {"periodo": puntos[-1][1], "financiero": puntos[-1][3],
                                     "fisico": puntos[-1][2],
                                     "brecha_pp": round(puntos[-1][3] - puntos[-1][2], 2) if fisica_pct and financiera_pct else None},
                },
            })
            if len(hallazgos) >= MAX_HALLAZGOS_FISICO_FINANCIEROS:
                return hallazgos
    return hallazgos


def _coherencia_empleo_agregada(datos: list[dict[str, Any]]) -> list[dict]:
    """Calibracion para informes laborales agregados."""
    if len(datos) < 4:
        return []
    perfiles = perfilado.perfilar(datos)
    tcol = _columna_temporal_parseable(datos)
    if not tcol:
        return []

    columnas = sorted({c for fila in datos for c in fila.keys()})
    desempleo_tasa = _col_por_patrones(columnas, [r"tasa.*desempleo", r"desempleo.*pct", r"desocupacion.*pct"])
    desocupados = _col_por_patrones(columnas, [r"desocupad", r"desemplead"])
    demanda = _col_por_patrones(columnas, [r"demanda.*laboral", r"vacantes?", r"puestos?.*ofrec", r"indice.*empleo"])
    programas = _col_por_patrones(columnas, [r"programas?.*empleo", r"politicas?.*empleo", r"presupuesto.*empleo", r"gasto.*empleo"])
    capacitaciones = _col_por_patrones(columnas, [r"capacitacion", r"formacion.*laboral", r"entrenamiento"])
    presion = desempleo_tasa or desocupados
    if not presion or not programas:
        return []

    dimension = _dimension_principal(datos, perfiles)
    buckets: dict[tuple[str, Any], dict[str, Any]] = {}
    for fila in datos:
        fecha = perfilado.fecha(fila.get(tcol))
        if fecha is None:
            continue
        vp = perfilado.numero(fila.get(presion))
        vg = perfilado.numero(fila.get(programas))
        vc = perfilado.numero(fila.get(capacitaciones)) if capacitaciones else None
        vd = perfilado.numero(fila.get(demanda)) if demanda else None
        if vp is None or vg is None:
            continue
        serie = str(fila.get(dimension)).strip() if dimension else "total"
        key = (serie or "sin dimension", fecha)
        bucket = buckets.setdefault(key, {"presion": [], "programas": [], "capacitaciones": [], "demanda": [], "periodo": _periodo_texto(fila.get(tcol))})
        bucket["presion"].append(vp)
        bucket["programas"].append(vg)
        if vc is not None:
            bucket["capacitaciones"].append(vc)
        if vd is not None:
            bucket["demanda"].append(vd)

    presion_pct = bool(desempleo_tasa)
    series: dict[str, list[tuple[Any, str, float, float, float | None, float | None]]] = {}
    for (serie, fecha), bucket in buckets.items():
        cap = sum(bucket["capacitaciones"]) / len(bucket["capacitaciones"]) if bucket["capacitaciones"] else None
        dem = sum(bucket["demanda"]) / len(bucket["demanda"]) if bucket["demanda"] else None
        pres = sum(bucket["presion"]) / len(bucket["presion"]) if presion_pct else sum(bucket["presion"])
        series.setdefault(serie, []).append((fecha, bucket["periodo"], pres, sum(bucket["programas"]), cap, dem))

    hallazgos: list[dict] = []
    for serie, puntos in series.items():
        puntos.sort(key=lambda item: item[0])
        if len(puntos) < 3:
            continue
        for i in range(1, len(puntos)):
            _, periodo_previo, pres_prev, prog_prev, cap_prev, dem_prev = puntos[i - 1]
            _, periodo, pres_act, prog_act, cap_act, dem_act = puntos[i]
            if presion_pct:
                delta_presion = pres_act - pres_prev
                presion_sube = delta_presion >= 0.8
                unidad_presion = "p.p"
            else:
                var_presion = _variacion(pres_prev, pres_act)
                if var_presion is None:
                    continue
                delta_presion = var_presion * 100
                presion_sube = delta_presion >= 15
                unidad_presion = "%"
            var_programas = _variacion(prog_prev, prog_act)
            if var_programas is None:
                continue
            programas_suben = var_programas >= 0.20
            cap_estable = False
            delta_cap = None
            if cap_prev is not None and cap_act is not None:
                var_cap = _variacion(cap_prev, cap_act)
                if var_cap is not None:
                    delta_cap = var_cap * 100
                    cap_estable = abs(delta_cap) <= 8
            demanda_no_acompana = False
            delta_demanda = None
            if dem_prev is not None and dem_act is not None:
                var_dem = _variacion(dem_prev, dem_act)
                if var_dem is not None:
                    delta_demanda = var_dem * 100
                    demanda_no_acompana = delta_demanda <= 5
            if not (presion_sube and programas_suben and (cap_estable or demanda_no_acompana)):
                continue
            foco = f" para '{serie}'" if dimension and serie != "total" else ""
            partes = [
                f"'{presion}' cambia {delta_presion:+.1f} {unidad_presion}",
                f"'{programas}' cambia {var_programas * 100:+.1f}%",
            ]
            if capacitaciones and delta_cap is not None:
                partes.append(f"'{capacitaciones}' cambia {delta_cap:+.1f}%")
            if demanda and delta_demanda is not None:
                partes.append(f"'{demanda}' cambia {delta_demanda:+.1f}%")
            hallazgos.append({
                "modo": "coherencia_empleo_agregada",
                "descripcion": (
                    f"En {periodo}{foco}, " + ", ".join(partes) + ". "
                    "La combinación no permite concluir eficacia ni responsabilidad, pero justifica pedir contexto sobre cobertura, rezago de programas, criterios de medición o composición regional."
                ),
                "severidad": "media",
                "evidencia": {
                    "regla": "coherencia_empleo_agregada",
                    "fuente_relacion": "heuristica_laboral_por_encabezados_y_serie_temporal",
                    "no_es_causalidad": True,
                    "dimension": dimension,
                    "serie": serie if dimension else None,
                    "periodo_previo": periodo_previo,
                    "periodo": periodo,
                    "columnas": [c for c in [presion, programas, capacitaciones, demanda] if c],
                },
            })
            if len(hallazgos) >= MAX_HALLAZGOS_OPERATIVOS:
                return hallazgos
    return hallazgos


def _coherencia_temporal_interna(datos: list[dict[str, Any]]) -> list[dict]:
    perfiles = perfilado.perfilar(datos)
    temporales = perfilado.columnas_temporales(perfiles)
    importes = perfilado.columnas_importe(perfiles)
    if not temporales or len(importes) < 2:
        return []

    tcol = _columna_temporal_parseable(datos) or temporales[0]
    por_periodo: dict[tuple[int, int], dict[str, float]] = {}
    for fila in datos:
        fecha = perfilado.fecha(fila.get(tcol))
        if fecha is None:
            continue
        bucket = por_periodo.setdefault((fecha.year, fecha.month), {c: 0.0 for c in importes})
        for col in importes:
            bucket[col] += perfilado.numero(fila.get(col)) or 0.0

    periodos = sorted(por_periodo)
    if len(periodos) < 5:
        return []

    hallazgos = []
    for i, a in enumerate(importes):
        for b in importes[i + 1:]:
            ratios = []
            valores = []
            periodos_validos = []
            for periodo in periodos:
                va, vb = por_periodo[periodo][a], por_periodo[periodo][b]
                if vb == 0:
                    continue
                ratios.append(va / vb)
                valores.append((va, vb))
                periodos_validos.append(periodo)
            if len(ratios) < 5:
                continue
            historico, actual = ratios[:-1], ratios[-1]
            mediana = sorted(historico)[len(historico) // 2]
            if mediana == 0:
                continue
            dispersion = (max(historico) - min(historico)) / abs(mediana)
            desvio = abs(actual - mediana) / abs(mediana)
            if dispersion <= 0.30 and desvio >= 0.35:
                prev_a, prev_b = valores[-2]
                act_a, act_b = valores[-1]
                var_a = (act_a - prev_a) / abs(prev_a) * 100 if prev_a else None
                var_b = (act_b - prev_b) / abs(prev_b) * 100 if prev_b else None
                hallazgos.append({
                    "modo": "coherencia",
                    "descripcion": (
                        f"La relación entre '{a}' y '{b}' venía siendo estable, pero en el último "
                        f"período se aparta {desvio * 100:.1f}% de su mediana histórica. "
                        "Esto orienta a revisar si hubo cambio de criterio, contexto documentado o inconsistencia entre fuentes."
                    ),
                    "severidad": "alta" if desvio > 0.6 else "media",
                    "evidencia": {
                        "columnas": [a, b],
                        "fuente_relacion": "patron_historico_observado_en_el_archivo",
                        "no_es_causalidad": True,
                        "periodos_observados": len(ratios),
                        "ratio_historico_mediano": round(mediana, 4),
                        "ratio_actual": round(actual, 4),
                        "desvio_relativo_pct": round(desvio * 100, 2),
                        "dispersion_historica": round(dispersion, 4),
                        "variacion_a_pct": round(var_a, 2) if var_a is not None else None,
                        "variacion_b_pct": round(var_b, 2) if var_b is not None else None,
                        "periodo_previo": "%04d-%02d" % periodos_validos[-2],
                        "periodo": "%04d-%02d" % periodos_validos[-1],
                        "formula_ratio": f"{a} / {b}",
                        "valores_previos": {a: prev_a, b: prev_b},
                        "valores_actuales": {a: act_a, b: act_b},
                        "criterio_seleccion": "Dispersión histórica relativa ≤ 30 % y desvío del cociente ≥ 35 %; prioridad alta si supera 60 %. Es un umbral heurístico, no una infracción presupuestaria.",
                    },
                })
    return hallazgos


def _coherencia_con_historial(datos: list[dict[str, Any]], historial: list[list[dict[str, Any]]]) -> list[dict]:
    if not datos or len(historial) < 3:
        return []

    numericas = columnas_numericas(datos)
    series: dict[str, list[float]] = {c: [] for c in numericas}
    for informe_previo in historial:
        cols = [c for c in numericas if c in columnas_numericas(informe_previo)]
        sumas = suma_por_columna(informe_previo, cols)
        for c in numericas:
            series[c].append(sumas.get(c, 0.0))

    actual = suma_por_columna(datos, numericas)
    sumas_anterior = suma_por_columna(historial[-1], [c for c in numericas if c in columnas_numericas(historial[-1])])

    hallazgos = []
    for i, a in enumerate(numericas):
        for b in numericas[i + 1:]:
            corr = correlacion(series[a], series[b])
            if corr is None or abs(corr) < UMBRAL_CORRELACION:
                continue
            delta_a = actual[a] - sumas_anterior.get(a, 0.0)
            delta_b = actual[b] - sumas_anterior.get(b, 0.0)
            if delta_a == 0 or delta_b == 0:
                continue
            mismo_signo = (delta_a > 0) == (delta_b > 0)
            esperado_mismo_signo = corr > 0
            if mismo_signo != esperado_mismo_signo:
                hallazgos.append({
                    "modo": "coherencia",
                    "descripcion": (
                        f"'{a}' y '{b}' venían moviéndose de forma "
                        f"{'conjunta' if corr > 0 else 'inversa'} (correlación histórica {corr:.2f}), "
                        f"pero en este período eso se rompió: {a} varió {delta_a:+.1f} y {b} varió {delta_b:+.1f}. "
                        "Es una ruptura de patrón observado, no una explicación causal."
                    ),
                    "severidad": "alta" if abs(corr) > 0.85 else "media",
                    "evidencia": {
                        "columnas": [a, b],
                        "fuente_relacion": "correlacion_historica_observada",
                        "no_es_causalidad": True,
                        "correlacion_historica": round(corr, 2),
                        "delta_actual": {a: round(delta_a, 2), b: round(delta_b, 2)},
                    },
                })
    return hallazgos


def analizar(datos: list[dict[str, Any]], historial: list[list[dict[str, Any]]], permitir_interdocumental: bool = True) -> list[dict]:
    # La comparación con preinformes pertenece a Radiólogo. Orquesta no debe
    # correlacionar totales de archivos históricos que pueden tener distinta
    # cantidad de filas, cobertura, período o granularidad: eso convierte un
    # cambio de composición en una falsa variación de las magnitudes.
    return (
        (_coherencia_interdocumental(datos) if permitir_interdocumental else [])
        + _coherencia_operativa(datos)
        + _coherencia_fisico_financiera(datos)
        + _coherencia_empleo_agregada(datos)
        + _coherencia_temporal_interna(datos)
    )
