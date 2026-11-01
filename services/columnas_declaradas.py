"""Columnas que la consulta declara como códigos, para que esa declaración tenga efecto.

Cuando alguien escribe «los códigos NCM y de país son identificadores, no cantidades», eso es una
restricción sobre el análisis y no un comentario: si el sistema la lee y corre igual sus pruebas
numéricas, devuelve señales que la persona ya había descartado.

El reconocimiento es deterministico y conservador: sólo se toman nombres de columna que existen en
los datos, y sólo cuando el texto los declara explícitamente. Se guarda el fragmento que lo
justifica, porque una restricción que no se puede auditar no sirve.
"""

from __future__ import annotations

import re

from services.perfilado import normalizar_texto

# «son códigos», «no son cantidades», «no los sumes»: la consulta pide dejarlos afuera.
SENAL_EXCLUSION = re.compile(
    r"(son|es)\s+(un\s+)?(c[oó]digos?|identificadores?)"
    r"|no\s+(son|es)\s+(cantidades?|importes?|valores?|magnitudes?)"
    r"|no\s+(los\s+|las\s+|lo\s+)?(sumes|sumar|promedies|promediar|analices|analizar|apliques|aplicar)"
    r"|identificadores?\s*,?\s*no\s+cantidades?"
    r"|no\s+(tomar|tomes)\s+como\s+(cantidad|importe|valor)",
    re.I,
)
# «(Porg, código numérico de instituto de estadística)»: el paréntesis declara la columna y dice que es un código.
PARENTESIS = re.compile(r"\(([^)]{0,200})\)")
CODIGO = re.compile(r"c[oó]digo|identificador|nomenclador", re.I)
MINIMO_NOMBRE = 2


def _nombrada(texto_norm: str, columna: str) -> bool:
    norm = normalizar_texto(columna)
    if len(norm) < MINIMO_NOMBRE:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(norm)}(?![a-z0-9])", texto_norm) is not None


def _fragmentos(texto: str) -> list[str]:
    partes = [p.strip() for p in re.split(r"(?<=[.;:\n])\s+", texto) if p.strip()]
    return [p for p in partes if SENAL_EXCLUSION.search(p)] + [p for p in PARENTESIS.findall(texto) if CODIGO.search(p)]


def detectar(orientacion: object, datos: list[dict]) -> dict:
    """Columnas declaradas como códigos, con el fragmento que lo dice."""
    texto = str(orientacion or "").strip()
    columnas = sorted({c for fila in datos[:200] for c in fila}) if datos else []
    if not texto or not columnas:
        return {"columnas": [], "motivos": {}}
    motivos: dict[str, str] = {}
    for fragmento in _fragmentos(texto):
        norm = normalizar_texto(fragmento)
        for columna in columnas:
            if columna not in motivos and _nombrada(norm, columna):
                motivos[columna] = " ".join(fragmento.split())[:220]
    return {"columnas": sorted(motivos), "motivos": motivos}


def linea_declarada(restriccion: object) -> str:
    """Cómo se cuenta la restricción en el reporte; sin esto sería un filtro invisible."""
    columnas = list((restriccion or {}).get("columnas") or [])
    if not columnas:
        return ""
    nombres = ", ".join(f"«{c}»" for c in columnas)
    return (
        f"Por indicación de la consulta, {nombres} se trataron como identificadores y quedaron fuera "
        "de los controles numéricos. El resto del análisis no cambia."
    )
