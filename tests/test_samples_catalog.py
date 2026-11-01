import json
from pathlib import Path

import pytest

from services import carga_archivos, formula_integridad
from services.lentes import ajedrecista, cronista, orquesta, rizoma

SAMPLES = Path(__file__).parents[1] / "static" / "samples"


def _hallazgos(item):
    path = SAMPLES / Path(item["archivo"]).name
    contenido = path.read_bytes()
    datos = carga_archivos.parse_archivo(path.name, contenido)
    resultado = []
    resultado.extend(ajedrecista.analizar(datos))
    resultado.extend(cronista.analizar(datos))
    resultado.extend(orquesta.analizar(datos, []))
    resultado.extend(rizoma.analizar(datos))
    opciones = item["opciones"]
    if opciones.get("revisar_formulas_excel"):
        resultado.extend(formula_integridad.analizar_archivo(path.name, contenido))
    if opciones.get("revisar_metodo_calculo"):
        resultado.extend(formula_integridad.analizar_matematico_archivo(path.name, contenido))
    return resultado


def _catalogo():
    return json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))


def test_catalogo_tiene_ocho_pares_completos():
    grupos = {}
    for item in _catalogo():
        grupos.setdefault(item["caso"], []).append(item)

    assert len(grupos) == 8
    assert all(len(items) == 2 for items in grupos.values())
    assert all({item["columna"] for item in items} == {"bueno", "malo"} for items in grupos.values())


@pytest.mark.parametrize("item", _catalogo(), ids=lambda item: Path(item["archivo"]).stem)
def test_muestras_coinciden_con_la_senal_esperada(item):
    hallazgos = _hallazgos(item)
    espera_senal = item["columna"] == "malo"

    assert bool(hallazgos) == espera_senal, (
        f'{item["archivo"]}: se esperaban hallazgos={espera_senal}, '
        f'pero se obtuvieron {len(hallazgos)}'
    )
