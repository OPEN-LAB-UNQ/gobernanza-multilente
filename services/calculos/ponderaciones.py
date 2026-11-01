"""Deteccion de cambios de criterio en promedios ponderados (lente Matematico)."""
from __future__ import annotations

import re
from typing import Any

from services import plural
from services.calculos.excel_utils import (
    MAX_HALLAZGOS,
    PONDERADOR_RE,
    PROMEDIO_SIMPLE_RE,
    _col_label,
    _is_formula,
    _nombre_columna_raw,
    _norm_label,
    _normalize_formula,
    _numero,
    _row_label,
    _texto_hoja,
)
from services.calculos.formulas import (
    _hallazgo_promedio_simple,
    _hallazgo_promedio_simple_grupo,
)


def _norm_col_calculo(value: Any) -> str:
    text = str(value or "").strip().lower()
    reemplazos = {
        "á": "a", "à": "a", "ä": "a", "â": "a",
        "é": "e", "è": "e", "ë": "e", "ê": "e",
        "í": "i", "ì": "i", "ï": "i", "î": "i",
        "ó": "o", "ò": "o", "ö": "o", "ô": "o",
        "ú": "u", "ù": "u", "ü": "u", "û": "u",
        "ñ": "n",
    }
    for a, b in reemplazos.items():
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _tokens_calculo(nombre: str) -> list[str]:
    return [t for t in _norm_col_calculo(nombre).split("_") if t]


def _sufijo_componente(nombre: str, tipo: str) -> str:
    tokens = _tokens_calculo(nombre)
    if tipo == "valor":
        quitar = {
            "promedio", "media", "nota", "calificacion", "calificaciones", "puntaje", "score",
            "valor", "indice", "indicador", "resultado",
        }
    else:
        quitar = {
            "peso", "pesos", "ponderacion", "ponderador", "ponderadores", "coef", "coeficiente",
            "credito", "creditos", "hora", "horas", "carga", "horaria", "volumen", "cantidad",
            "casos", "respuestas", "respondidas", "encuestas", "n", "num", "numero", "estudiantes",
        }
    restantes = [t for t in tokens if t not in quitar]
    return "_".join(restantes) or _norm_col_calculo(nombre)


def _es_col_valor_promediable(nombre: str) -> bool:
    n = _norm_col_calculo(nombre)
    if re.search(r"informad|reportad|publicad|declarad|esperad|referencia|simple|ponderad|peso|ponderacion|coef|hora|credito", n):
        return False
    return bool(re.search(r"promedio|media|nota|calificacion|puntaje|score", n))


def _es_col_peso(nombre: str) -> bool:
    n = _norm_col_calculo(nombre)
    return bool(re.search(r"peso|ponderacion|ponderador|coef|credito|hora|carga_horaria|volumen|cantidad|n_estudiantes|numero_estudiantes|respuestas|respondidas|casos", n))


def _es_col_promedio_informado(nombre: str) -> bool:
    n = _norm_col_calculo(nombre)
    if re.search(r"peso|ponderacion|coef|hora|credito|esperad|referencia", n):
        return False
    return bool(
        re.search(r"promedio|media|nota|calificacion|puntaje|score|resultado", n)
        and re.search(r"informad|reportad|publicad|declarad|oficial|final", n)
    )


def _mapear_componentes_ponderados(ws) -> list[dict[str, Any]]:
    columnas: list[dict[str, Any]] = []
    for col in range(1, ws.max_column + 1):
        nombre = _nombre_columna_raw(ws, col)
        columnas.append({"col": col, "nombre": nombre, "norm": _norm_col_calculo(nombre)})
    valores = [c for c in columnas if _es_col_valor_promediable(c["nombre"])]
    pesos = [c for c in columnas if _es_col_peso(c["nombre"])]
    componentes = []
    usados_pesos: set[int] = set()
    for valor in valores:
        suf_v = _sufijo_componente(valor["nombre"], "valor")
        candidatos: list[tuple[int, int, dict[str, Any]]] = []
        for peso in pesos:
            if peso["col"] in usados_pesos:
                continue
            suf_p = _sufijo_componente(peso["nombre"], "peso")
            score = 0
            if suf_v and suf_p and suf_v == suf_p:
                score = 3
            elif suf_v and suf_p and (suf_v in suf_p or suf_p in suf_v):
                score = 2
            elif abs(valor["col"] - peso["col"]) <= 2:
                score = 1
            if score:
                candidatos.append((score, -abs(valor["col"] - peso["col"]), peso))
        if not candidatos:
            continue
        candidatos.sort(reverse=True, key=lambda item: (item[0], item[1]))
        peso = candidatos[0][2]
        usados_pesos.add(peso["col"])
        componentes.append({"valor_col": valor["col"], "peso_col": peso["col"], "valor_nombre": valor["nombre"], "peso_nombre": peso["nombre"]})
    return componentes


def _hallazgo_cambio_criterio_ponderado(ws, target_col: int, componentes: list[dict[str, Any]], casos: list[dict[str, Any]]) -> dict:
    primero = casos[0]
    filas = [c["row"] for c in casos]
    filas_detalle = [_row_label(ws, r) for r in filas[:8]]
    componentes_txt = [f"{c['valor_nombre']} x {c['peso_nombre']}" for c in componentes[:6]]
    return {
        "modo": "pertinencia_calculo",
        "descripcion": (
            f"En la hoja '{ws.title}', {_col_label(ws, target_col)} se comporta como promedio simple en {plural.contar(len(casos), 'fila')}, "
            "aunque el archivo contiene ponderadores compatibles con un promedio ponderado. "
            f"Muestra: {primero['fila_detalle']} informa {primero['actual']:.2f}; el ponderado esperado da {primero['ponderado']:.2f} "
            f"y el promedio simple da {primero['simple']:.2f}. Conviene justificar si hubo cambio de criterio de cálculo."
        ),
        "severidad": "media",
        "evidencia": {
            "regla": "promedio_informado_simple_con_ponderadores",
            "plan_calculo": "promedio_ponderado_seguro",
            "hoja": ws.title,
            "columna_resultado": _col_label(ws, target_col),
            "filas": filas[:20],
            "filas_detalle": filas_detalle,
            "componentes": componentes_txt,
            "muestra": primero,
            "criterio": "Se comparó el valor informado contra promedio ponderado por columnas de peso y contra promedio simple de los componentes. No se ejecutó código generado por IA.",
        },
        "incertidumbre": "media",
        "tipo_evidencia": "CALCULO_DETERMINISTICO",
    }


def _analizar_cambio_criterio_ponderado(ws) -> list[dict]:
    contexto = _texto_hoja(ws)
    if not PONDERADOR_RE.search(contexto):
        return []
    # "final"/"oficial" son ambiguos por nombre: "Examen Final" es un componente
    # legitimo, "Promedio Final" es un resultado. La desambiguacion real es
    # estructural, no lexica: si la columna tiene una columna de peso emparejada,
    # esta actuando como componente ponderado (sin importar la palabra), y no
    # puede ser ademas el target a verificar.
    componentes = _mapear_componentes_ponderados(ws)
    cols_usadas_como_componente = {c["valor_col"] for c in componentes}
    target_cols = [
        col for col in range(1, ws.max_column + 1)
        if _es_col_promedio_informado(_nombre_columna_raw(ws, col)) and col not in cols_usadas_como_componente
    ]
    if not target_cols or len(componentes) < 2:
        return []

    hallazgos: list[dict] = []
    for target_col in target_cols:
        casos = []
        for row in range(1, ws.max_row + 1):
            actual = _numero(ws.cell(row=row, column=target_col).value)
            if actual is None:
                continue
            pares = []
            for comp in componentes:
                valor = _numero(ws.cell(row=row, column=comp["valor_col"]).value)
                peso = _numero(ws.cell(row=row, column=comp["peso_col"]).value)
                if valor is None or peso is None or peso <= 0:
                    continue
                pares.append((valor, peso))
            if len(pares) < 2:
                continue
            suma_pesos = sum(p for _, p in pares)
            if suma_pesos <= 0:
                continue
            ponderado = sum(v * p for v, p in pares) / suma_pesos
            simple = sum(v for v, _ in pares) / len(pares)
            tol = max(0.04, abs(ponderado) * 0.003)
            if abs(actual - simple) <= tol and abs(actual - ponderado) > max(0.12, tol * 2):
                casos.append({
                    "row": row,
                    "fila_detalle": _row_label(ws, row),
                    "actual": round(actual, 4),
                    "ponderado": round(ponderado, 4),
                    "simple": round(simple, 4),
                    "diferencia_vs_ponderado": round(actual - ponderado, 4),
                })
        if casos:
            hallazgos.append(_hallazgo_cambio_criterio_ponderado(ws, target_col, componentes, casos))
        if len(hallazgos) >= MAX_HALLAZGOS:
            return hallazgos[:MAX_HALLAZGOS]
    return hallazgos


def _analizar_matematico_hoja(ws) -> list[dict]:
    contexto = _texto_hoja(ws)
    if not PONDERADOR_RE.search(contexto):
        return []

    hallazgos: list[dict] = []
    hallazgos.extend(_analizar_cambio_criterio_ponderado(ws))
    if len(hallazgos) >= MAX_HALLAZGOS:
        return hallazgos[:MAX_HALLAZGOS]

    grupos: dict[tuple[int, str], list[tuple[Any, str]]] = {}
    individuales: list[tuple[Any, str]] = []
    for row in ws.iter_rows():
        for cell in row:
            value = cell.value
            if _is_formula(value) and PROMEDIO_SIMPLE_RE.search(value):
                nombre_col = _norm_col_calculo(_nombre_columna_raw(ws, cell.column))
                etiqueta_fila = _norm_label(ws, cell.row)
                if re.search(r"referencia|auxiliar|control|simple", nombre_col) or re.search(r"^total|resumen|cierre", etiqueta_fila):
                    continue
                patron = _normalize_formula(value, cell.row, cell.column)
                grupos.setdefault((cell.column, patron), []).append((cell, value))
    for cells in grupos.values():
        if len(cells) >= 2:
            hallazgos.append(_hallazgo_promedio_simple_grupo(ws, cells))
        else:
            individuales.extend(cells)
        if len(hallazgos) >= MAX_HALLAZGOS:
            return hallazgos[:MAX_HALLAZGOS]
    for cell, value in individuales:
        hallazgos.append(_hallazgo_promedio_simple(ws, cell, value))
        if len(hallazgos) >= MAX_HALLAZGOS:
            return hallazgos[:MAX_HALLAZGOS]
    return hallazgos
