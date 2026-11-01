"""Matemático: métodos cuantitativos aplicados a los datos del informe.

Complementa los controles de fórmulas de Excel ya extraídos durante la carga.
Benford vive aquí porque evalúa la pertinencia y el comportamiento de una
técnica estadística, no una regla estructural del objeto.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from services import perfilado

from .util import ID_LIKE, columnas_numericas, valor_numero

BENFORD_ESPERADO = [math.log10(1 + 1 / digito) for digito in range(1, 10)]
BENFORD_MIN_N = 50
BENFORD_MAD_NO_CONFORME = 0.015
BENFORD_MIN_ORDENES = 3  # órdenes de magnitud distintos que deben aparecer entre los valores
BENFORD_CONCENTRACION = 0.85  # proporción máxima de valores en un mismo orden de magnitud
NOMBRE_COLUMNA_PERIODO = re.compile(
    r"^(?:19|20)\d{2}(?:\*|e|p)?(?:[_\s-]*(?:total|valor|monto))?(?:_\d+)?$", re.I
)
NO_BENFORD_POR_NOMBRE = re.compile(
    r"(variaci[oó]n|var\.?|porcentaje|%|tasa|ratio|indice|[ií]ndice|pagina|p[aá]gina)", re.I
)


def _columna_benford_apta(columna: str) -> bool:
    nombre = perfilado.normalizar_texto(columna)
    return not (
        re.fullmatch(r"(?:columna|column|unnamed|campo|field)[ _:.]*\d*", nombre)
        or re.search(r"usuario|depositario|legajo|identificador", nombre)
        or ID_LIKE.search(str(columna))
        or NOMBRE_COLUMNA_PERIODO.fullmatch(nombre)
        or NO_BENFORD_POR_NOMBRE.search(nombre)
    )


def _es_nomenclador(positivos: list[float]) -> bool:
    """Valores enteros encerrados en una misma escala: eso es un código, no una cantidad.

    Una posición arancelaria, un país de origen, un año o un mes tienen todos sus valores con la
    misma cantidad de dígitos y sin decimales. Ahí la distribución del primer dígito describe el
    nomenclador y no el registro de una cantidad, así que la prueba de Benford no dice nada.
    Una serie angosta pero con decimales sí puede ser una cantidad y se sigue evaluando.
    """
    if any(valor != int(valor) for valor in positivos):
        return False
    ordenes = Counter(math.floor(math.log10(valor)) for valor in positivos)
    return len(ordenes) < BENFORD_MIN_ORDENES or max(ordenes.values()) / len(positivos) > BENFORD_CONCENTRACION


def _primer_digito(valor: float) -> int | None:
    valor = abs(valor)
    if valor <= 0:
        return None
    while valor < 1:
        valor *= 10
    while valor >= 10:
        valor /= 10
    return int(valor)


def _benford_columna(datos: list[dict[str, Any]], columna: str) -> dict | None:
    if not _columna_benford_apta(columna):
        return None
    positivos = [
        valor
        for valor in (valor_numero(fila.get(columna)) for fila in datos)
        if valor is not None and valor > 0
    ]
    n = len(positivos)
    if n < BENFORD_MIN_N or _es_nomenclador(positivos):
        return None

    conteos = Counter(digito for valor in positivos if (digito := _primer_digito(valor)) is not None)
    observado = [conteos.get(digito, 0) / n for digito in range(1, 10)]
    mad = sum(abs(obs - esperado) for obs, esperado in zip(observado, BENFORD_ESPERADO)) / 9
    if mad < BENFORD_MAD_NO_CONFORME:
        return None

    chi_cuadrado = sum(
        ((conteos.get(digito, 0) - esperado * n) ** 2) / (esperado * n)
        for digito, esperado in zip(range(1, 10), BENFORD_ESPERADO)
    )
    digito_mayor_desvio = max(
        range(1, 10),
        key=lambda digito: abs(observado[digito - 1] - BENFORD_ESPERADO[digito - 1]),
    )
    return {
        "modo": "primer_digito_no_conforme",
        "descripcion": (
            f"La distribución del primer dígito de '{columna}' ({n} valores positivos) se aparta de lo esperado "
            f"por la ley de Benford (desvío medio {mad:.3f}, dígito {digito_mayor_desvio} con mayor desvío). "
            "Es una hipótesis exploratoria, no una conclusión: la forma de agregación puede producir este patrón "
            "sin que exista un problema de carga o registro."
        ),
        "severidad": "baja",
        "incertidumbre": "alta",
        "tipo_evidencia": "PERTINENCIA_METODOLOGICA",
        "evidencia": {
            "regla": "primer_digito_no_conforme_benford",
            "columna": columna,
            "n": n,
            "mad": round(mad, 5),
            "chi_cuadrado": round(chi_cuadrado, 2),
            "digito_mayor_desvio": digito_mayor_desvio,
            "observado_pct": {
                str(digito): round(observado[digito - 1] * 100, 2) for digito in range(1, 10)
            },
            "esperado_pct": {
                str(digito): round(BENFORD_ESPERADO[digito - 1] * 100, 2) for digito in range(1, 10)
            },
            "alcance_metodologico": "exploratorio; requiere validar que los datos sean aptos para Benford",
        },
    }


def motivo_abstencion(datos: list[dict[str, Any]], roles: dict | None = None) -> str | None:
    """Elegibilidad conservadora: no aplicar Benford automáticamente a series temporales."""
    if ("periodo_serie" in roles.values()) if roles is not None else perfilado.columnas_temporales(perfilado.perfilar(datos)):
        return ("Benford no aplicado: el cuadro contiene un eje temporal; la evolución y la agregación "
                "de la serie pueden alterar los primeros dígitos. Requiere justificar su pertinencia por separado.")
    return None


def analizar(datos: list[dict[str, Any]], *, roles: dict | None = None) -> list[dict]:
    if motivo_abstencion(datos, roles):
        return []
    hallazgos = []
    for columna in columnas_numericas(datos):
        if roles is not None and roles.get(columna) != "importe":
            continue
        hallazgo = _benford_columna(datos, columna)
        if hallazgo:
            hallazgos.append(hallazgo)
    return hallazgos
