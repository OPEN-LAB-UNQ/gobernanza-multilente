"""Rizoma: análisis relacional exploratorio.

Busca conexiones inesperadas entre columnas numéricas. A diferencia de una
correlación general, esta lente intenta no comunicar relaciones obvias del
ciclo presupuestario (crédito, devengado, pagado, compromiso) porque esas
pertenecen mejor a Orquesta o Ajedrecista.
"""
from __future__ import annotations

import re
from typing import Any

from services import perfilado

from .util import CORRELACION_MIN_N, columnas_numericas, correlacion, valor_numero

UMBRAL_NOTABLE = 0.9
MAX_HALLAZGOS = 3

PRESUPUESTARIAS_ESPERABLES = re.compile(
    r"credito|cr[eé]dito|vigente|devengado|pagado|pago|compromiso|comprometido|presupuesto|ejecutado",
    re.I,
)
FISICAS_ESPERABLES = re.compile(r"avance|meta|fisic|f[ií]sic|obra|ejecucion|ejecuci[oó]n", re.I)
PERIODO_ESPERABLE = re.compile(
    r"^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+\d{4}$|^\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?(?:\s+00:00:00)?$|^\d+[°º]?\s*trim\.?\s*\d{4}$|^periodo$|^mes$",
    re.I,
)
CALCULO_DERIVADO_RE = re.compile(
    r"promedio|media|ponderado|total|subtotal|saldo|resultado|diferencia|brecha|ratio|"
    r"porcentaje|pct|tasa|indice|índice|score|puntaje|calculado|desv[ií]o|margen|variaci[oó]n|excedente",
    re.I,
)
DERIVADO_POR_UNIDAD_RE = re.compile(
 r"por\s+(?:dia|día|tambo|productor|hectarea|ha|jornada|persona|unidad)|"
 r"(?:litros?|kg|tn|toneladas?|pesos?|casos?|tramites?|trámites?)\s+por|/",
 re.I,
)
ID_TEMPORAL_RE = re.compile(r"(^|[_\s])(id|codigo|c[oó]digo|cohorte|año|anio|year|periodo|mes|fecha)([_\s]|$)", re.I)
DEMANDA_BASE_RE = re.compile(r"turnos?|atendid|atencion|atención|ausente|ausentismo", re.I)
VOLUMEN_OPERATIVO_RE = re.compile(r"turnos?|atendid|atencion|atención|ausente|ausentismo|derivac|reclamo|encuesta", re.I)
FLUJO_TRAMITE_RE = re.compile(
    r"consulta|consultas|recibid|ingresad|entrad|resuelt|cerrad|pendient|stock|backlog|tramite|trámite|expediente|derivac|atendid|demora|plazo|tiempo|dias|días",
    re.I,
)
FAMILIAS_RELACIONALES = {
    "demanda": re.compile(r"consulta|reclamo|solicitud|pedido|turno|demanda|ingresad|recibid", re.I),
    "capacidad": re.compile(r"dotacion|dotación|personal|equipo|capacidad|horas|recursos", re.I),
    "calidad": re.compile(r"error|rechazo|devolucion|devolución|retrabajo|observacion|observación|calidad", re.I),
    "tiempo": re.compile(r"demora|plazo|tiempo|dias|días|vencim|antiguedad|antigüedad", re.I),
    "resultado": re.compile(r"resuelt|finaliz|cerrad|atendid|cumplid|aprob|pendient|stock|backlog", re.I),
}
COMPARATIVO_ACTUAL_RE = re.compile(r"\b(current|actual|corriente|vigente|mar\s*31\s*2026|2026)\b", re.I)
COMPARATIVO_PREVIO_RE = re.compile(r"\b(prior|previous|previo|anterior|comparativo|dec\s*31\s*2025|mar\s*31\s*2025|2025)\b", re.I)
VALOR_COMPARATIVO_RE = re.compile(r"valor|value|monto|importe|usd|actual|current|prior|previo|previous|anterior", re.I)
ANIO_COMPARATIVO_RE = re.compile(r"\b(?:19|20)\d{2}\b")
PRECIO_MERCADO_RE = re.compile(r"^(?:apertura|open|maximo|máximo|high|minimo|mínimo|low|cierre|close|ultimo|último|last|cierre previo|previous close|prev close|cierre ajustado|adjusted close|adj close)$", re.I)
VOLUMEN_MERCADO_RE = re.compile(r"volumen", re.I)
GENERICA_EXTRACCION_RE = re.compile(r"^columna_\d+$", re.I)
COLUMNA_FRAGMENTARIA_RE = re.compile(r"^(?:\d[\d\s,%.()/-]*|[a-z]\s*\d{4}(?:_\d+)?|[a-z]{1,2}(?:_\d+)?)$", re.I)
PRECIOS_BASE_RE = re.compile(r"a precios|precios corrientes|precios constantes|precios acumulados", re.I)
VALOR_BASE_ALTERADO_RE = re.compile(r"valor.*(base|alterad[oa])|(base|alterad[oa]).*valor", re.I)
REGION_IPC_RE = re.compile(
    r"regi[oó]n|regiones|nacional|gba|pampeana|noreste|noroeste|cuyo|patagonia",
    re.I,
)
UNIDAD_MEDIDA_MEZCLADA_RE = re.compile(r"unidad|medida|millones|miles|% del pib|porcentaje|puntos?", re.I)


def _es_periodo(col: str) -> bool:
    return bool(PERIODO_ESPERABLE.search(str(col).strip()))


def _columna_fragmentaria(col: str) -> bool:
    texto = str(col).strip()
    letras = re.findall(r"[A-Za-zÀ-ÿ]", texto)
    return bool(GENERICA_EXTRACCION_RE.search(texto) or COLUMNA_FRAGMENTARIA_RE.search(texto) or len(letras) < 3)


def _par_comparativo_esperable(a: str, b: str) -> bool:
    a_txt = str(a).replace("_", " ")
    b_txt = str(b).replace("_", " ")
    if not (VALOR_COMPARATIVO_RE.search(a_txt) and VALOR_COMPARATIVO_RE.search(b_txt)):
        return False
    if (
        (COMPARATIVO_ACTUAL_RE.search(a_txt) and COMPARATIVO_PREVIO_RE.search(b_txt))
        or (COMPARATIVO_ACTUAL_RE.search(b_txt) and COMPARATIVO_PREVIO_RE.search(a_txt))
    ):
        return True
    anios_a = {int(x) for x in ANIO_COMPARATIVO_RE.findall(a_txt)}
    anios_b = {int(x) for x in ANIO_COMPARATIVO_RE.findall(b_txt)}
    return bool(anios_a and anios_b and anios_a != anios_b)

def _par_mercado_esperable(a: str, b: str) -> bool:
    a_txt = str(a).strip().replace("_", " ")
    b_txt = str(b).strip().replace("_", " ")
    precios = PRECIO_MERCADO_RE.search(a_txt) and PRECIO_MERCADO_RE.search(b_txt)
    volumenes = VOLUMEN_MERCADO_RE.search(a_txt) and VOLUMEN_MERCADO_RE.search(b_txt)
    return bool(precios or volumenes)


def _familia_relacional(col: str) -> str | None:
    texto = perfilado.normalizar_texto(col)
    for familia, patron in FAMILIAS_RELACIONALES.items():
        if patron.search(texto):
            return familia
    return None


def _tokens_significativos(col: str) -> set[str]:
    tokens = set(re.findall(r"[a-záéíóúñü]{4,}", perfilado.normalizar_texto(col)))
    ruido = {"total", "cantidad", "numero", "valor", "monto", "mensual", "acumulado", "actual", "previo"}
    return tokens - ruido


def _par_flujo_tramite_obvio(a: str, b: str) -> bool:
    a_txt = perfilado.normalizar_texto(a)
    b_txt = perfilado.normalizar_texto(b)
    if not (FLUJO_TRAMITE_RE.search(a_txt) and FLUJO_TRAMITE_RE.search(b_txt)):
        return False
    familia_a = _familia_relacional(a)
    familia_b = _familia_relacional(b)
    familias = {f for f in (familia_a, familia_b) if f}
    if familias & {"tiempo", "calidad", "capacidad"}:
        # Demanda contra demora/calidad/capacidad puede abrir una pregunta útil.
        return False
    return True


def _par_redundante_por_nombre(a: str, b: str) -> bool:
    tokens_a = _tokens_significativos(a)
    tokens_b = _tokens_significativos(b)
    return bool(tokens_a and tokens_b and tokens_a & tokens_b)

def _es_pdf_tabular(datos: list[dict[str, Any]]) -> bool:
    return any(str(fila.get("extraccion_pdf") or "").lower() == "tabla" for fila in datos)


def _par_regional_pdf_obvio(a: str, b: str, datos: list[dict[str, Any]]) -> bool:
    if not _es_pdf_tabular(datos):
        return False
    return bool(REGION_IPC_RE.search(str(a)) and REGION_IPC_RE.search(str(b)))


def _relacion_obvia(a: str, b: str, datos: list[dict[str, Any]] | None = None) -> bool:
    """Evita vender como hallazgo exploratorio lo que ya se espera o se deriva mecánicamente."""
    datos = datos or []
    if _par_regional_pdf_obvio(a, b, datos):
        return True
    if _es_periodo(a) or _es_periodo(b):
        return True
    if _columna_fragmentaria(a) or _columna_fragmentaria(b):
        return True
    if UNIDAD_MEDIDA_MEZCLADA_RE.search(str(a)) or UNIDAD_MEDIDA_MEZCLADA_RE.search(str(b)):
        return True
    if PRECIOS_BASE_RE.search(str(a)) or PRECIOS_BASE_RE.search(str(b)):
        return True
    if _par_comparativo_esperable(a, b):
        return True
    if _par_mercado_esperable(a, b):
        return True
    if _par_flujo_tramite_obvio(a, b):
        return True
    if _par_redundante_por_nombre(a, b):
        return True
    if VALOR_BASE_ALTERADO_RE.search(a) and VALOR_BASE_ALTERADO_RE.search(b):
        return True
    if ID_TEMPORAL_RE.search(a) or ID_TEMPORAL_RE.search(b):
        return True
    if CALCULO_DERIVADO_RE.search(a) or CALCULO_DERIVADO_RE.search(b):
        return True
    if (DEMANDA_BASE_RE.search(a) and VOLUMEN_OPERATIVO_RE.search(b)) or (DEMANDA_BASE_RE.search(b) and VOLUMEN_OPERATIVO_RE.search(a)):
        return True
    a_core = bool(PRESUPUESTARIAS_ESPERABLES.search(a) or FISICAS_ESPERABLES.search(a))
    b_core = bool(PRESUPUESTARIAS_ESPERABLES.search(b) or FISICAS_ESPERABLES.search(b))
    return a_core or b_core


def _estadistica_par(datos: list[dict[str, Any]], a: str, b: str, interpretacion=None) -> dict[str, Any] | None:
    from services.observaciones import eje_temporal
    eje = eje_temporal(datos, interpretacion)
    if eje:
        datos = [datos[i] for i in eje[1]]
    pares: list[tuple[float, float, str | None]] = []
    posiciones = []
    for posicion, fila in enumerate(datos):
        va, vb = valor_numero(fila.get(a)), valor_numero(fila.get(b))
        if va is None or vb is None:
            continue
        periodo = str(fila[eje[0]]) if eje else None
        pares.append((float(va), float(vb), periodo))
        posiciones.append(posicion)
    corr = correlacion([p[0] for p in pares], [p[1] for p in pares])
    if corr is None:
        return None
    # Un dato ausente no convierte dos períodos separados en períodos vecinos.
    consecutivos = [i for i in range(1, len(pares)) if posiciones[i] == posiciones[i - 1] + 1] if eje else []
    dx = [pares[i][0] - pares[i - 1][0] for i in consecutivos]
    dy = [pares[i][1] - pares[i - 1][1] for i in consecutivos]
    corr_diferencias = correlacion(dx, dy)
    periodos = [p[2] for p in pares if p[2]]
    return {
        "columnas": [a, b],
        "metodo": "correlación de Pearson",
        "coeficiente_pearson": round(corr, 4),
        "correlacion": round(corr, 4),
        "n_observaciones": len(pares),
        "eje_temporal_verificado": bool(eje),
        "periodo_desde": periodos[0] if periodos else None,
        "periodo_hasta": periodos[-1] if periodos else None,
        "datos_faltantes": len(datos) - len(pares),
        "umbral_seleccion_abs": UMBRAL_NOTABLE,
        "correlacion_primeras_diferencias": round(corr_diferencias, 4) if corr_diferencias is not None else None,
        "n_primeras_diferencias": len(dx),
        "limitacion_muestra": (
            f"La asociación se observa en solo {len(pares)} registros; su estabilidad fuera de esta muestra no está demostrada."
            if len(pares) < 12 else None
        ),
    }


def evaluar_relaciones(datos: list[dict[str, Any]], *, interpretacion=None) -> list[dict[str, Any]]:
    """Devuelve las relaciones no obvias evaluables, incluso si no alcanzan
    el umbral. Permite documentar controles negativos sin convertirlos en
    hallazgos."""
    from services.resultado_revision import separar_datos
    datos, _ = separar_datos(datos)
    from services.observaciones import sin_agregados
    datos, agregados = sin_agregados(datos)
    if len(datos) < CORRELACION_MIN_N:
        return []
    numericas = columnas_numericas(datos)
    partes = [c for c in numericas if not ID_TEMPORAL_RE.search(c) and not CALCULO_DERIVADO_RE.search(c)]
    composicion = False
    if len(partes) >= 3:
        filas = [[valor_numero(f.get(c)) for c in partes] for f in datos]
        completas = [vs for vs in filas if all(v is not None and v >= 0 for v in vs)]
        composicion = len(completas) == len(datos) and any(
            all(abs(sum(vs)-base) <= .005*base for vs in completas) for base in (1,100)
        )
    relaciones = []
    for i, a in enumerate(numericas):
        for b in numericas[i + 1:]:
            if composicion and a in partes and b in partes:
                continue
            if _relacion_obvia(a, b, datos):
                continue
            estadistica = _estadistica_par(datos, a, b, interpretacion)
            if estadistica is not None:
                estadistica["filas_agregadas_excluidas"] = agregados
                relaciones.append(estadistica)
    return sorted(relaciones, key=lambda item: abs(item["coeficiente_pearson"]), reverse=True)


def evidencia_control_negativo(datos: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (item for item in evaluar_relaciones(datos) if abs(item["coeficiente_pearson"]) < UMBRAL_NOTABLE),
        None,
    )


def analizar(datos: list[dict[str, Any]], *, interpretacion=None) -> list[dict]:
    from services.resultado_revision import separar_datos
    datos, _ = separar_datos(datos)
    if len(datos) < CORRELACION_MIN_N:
        return []

    hallazgos = []
    relaciones = evaluar_relaciones(datos, interpretacion=interpretacion) if interpretacion is not None else evaluar_relaciones(datos)
    candidatos = [item for item in relaciones if abs(item["coeficiente_pearson"]) >= UMBRAL_NOTABLE]
    for estadistica in candidatos[:MAX_HALLAZGOS]:
        a, b = estadistica["columnas"]
        corr = estadistica["coeficiente_pearson"]
        sentido = "presentan una asociación positiva" if corr > 0 else "presentan una asociación inversa"
        hallazgos.append({
            "modo": "exploratorio",
            "descripcion": (
                f"'{a}' y '{b}' {sentido} de forma muy marcada dentro de este informe "
                f"(correlación {corr:.4f}). No se comunica como causa ni conclusión: "
                "queda como pregunta abierta para revisar mecanismos plausibles y posibles variables de confusión."
            ),
            "severidad": "media",
            "pregunta_institucional": (
                f"¿Existe un mecanismo plausible que vincule '{a}' y '{b}', o ambas variables responden a un tercer factor "
                "como la composición de la muestra, la cobertura o la metodología de la fuente?"
            ),
            "evidencia": {
                **estadistica,
                "umbral": UMBRAL_NOTABLE,
                "criterio_pertinencia": "Se comunica solo si la asociación no parece derivada, temporal, operativa obvia ni redundante por nombre.",
                "comprobaciones_sugeridas": ([
                    "Ampliar el número de períodos.",
                    "Comparar los mismos meses de distintos años.",
                    "Controlar estacionalidad y tendencia temporal.",
                    "Consultar al área responsable si cambió la cobertura, la definición de las variables o la metodología de la fuente.",
                    "Analizar primeras diferencias además de los niveles.",
                ] if estadistica.get("eje_temporal_verificado") else [
                    "Ampliar la muestra con observaciones comparables e independientes.",
                    "Revisar diferencias de tamaño y composición entre categorías.",
                    "Consultar si cambió la cobertura, la definición de las variables o la metodología de la fuente.",
                ]),
                "nota": "Se omitieron pares presupuestarios, físicos, temporales, identificatorios, comparativos esperables, pares regionales de PDF tabular, pares de mercado esperables, flujos de trámite obvios, operativos esperables y columnas derivadas, ratios por unidad y métricas de productividad derivada para reducir ruido.",
            },
        })
    return hallazgos



