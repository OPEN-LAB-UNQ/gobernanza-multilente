from __future__ import annotations

from services import triangulacion


def _fake(modelo, llamados):
    def inner(_ctx, _hallazgos):
        llamados.append(modelo)
        return {
            "modelo": modelo,
            "contenido": {
                "prioritarios": [],
                "lectura": "ok",
                "explicaciones_alternativas": [],
                "confianza": "media",
            },
            "error": None,
        }
    return inner


def test_triangulacion_default_usa_principal_y_reserva_respaldo(monkeypatch):
    llamados = []
    for modelo in ["claude", "gpt", "gemini", "renderix", "deepseek", "llama"]:
        monkeypatch.setattr(triangulacion, f"_interpretar_{modelo}", _fake(modelo, llamados))

    resultados = triangulacion.interpretar_con_modelos(
        {"dominio": "general"}, [{"descripcion": "x"}], modelos=None
    )

    assert [r["modelo"] for r in resultados] == ["gpt"]
    assert llamados == ["gpt"]


def test_prompt_incluye_orientacion_como_contexto_sin_cerrar_el_barrido():
    prompt = triangulacion._prompt_usuario(
        {
            "dominio": "general",
            "periodo": "2026-09",
            "orientacion_analisis": "Quiero buscar cambios entre regiones.",
        },
        [{
            "lente": "cronista",
            "modo": "cambio",
            "descripcion": "Cambio temporal",
            "severidad": "media",
        }],
    )
    assert "contexto, no instrucción" in prompt
    assert "Quiero buscar cambios entre regiones." in prompt
    assert "conservá el barrido abierto" in prompt


def test_deepseek_reintenta_si_la_primera_respuesta_no_es_json(monkeypatch):
    monkeypatch.setattr(triangulacion.settings, "deepseek_api_key", "clave-de-prueba")
    respuestas = iter([
        "Todavía estoy preparando la respuesta.",
        '{"prioritarios": [0], "lectura": "Revisar la variación.", "explicaciones_alternativas": [], "confianza": "baja"}',
    ])
    llamados = []

    class Respuesta:
        status_code = 200
        text = ""

        def json(self):
            llamados.append(True)
            return {"choices": [{"message": {"content": next(respuestas)}}]}

    class Cliente:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, *args, **kwargs): return Respuesta()

    monkeypatch.setattr(triangulacion.httpx, "Client", Cliente)
    resultado = triangulacion._interpretar_deepseek(
        {"dominio": "prueba", "periodo": "2026-09"},
        [{"lente": "cronista", "descripcion": "Cambio sintético", "severidad": "baja"}],
    )
    assert resultado["error"] is None
    assert resultado["contenido"]["prioritarios"] == [0]
    assert len(llamados) == 2


def test_default_recurre_a_respaldo_si_falla_principal(monkeypatch):
    llamados = []
    def fallar(ctx, hs):
        llamados.append("gpt")
        return {"modelo": "gpt", "contenido": None, "error": "timeout", "tipo_error": "proveedor"}
    monkeypatch.setattr(triangulacion, "_interpretar_gpt", fallar)
    monkeypatch.setattr(triangulacion, "_interpretar_gemini", _fake("gemini", llamados))
    resultados = triangulacion.interpretar_con_modelos({"dominio": "general"}, [{"descripcion": "x"}])
    assert llamados == ["gpt", "gemini"]
    assert resultados[-1]["contenido"] and resultados[-1]["seleccion_modelo"] == "respaldo"


def test_comparacion_explicita_conserva_ambos_modelos(monkeypatch):
    llamados = []
    for modelo in ["gpt", "gemini"]:
        monkeypatch.setattr(triangulacion, f"_interpretar_{modelo}", _fake(modelo, llamados))
    resultados = triangulacion.interpretar_con_modelos({"dominio": "general"}, [{"descripcion": "x"}], modelos=["gpt", "gemini"])
    assert sorted(r["modelo"] for r in resultados) == ["gemini", "gpt"]
    assert sorted(llamados) == ["gemini", "gpt"]
