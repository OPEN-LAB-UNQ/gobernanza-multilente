"""3. Fallos enmascarados: lectura de señales y exploración del libro con estado propio.
8. Roles: el respaldo no cuenta como coincidencia independiente."""
from __future__ import annotations

from services import analisis, semantica_plan, triangulacion
from tests.test_ia_datos_eval import HALLAZGOS_264, interpretacion, lectura

CORPUS = {
    "elementos": [
        {"id": "e1", "archivo": "t.xlsx", "hoja": "Chaco", "celda": "A1", "rol": "titulo_subtitulo_nota", "texto": "Matrícula — Provincia de Corrientes"},
        {"id": "e2", "archivo": "t.xlsx", "hoja": "Chaco", "celda": None, "rol": "nombre_hoja", "texto": "Chaco"},
    ],
    "bloques": [{"id": "b1", "referencias": ["e1", "e2"]}],
    "relaciones": [],
}
HIPOTESIS = {"tipo": "jurisdiccion", "referencias": ["e1", "e2"],
             "explicacion": "El título nombra Corrientes mientras la hoja se llama Chaco; la jurisdicción difiere.",
             "alternativa": "Plantilla reutilizada sin actualizar el título."}


def _llamar_base_falla(motivo, tipo):
    def llamar(fn, ctx, hs):
        if not ctx.get("_semantica_activa"):
            return {"modelo": ctx["_modelo"], "contenido": None, "error": motivo,
                    "llamadas": [{"status": "failed", "error_type": tipo, "discard_reason": motivo}]}
        return {"modelo": ctx["_modelo"], "contenido": {"prioritarios": [], "lectura": "x", "explicaciones_alternativas": [],
                                                        "confianza": "baja", "hallazgos_exploratorios": [HIPOTESIS]},
                "llamadas": [{"status": "completed"}]}
    return llamar


def test_lectura_truncada_no_se_disfraza_de_respuesta_263():
    it = semantica_plan.ejecutar(lambda: None, {"_modelo": "deepseek", "contexto_semantico": CORPUS}, HALLAZGOS_264,
                                 _llamar_base_falla("Salida truncada por límite de tokens; no acredita una revisión completa.", "token_limit"))
    assert "lectura" not in it["contenido"] and "prioritarios" not in it["contenido"]
    assert it["contenido"]["hallazgos_exploratorios"]
    assert it["estado_tareas"]["lectura_senales"]["estado"] == "fallida"
    assert it["estado_tareas"]["exploracion_libro"]["estado"] == "completada"
    assert "Lectura de señales" in it["error"]
    publico = analisis.estado_interpretacion_publico(it["modelo"], it["contenido"], it["error"], it["estado_tareas"])
    assert publico["estado"] == "sin_respuesta" and "límite de tokens" in publico["detalle"]
    c = triangulacion.consolidar(HALLAZGOS_264, [it])
    assert c["hallazgos_singulares"] == []
    assert "fallaron deepseek: salida truncada por límite de tokens" in c["linea_estado"]
    assert "Señales leídas por algún modelo: 0 de 2" in c["linea_estado"]


def test_limite_de_uso_del_proveedor_se_informa_240():
    it = semantica_plan.ejecutar(lambda: None, {"_modelo": "gemini", "contexto_semantico": CORPUS}, HALLAZGOS_264,
                                 _llamar_base_falla("429 RESOURCE_EXHAUSTED", "rate_limit"))
    publico = analisis.estado_interpretacion_publico(it["modelo"], it["contenido"], it["error"], it["estado_tareas"])
    assert publico["estado"] != "respondio" and "límite de uso" in publico["detalle"]


def test_registro_historico_con_lectura_sustituta_no_figura_como_respondio():
    sustituta = {"prioritarios": [], "lectura": "Exploración semántica independiente; consultar su alcance y evidencia comparativa.",
                 "explicaciones_alternativas": [], "confianza": "media", "hallazgos_exploratorios": []}
    assert analisis.estado_interpretacion_publico("deepseek", sustituta, None)["estado"] != "respondio"


def test_suspendido_figura_como_omitido():
    it = {"modelo": "claude", "contenido": None, "error": "Modelo temporalmente fuera de servicio", "status": "skipped"}
    assert analisis.modelos_consultados_publicos([it])[0]["estado"] == "omitido"
    c = triangulacion.consolidar(HALLAZGOS_264, [it, interpretacion("gpt", lectura("Revisar el dato 0.452 de 2021 (idx 0).", [0]))])
    assert "omitidos claude (suspendido)" in c["linea_estado"]


def test_respaldo_no_cuenta_como_coincidencia_independiente_282(monkeypatch):
    lecturas = {
        "gpt": lectura("Se detecta un valor aislado en el indicador 1500 para 2021 (idx 0).", [0]),
        "gemini": lectura("Comportamiento atípico en el rubro 1500 para 2021 (celda E11), valor 0.452 (idx 0).", [0]),
    }

    def proveedor(nombre):
        def interpretar(ctx, hs):
            contenido = dict(lecturas[nombre])
            if ctx.get("_semantica_activa"):
                contenido["hallazgos_exploratorios"] = []
            return {"modelo": nombre, "contenido": contenido, "error": None}
        return interpretar

    monkeypatch.setattr(triangulacion, "_interpretar_gpt", proveedor("gpt"))
    monkeypatch.setattr(triangulacion, "_interpretar_gemini", proveedor("gemini"))
    monkeypatch.setattr(type(triangulacion.settings), "modelo_habilitado", lambda self, m: True)
    monkeypatch.setattr(semantica_plan, "MAX_LLAMADAS", 1)  # la exploración del principal queda incompleta
    its = triangulacion.interpretar_con_modelos({"dominio": "general", "contexto_semantico": CORPUS}, HALLAZGOS_264)
    assert [(i["modelo"], i["rol"]) for i in its] == [("gpt", "principal"), ("gemini", "respaldo")]
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    assert c["coincidencias"] == []  # antes: "Varios modelos coincidieron"
    assert c["respaldo_no_independiente"]
    assert {s["modelo"]: s["rol"] for s in c["hallazgos_singulares"]} == {"gpt": "principal", "gemini": "respaldo"}
    assert "gemini (respaldo, no cuenta como coincidencia independiente)" in c["linea_estado"]
    assert analisis.modelos_consultados_publicos(its, c)[1]["rol"] == "respaldo"


def test_tope_de_consultas_se_informa_como_exploracion_parcial_no_como_demora():
    # Prueba en vivo con el libro de gasto: «No respondió a tiempo» parecía una falla y era el tope previsto.
    from services.reporte_ejecutivo import _estado_exploracion

    estado = _estado_exploracion({"evaluada": False, "motivos": [
        "Límite de llamadas o tiempo de la estrategia alcanzado; quedan tareas sin completar."]})
    assert estado.startswith("completada parcialmente")
    assert "a tiempo" not in estado


def test_evento_de_tope_de_consultas_es_informativo():
    from services.jobs import _evento_analisis

    ev = _evento_analisis({"tipo": "modelo", "modelo": "gpt", "ok": True, "exploracion_completada": False,
                           "motivos_exploracion": ["Límite de llamadas o tiempo de la estrategia alcanzado; "
                                                   "quedan tareas sin completar."]}, 4)
    assert ev["estado"] == "informativo"
    assert "quedó parcial" in ev["mensaje"] and "a tiempo" not in ev["detalle"]
