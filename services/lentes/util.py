"""Utilidades compartidas por las lentes."""
from __future__ import annotations

import re
from typing import Any

from services import perfilado

NEGATIVO_SOSPECHOSO = re.compile(
    r"(monto|importe|total|stock|ventas|ingreso|credito|cr[eé]dito|devengado|pagado|avance|presupuestado|ejecutado|gasto)",
    re.I,
)
ID_LIKE = re.compile(r"(^id$|_id$|^codigo$|^cod_)", re.I)
CORRELACION_MIN_N = 5


def columnas_numericas(datos: list[dict[str, Any]]) -> list[str]:
    return perfilado.columnas_numericas(datos)


def valor_numero(valor: Any) -> float | None:
    return perfilado.numero(valor)


def suma_por_columna(datos: list[dict[str, Any]], columnas: list[str]) -> dict[str, float]:
    return {col: sum(float(perfilado.numero(fila.get(col)) or 0) for fila in datos) for col in columnas}


def zscore(valor: float, serie: list[float]) -> float:
    if len(serie) < 2:
        return 0.0
    media = sum(serie) / len(serie)
    var = sum((x - media) ** 2 for x in serie) / len(serie)
    desvio = var ** 0.5
    if desvio == 0:
        return 0.0
    return (valor - media) / desvio


def correlacion(xs: list[float], ys: list[float]) -> float | None:
    """Correlación exploratoria con un piso conservador de observaciones.

    Con menos de cinco pares la estimación es demasiado inestable para abrir
    una señal institucional. Una serie constante tampoco tiene correlación
    definida y debe producir abstención, no 0 ni una alerta.
    """
    if len(xs) != len(ys) or len(xs) < CORRELACION_MIN_N:
        return None
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / ((vx ** 0.5) * (vy ** 0.5))


FILA_LABEL_PREFERIDA = re.compile(
    r"^(concepto|periodo|fecha|mes|rubro|categoria|categoría|cuenta|partida|programa|proyecto|sector|area|área|jurisdiccion|jurisdicción|finalidad|funcion|función)$",
    re.I,
)
FILA_LABEL_EVITAR = re.compile(
    r"cuit|cuil|dni|email|telefono|teléfono|factura|expediente|"
    r"proveedor|contratista|adjudicatari[oa]|cliente|beneficiario|"
    r"nombre|apellido|legajo|domicilio|observaci|comentario|(?<![a-záéíóúñ])personas?(?![a-záéíóúñ])|"
    r"(?<![a-záéíóúñ])(?:agentes?|emplead[oa]s?|titular(?:es)?|pacientes?|docentes?|soci[oa]s?|"
    r"afiliad[oa]s?|alumn[oa]s?|destinatari[oa]s?|contactos?)(?![a-záéíóúñ])",
    re.I,
)


def columna_etiqueta_fila(datos: list[dict[str, Any]]) -> str | None:
    if not datos:
        return None
    columnas = list(datos[0].keys())
    perfiles = perfilado.perfilar(datos)

    def tiene_valores(col: str) -> bool:
        # Una columna con el mismo valor en todas las filas («fecha_actualizacion», la fuente) es un
        # metadato del cuadro: no distingue una fila de otra.
        valores = [str(fila.get(col)).strip() for fila in datos if fila.get(col) is not None and str(fila.get(col)).strip()]
        return bool(valores) and not (len(valores) >= 3 and len(set(valores)) <= 1)

    temporales = [p["name"] for p in perfiles if p.get("role") == "temporal" and tiene_valores(p["name"])]
    for preferida in ("periodo", "fecha", "mes", "anio", "año", "year"):
        for col in columnas:
            if perfilado.normalizar_texto(col) == preferida and tiene_valores(col):
                return col
    if temporales:
        return temporales[0]

    for col in columnas:
        if FILA_LABEL_PREFERIDA.search(str(col).strip()) and tiene_valores(col):
            return col
    candidatas = [
        p["name"] for p in perfiles
        if p.get("dtype") == "texto"
        and p.get("role") in {"dimension", "texto"}
        and tiene_valores(p["name"])
        and not FILA_LABEL_EVITAR.search(str(p.get("name")))
    ]
    return candidatas[0] if candidatas else None


def etiqueta_fila(datos: list[dict[str, Any]], idx: int) -> str:
    etiqueta_base = f"registro {idx + 1} (fila {idx + 2} si la fuente tiene encabezado)"
    if idx < 0 or idx >= len(datos):
        return etiqueta_base
    col = columna_etiqueta_fila(datos)
    if not col:
        return etiqueta_base
    valor = datos[idx].get(col)
    if valor is None or str(valor).strip() == "":
        return etiqueta_base
    texto = str(valor).strip()
    if len(texto) > 90:
        texto = texto[:87].rstrip() + "..."
    return f"{etiqueta_base}; {col}: {texto}"


def etiquetas_filas(datos: list[dict[str, Any]], indices: list[int], max_items: int = 6) -> list[str]:
    return [etiqueta_fila(datos, i) for i in indices[:max_items]]
