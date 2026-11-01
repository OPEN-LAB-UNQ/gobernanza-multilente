"""Controles determinísticos derivados de una pregunta explícita del usuario.

La pregunta nunca modifica reglas existentes ni ejecuta código libre. Solo
activa controles cerrados y auditables. Cada control informa si fue evaluado,
qué resultado produjo o por qué la estructura no permitió responderlo.
"""
from __future__ import annotations

import re
from typing import Any

from services import perfilado, plural
from services.lentes.util import columna_etiqueta_fila, valor_numero

PALABRAS_NUMERO = {
    "una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
STOPWORDS = {
    "a", "al", "de", "del", "el", "en", "es", "la", "las", "los", "que",
    "si", "tres", "fila", "filas", "inferior", "inferiores", "suma", "sumar",
    "verificar", "verifique", "calcular", "identificar", "mayor", "incremento",
    "porcentual", "entre", "mes", "meses", "mensual", "intermensual",
}


def _norm(valor: object) -> str:
    return perfilado.normalizar_texto(valor)


def _pide_suma(texto: str) -> bool:
    return bool(
        re.search(r"\b(suma|sumar|sume|coincid|totaliz|cierra|cierran)\w*\b", texto)
        and re.search(r"\b(total|fila|filas|componente|componentes|inferior|inferiores)\b", texto)
    )


def _pide_variacion(texto: str) -> bool:
    return bool(
        re.search(r"\b(variaci|incremento|aumento|crecimiento)\w*\b", texto)
        and re.search(r"\b(mes|meses|mensual|intermensual|porcentual|porcentaje)\w*\b", texto)
    )


def _cantidad_componentes(texto: str) -> int:
    match = re.search(r"\b(\d{1,2})\s+filas?\b", texto)
    if match:
        return max(1, min(int(match.group(1)), 20))
    for palabra, cantidad in PALABRAS_NUMERO.items():
        if re.search(rf"\b{palabra}\s+filas?\b", texto):
            return cantidad
    return 3 if "inferior" in texto else 0


def _tokens_relevantes(texto: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", _norm(texto))
        if len(token) > 2 and token not in STOPWORDS
    }


def _fila_objetivo(datos: list[dict[str, Any]], orientacion: str) -> tuple[int, str] | None:
    # In wide series, a dated header is a value column, not the row label.
    periodos = {col for fila in datos for col in fila if perfilado.fecha(col) is not None}
    etiquetas = [{col: valor for col, valor in fila.items() if col not in periodos} for fila in datos] if len(periodos) >= 2 else datos
    columna = columna_etiqueta_fila(etiquetas)
    if not columna:
        return None
    tokens = _tokens_relevantes(orientacion)
    candidatas: list[tuple[int, int, str]] = []
    for indice, fila in enumerate(datos):
        etiqueta = str(fila.get(columna) or "").strip()
        normalizada = _norm(etiqueta)
        if not normalizada:
            continue
        puntaje = len(tokens & set(re.findall(r"[a-z0-9]+", normalizada))) * 3
        if "total" in normalizada:
            puntaje += 2
        if "deuda bruta total" in _norm(orientacion) and "deuda bruta total" in normalizada:
            puntaje += 20
        if puntaje:
            candidatas.append((puntaje, -indice, etiqueta))
    if not candidatas:
        return None
    _, negativo_indice, etiqueta = max(candidatas)
    return -negativo_indice, etiqueta


def _columnas_periodo_anchas(datos: list[dict[str, Any]]) -> list[str]:
    if not datos:
        return []
    numericas = set(perfilado.columnas_numericas(datos))
    orden = [col for col in datos[0].keys() if col in numericas]
    temporales = [col for col in orden if perfilado.fecha(col) is not None]
    if len(temporales) >= 2:
        return sorted(temporales, key=lambda col: perfilado.fecha(col))
    return orden


def _control_suma(
    datos: list[dict[str, Any]], orientacion: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cantidad = _cantidad_componentes(_norm(orientacion))
    objetivo = _fila_objetivo(datos, orientacion)
    columnas = _columnas_periodo_anchas(datos)
    base = {"codigo": "suma_total_componentes", "nombre": "Total versus componentes"}
    if not objetivo:
        return ({
            **base,
            "estado": "no_evaluable",
            "resultado": "No se identificó de forma inequívoca la fila total mencionada en la pregunta.",
            "motivo": "falta_fila_total_identificable",
        }, [])
    indice, etiqueta = objetivo
    if cantidad <= 0:
        return ({
            **base,
            "estado": "no_evaluable",
            "resultado": "La pregunta no indica cuántas filas componen el total.",
            "motivo": "cantidad_componentes_no_indicada",
        }, [])
    componentes = datos[indice + 1: indice + 1 + cantidad]
    if len(componentes) != cantidad or not columnas:
        return ({
            **base,
            "estado": "no_evaluable",
            "resultado": f"No hay {cantidad} filas inferiores y columnas numéricas suficientes para comprobar '{etiqueta}'.",
            "motivo": "estructura_insuficiente",
        }, [])

    comparaciones = []
    for columna in columnas:
        total = valor_numero(datos[indice].get(columna))
        valores = [valor_numero(fila.get(columna)) for fila in componentes]
        if total is None or any(valor is None for valor in valores):
            continue
        suma = sum(valor for valor in valores if valor is not None)
        diferencia = total - suma
        tolerancia = max(0.01, abs(total) * 1e-6)
        comparaciones.append({
            "periodo": columna,
            "total": round(total, 6),
            "suma_componentes": round(suma, 6),
            "diferencia": round(diferencia, 6),
            "coincide": abs(diferencia) <= tolerancia,
        })
    if not comparaciones:
        return ({
            **base,
            "estado": "no_evaluable",
            "resultado": "La fila total y sus componentes no comparten valores numéricos comparables.",
            "motivo": "sin_periodos_comparables",
        }, [])

    diferencias = [item for item in comparaciones if not item["coincide"]]
    if not diferencias:
        return ({
            **base,
            "estado": "conforme",
            "resultado": f"'{etiqueta}' coincide con la suma de las {cantidad} filas inferiores en {plural.contar(len(comparaciones), 'período')}.",
            "evidencia": {"fila_total": etiqueta, "cantidad_componentes": cantidad, "comparaciones": comparaciones},
        }, [])

    periodos = ", ".join(str(item["periodo"]) for item in diferencias[:5])
    hallazgo = {
        "lente": "ajedrecista",
        "modo": "total_no_coincide_componentes",
        "descripcion": (
            f"La fila '{etiqueta}' no coincide con la suma de las {cantidad} filas inferiores "
            f"en {plural.contar(len(diferencias), 'período')}: {periodos}."
        ),
        "severidad": "alta",
        "incertidumbre": "baja",
        "tipo_evidencia": "REGLA_FORMAL_O_ARITMETICA",
        "metodo": "comparación determinística entre total declarado y suma de componentes",
        "evidencia": {"fila_total": etiqueta, "cantidad_componentes": cantidad, "comparaciones": diferencias},
        "pregunta_institucional": (
            f"Verificar por qué '{etiqueta}' no coincide con la suma de las {cantidad} filas inferiores "
            f"en {periodos}."
        ),
        "limites": {"fundamento_regla": "consigna explícita de la persona usuaria"},
    }
    return ({
        **base,
        "estado": "observado",
        "resultado": hallazgo["descripcion"],
        "evidencia": hallazgo["evidencia"],
    }, [hallazgo])


def _control_variacion(datos: list[dict[str, Any]], orientacion: str) -> dict[str, Any]:
    base = {"codigo": "mayor_variacion_intermes", "nombre": "Mayor variación intermensual"}
    objetivo = _fila_objetivo(datos, orientacion)
    if not objetivo:
        return {
            **base,
            "estado": "no_evaluable",
            "resultado": "No se identificó la serie mencionada para calcular su variación intermensual.",
            "motivo": "serie_no_identificada",
        }
    indice, etiqueta = objetivo
    # Preserve missing observations and ambiguous aliases; never bridge them.
    fila = datos[indice]
    periodos = [(columna, perfilado.fecha(columna)) for columna in fila]
    periodos = sorted(((columna, fecha) for columna, fecha in periodos if fecha is not None), key=lambda p: p[1])
    puntos = [(columna, fecha.year * 12 + fecha.month, valor_numero(fila.get(columna))) for columna, fecha in periodos]
    meses = [mes for _, mes, _ in puntos]
    duplicados = {mes for mes in meses if meses.count(mes) > 1}
    variaciones = []
    excluidos = []
    for (periodo_anterior, mes_anterior, anterior), (periodo_actual, mes_actual, actual) in zip(puntos, puntos[1:]):
        motivo = None
        if mes_anterior in duplicados or mes_actual in duplicados:
            motivo = "mes_duplicado"
        elif any("trim" in _norm(periodo) for periodo in (periodo_anterior, periodo_actual)):
            motivo = "periodo_trimestral_no_mensual"
        elif mes_actual - mes_anterior != 1:
            motivo = "meses_no_consecutivos"
        elif anterior is None or actual is None:
            motivo = "valor_ausente_o_no_numerico"
        elif anterior == 0:
            motivo = "base_cero"
        if motivo:
            excluidos.append({"desde": periodo_anterior, "hasta": periodo_actual, "motivo": motivo})
            continue
        variacion = ((actual - anterior) / abs(anterior)) * 100
        variaciones.append({
            "desde": periodo_anterior,
            "hasta": periodo_actual,
            "valor_anterior": round(anterior, 6),
            "valor_actual": round(actual, 6),
            "variacion_pct": round(variacion, 4),
        })
    if not variaciones:
        return {
            **base,
            "estado": "no_evaluable",
            "resultado": f"La serie '{etiqueta}' no tiene pares de meses consecutivos, inequívocos y numéricos con base distinta de cero para calcular la variación intermensual.",
            "motivo": "sin_pares_mensuales_evaluables",
            "evidencia": {"serie": etiqueta, "variaciones": [], "pares_excluidos": excluidos},
        }
    mayor = max(variaciones, key=lambda item: item["variacion_pct"])
    resultado = (
        f"El mayor incremento de '{etiqueta}' fue {mayor['variacion_pct']:.2f}% entre "
        f"{mayor['desde']} y {mayor['hasta']} ({mayor['valor_anterior']:g} → {mayor['valor_actual']:g})."
    )
    if mayor['variacion_pct'] <= 0:
        resultado = (
            f"No hubo incrementos en los pares mensuales evaluados de '{etiqueta}'. "
            f"La mayor variación fue {mayor['variacion_pct']:.2f}% entre {mayor['desde']} y {mayor['hasta']}."
        )
    if excluidos:
        resultado += f" Cobertura parcial: {len(variaciones)} pares mensuales evaluados y {len(excluidos)} comparaciones excluidas; el resultado se limita a los pares evaluables."
    return {
        **base,
        "cobertura_parcial": bool(excluidos),
        "estado": "informado",
        "resultado": resultado,
        "evidencia": {"serie": etiqueta, "mayor_incremento": mayor, "variaciones": variaciones, "pares_excluidos": excluidos},
    }


def evaluar(datos: list[dict[str, Any]], orientacion: str | None) -> dict[str, Any]:
    texto = _norm(orientacion)
    controles: list[dict[str, Any]] = []
    hallazgos: list[dict[str, Any]] = []
    if texto and _pide_suma(texto):
        control, nuevos = _control_suma(datos, texto)
        controles.append(control)
        hallazgos.extend(nuevos)
    if texto and _pide_variacion(texto):
        controles.append(_control_variacion(datos, texto))

    estado = estado_controles(controles)
    return {"orientacion": str(orientacion or "").strip(), "estado": estado, "controles": controles, "hallazgos": hallazgos}


def estado_controles(controles):
    if not controles:
        estado = "sin_controles_especificos"
    elif all(control["estado"] == "no_evaluable" for control in controles):
        estado = "no_evaluable"
    elif any(control["estado"] == "no_evaluable" or control.get("cobertura_parcial") for control in controles):
        estado = "parcialmente_evaluado"
    elif any(control["estado"] == "observado" for control in controles):
        estado = "evaluado_con_observaciones"
    else:
        estado = "evaluado"
    return estado
