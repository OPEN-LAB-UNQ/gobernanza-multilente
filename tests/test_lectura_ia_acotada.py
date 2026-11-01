from copy import deepcopy

from services import triangulacion as t
from services.lentes import matematico


def test_genericos_y_usuarios_no_son_magnitudes_benford():
    for c in ["columna_5", "Unnamed: 5", "usuario_depositario", "legajo"]:
        assert matematico._benford_columna([{c: 100000 + i} for i in range(184)], c) is None
    # Los controles estadísticos de magnitudes explícitas permanecen activos.
    assert matematico._benford_columna([{"monto": 480 + i / 10} for i in range(184)], "monto")


def test_presupuesto_preserva_indices_evidencia_original_y_declara_omisiones():
    hs = [
        {
            "lente": "cronista",
            "descripcion": "á" * 1000,
            "severidad": "media",
            "evidencia": {"naturaleza": "contexto" if i < 80 else "control", "datos": list(range(10000))},
        }
        for i in range(100)
    ]
    original = deepcopy(hs)
    ctx = {"_max_prompt_bytes": 12000}
    prompt = t._prompt_usuario(ctx, hs)
    items, alcance = t._preparar_lectura(ctx, hs)
    assert len(prompt.encode()) < 20000 and alcance["hallazgos_omitidos"] > 0
    assert items[0]["idx"] == 80 and all(i["idx"] >= 80 for i in items[: min(20, len(items))])
    assert hs == original and "omitidos" in prompt and "abreviada" in prompt


def test_modelo_no_puede_priorizar_un_indice_omitido():
    hs = [{"lente": "x", "descripcion": "x" * 450, "evidencia": {"dato": "a" * 1000}} for _ in range(200)]
    calls = []

    def fake(ctx, datos):
        calls.append(1)
        return {
            "modelo": "test",
            "contenido": {"prioritarios": [199], "lectura": "x", "explicaciones_alternativas": [], "confianza": "baja"},
            "error": None,
        }

    r = t._interpretar_validado(fake, {}, hs)
    assert len(calls) == 2 and r["contenido"] is None and r["errores_formato"]
