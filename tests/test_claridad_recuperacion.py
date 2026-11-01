"""Cobertura temporal y recuperación semántica sin inventar revisión completa."""

from services import semantica_plan as plan
from services.controles_excel.lectura import lineas


def corpus_notas():
    elementos = []
    bloques = []
    for b in range(2):
        refs = []
        for i in range(6):
            ref = f"e{b}-{i}"
            refs.append(ref)
            elementos.append(
                {
                    "id": ref,
                    "archivo": "sintetico.xlsx",
                    "hoja": f"Hoja {b}",
                    "celda": f"A{i + 1}",
                    "rol": "nota",
                    "texto": f"Nota {b}-{i} " + ("contenido " * 38),
                }
            )
        bloques.append({"id": f"b{b}", "referencias": refs})
    return {"elementos": elementos, "bloques": bloques, "relaciones": [{"bloques": ["b0", "b1"]}]}


def test_cobertura_sin_series_no_equivale_a_cero_por_ciento_leido():
    salida = " ".join(lineas({"estado": "insuficiente", "series_leidas": 0, "series_aparentes": 0, "archivos": []}))
    assert "no calculable" in salida
    assert "0 %" not in salida and "no significa que el archivo no se haya leído" in salida


def test_series_incompletas_no_excluyen_otros_controles():
    salida = " ".join(lineas({"estado": "insuficiente", "series_leidas": 1, "series_aparentes": 4, "archivos": []}))
    assert "25 %" in salida and "series temporales" in salida
    assert "no mide la lectura total" in salida and "Otros controles" in salida
    completa = " ".join(lineas({"estado": "completa", "series_leidas": 4, "series_aparentes": 4, "archivos": []}))
    assert "100 %" in completa and "no mide la lectura total" in completa


def test_notas_grandes_se_dividen_sin_perder_elementos_ni_pares():
    c = corpus_notas()
    p = plan.planificar(c, 3500)
    assert not p.get("error"), p
    assert p["estrategia"] == "lotes_transversal"
    assert all(plan.tamano(t["contexto"]) <= 3500 for t in p["tareas"])
    for a in c["elementos"]:
        for b in c["elementos"]:
            assert any(
                {a["id"], b["id"]} <= {e["id"] for e in t["contexto"]["elementos"]}
                for t in p["tareas"]
                if t["fase"] == "transversal"
            )


def test_truncamiento_se_recupera_con_lotes_menores_y_cobertura_completa():
    c = corpus_notas()
    calls = []

    def llamar(fn, ctx, hs):
        calls.append(ctx)
        if len(calls) == 1:
            return {
                "contenido": None,
                "error": "Salida truncada",
                "llamadas": [{"status": "failed", "error_type": "token_limit"}],
            }
        return {"contenido": {"hallazgos_exploratorios": []}, "llamadas": [{"status": "completed"}]}

    it = plan.ejecutar(lambda: None, {"_modelo": "gpt", "contexto_semantico": c}, [], llamar)
    st = it["estrategia_semantica"]
    assert st["evaluada"] and st["comparacion_transversal_completada"], st
    assert st["reajustes_por_truncamiento"]
    assert st["elementos_cubiertos"] == len(c["elementos"])
    assert len(calls) <= plan.MAX_LLAMADAS
    assert all(plan.tamano(x["_semantica_enviada"]) < plan.tamano(c) for x in calls[1:])


def test_recuperacion_respeta_limite_y_no_declara_exito(monkeypatch):
    monkeypatch.setattr(plan, "MAX_LLAMADAS", 2)

    def llamar(fn, ctx, hs):
        return {
            "contenido": None,
            "error": "Salida truncada",
            "llamadas": [{"status": "failed", "error_type": "token_limit"}],
        }

    it = plan.ejecutar(lambda: None, {"_modelo": "gpt", "contexto_semantico": corpus_notas()}, [], llamar)
    assert not it["estrategia_semantica"]["evaluada"] and len(it["llamadas"]) <= 2


def test_tutoria_recibe_propuesta_completa_sin_limite_del_mensaje(monkeypatch):
    import sys
    from types import SimpleNamespace

    import models
    from routers import proyectos_ia as router

    capturado = {}

    def crear(**kwargs):
        capturado.update(kwargs)
        # La revisión ahora exige citas estructuradas. Se conserva la regresión
        # original: la propuesta de 29.000 caracteres llega completa al modelo.
        from tests.test_memoria_incubadora_049 import revision
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=revision()))]
        )

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(
            OpenAI=lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)))
        ),
    )
    monkeypatch.setattr(router.settings, "openai_api_key", "test-only")
    monkeypatch.setattr(router, "_contexto_progreso_para_ia", lambda *args: "Progreso de prueba")

    class DB:
        def query(self, *args):
            return self

        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def limit(self, *args):
            return self

        def all(self):
            return []

    texto = "a" * 29000 + " evidencia final"
    proyecto = models.ProyectoIA(id=1, titulo="Prueba", entrega_final=texto)
    result = router._respuesta_ia(DB(), proyecto, "Revisá estos diez criterios")
    assert "Revisión con fuentes del participante" in result and "10. Próximo paso" in result
    assert any(m["content"].endswith(texto) and m["role"] == "user" for m in capturado["messages"])
    assert capturado["max_tokens"] == 3200  # diez criterios, citas y pendientes, sin truncarlos


def test_revision_sin_proveedor_no_devuelve_orientacion_generica_como_revision(monkeypatch):
    import pytest
    from fastapi import HTTPException

    import models
    from routers import proyectos_ia as router

    monkeypatch.setattr(router.settings, "openai_api_key", "")
    with pytest.raises(HTTPException) as error:
        router._respuesta_ia(None, models.ProyectoIA(titulo="Prueba"), "Revisá estos diez criterios")
    assert error.value.status_code == 503
