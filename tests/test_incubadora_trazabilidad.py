import datetime as dt

import models
from routers.proyectos_ia import (
    _bitacora_narrativa,
    _checkpoint_propuesta,
    _consulta_docente_pendiente,
    _contexto_progreso_para_ia,
    _contiene,
    _estado_acompanamiento,
    _fragmento_por_claves,
    _hay_bucle_reciente,
    _limitar_preguntas,
)


def test_acronimo_y_evidencia_sin_falsos_positivos():
    assert not _contiene("mejorar la experiencia diaria", ("ia",))
    assert _contiene("utilizar IA con supervision", ("ia",))
    assert _fragmento_por_claves("Una descripcion sin el concepto buscado.", ("indicador",), None) is None


def test_palabras_sueltas_no_hacen_proyecto_implementable():
    p = models.ProyectoIA(titulo="IA", situacion="problema usuarios evidencia datos flujo supervision riesgos indicador piloto", estado="revisado")
    checkpoint = _checkpoint_propuesta(p)
    assert checkpoint["madurez"] != "implementable"
    assert checkpoint["completos"] < 9


def test_bitacora_ordena_y_distingue_consulta_de_respuesta():
    p = models.ProyectoIA(titulo="Proyecto", situacion="Contexto", estado="en_proceso")
    p.mensajes = [
        models.MensajeProyectoIA(id=3, remitente="participante", contenido="Decidi cambiar los datos porque contienen nombres.", creado_en=dt.datetime(2026, 9, 3)),
        models.MensajeProyectoIA(id=2, remitente="consulta_docente", contenido="Podemos revisar el alcance?", creado_en=dt.datetime(2026, 9, 2)),
        models.MensajeProyectoIA(id=1, remitente="participante", contenido="Mi idea inicial es mejorar el proceso.", creado_en=dt.datetime(2026, 9, 1)),
    ]
    bitacora = _bitacora_narrativa(p)
    assert bitacora["idea_inicial"].startswith("Mi idea inicial")
    assert bitacora["intervencion_docente"] == "Sin respuesta docente registrada."
    assert [h["mensaje_id"] for h in bitacora["hitos"]] == [2, 3]
    assert "porque contienen nombres" in bitacora["hitos"][-1]["contenido"]


def test_checkpoint_escucha_aportes_de_la_conversacion():
    p = models.ProyectoIA(titulo="Asistente de soporte", situacion="Hay demoras frecuentes en la mesa de servicio que afectan al equipo.", estado="en_proceso")
    p.mensajes = [
        models.MensajeProyectoIA(
            id=1,
            remitente="participante",
            contenido=(
                "Usaremos registros y documentos anonimizados. El asistente clasifica consultas y propone respuestas, "
                "pero no decide ni reemplaza al agente responsable, que revisa y valida. Existe riesgo de error y privacidad. "
                "Mediremos antes y despues el tiempo promedio. Haremos un piloto para probar el flujo del proceso."
            ),
            creado_en=dt.datetime(2026, 9, 8),
        )
    ]
    checkpoint = _checkpoint_propuesta(p)
    assert checkpoint["completos"] >= 6
    assert any(c["clave"] == "supervision" and c["ok"] for c in checkpoint["criterios"])


def test_contexto_de_progreso_separa_deteccion_textual_de_cierres():
    p = models.ProyectoIA(titulo="Proyecto", situacion="Actualmente hay demoras y errores que afectan al equipo responsable.", estado="en_proceso")
    p.mensajes = []
    contexto = _contexto_progreso_para_ia(p, "Siguiente paso")
    assert "DETECCIÓN ORIENTATIVA" in contexto
    assert "CERRADOS POR EL PARTICIPANTE: ninguno" in contexto
    assert "AVANCE" in contexto
    assert "maximo dos focos" in contexto


def test_estado_acompanamiento_habilita_cierre_en_propuesta_defendible():
    p = models.ProyectoIA(
        titulo="Asistente para el area usuaria",
        organismo_area="Mesa de servicio",
        situacion="Actualmente el proceso de atención tiene demoras frecuentes que afectan a usuarios y al equipo responsable.",
        entrega_final=(
            "Problema: las demoras actuales dificultan sostener una atención oportuna y consistente. "
            "Usuarios: los agentes y ciudadanos necesitan respuestas claras durante todo el proceso. "
            "Evidencia: el volumen mensual y los errores observados muestran una dificultad verificable. "
            "Datos: el sistema utilizará documentos y archivos institucionales previamente anonimizados y autorizados. "
            "Flujo: el circuito recibe solicitudes, las procesa y produce una salida trazable. "
            "La IA clasifica las consultas y sugiere respuestas, pero nunca decide automáticamente. "
            "Supervisión humana: un responsable revisa, valida y conserva la decisión adoptada. "
            "Riesgos y límites: deben controlarse la privacidad, los sesgos y las respuestas incorrectas. "
            "Indicador: compararemos antes y después el tiempo promedio y el porcentaje de errores. "
            "Próximo paso: implementaremos un piloto acotado para probar y validar el prototipo."
        ),
        estado="en_proceso",
    )
    p.mensajes = []
    estado = _estado_acompanamiento(p)
    assert estado["listo_para_borrador"] is True
    assert "material suficiente" in estado["mensaje_cierre"]


def test_entrega_registrada_cierra_la_etapa_sin_reabrir_exigencias():
    p = models.ProyectoIA(titulo="Entrega breve", entrega_final="Borrador entregado por el participante.", estado="entregado")
    p.mensajes = []
    estado = _estado_acompanamiento(p)
    assert estado["entrega_registrada"] is True
    assert "disponible para revisión docente" in estado["mensaje_cierre"]
    assert "opcionales" in estado["mensaje_cierre"]


def test_cierre_manual_de_criterio_es_persistente_y_reversible():
    p = models.ProyectoIA(titulo="Proyecto", situacion="Caso inicial", estado="en_proceso")
    p.mensajes = [models.MensajeProyectoIA(id=1, remitente="control", contenido="criterio:datos:cerrado", creado_en=dt.datetime(2026, 9, 8))]
    datos = next(c for c in _checkpoint_propuesta(p)["criterios"] if c["clave"] == "datos")
    assert datos["ok"] is True
    assert datos["cierre_manual"] is True
    p.mensajes.append(models.MensajeProyectoIA(id=2, remitente="control", contenido="criterio:datos:abierto", creado_en=dt.datetime(2026, 9, 9)))
    datos = next(c for c in _checkpoint_propuesta(p)["criterios"] if c["clave"] == "datos")
    assert datos["cierre_manual"] is False


def test_detecta_repeticion_de_preguntas_y_limita_salida():
    mensajes = [
        models.MensajeProyectoIA(id=i, remitente="ia", contenido=texto, creado_en=dt.datetime(2026, 9, i))
        for i, texto in enumerate([
            "¿Quién revisa y valida finalmente las alertas del sistema?",
            "¿Qué persona revisa y valida las alertas que genera el sistema?",
            "¿Quién será responsable de revisar y validar las alertas del sistema?",
        ], start=1)
    ]
    assert _hay_bucle_reciente(mensajes) is True
    respuesta = _limitar_preguntas("¿Primera pregunta? ¿Segunda pregunta? ¿Tercera pregunta?")
    assert respuesta.count("?") == 2
    assert "Tercera pregunta" not in respuesta
    assert _limitar_preguntas("¿Primera? Segunda? Tercera?").count("?") == 2


def test_consulta_docente_pendiente_sigue_el_ultimo_estado_del_canal():
    mensajes = [models.MensajeProyectoIA(id=1, remitente="consulta_docente", contenido="Necesito ayuda")]
    assert _consulta_docente_pendiente(mensajes) is True
    mensajes.append(models.MensajeProyectoIA(id=2, remitente="docente", contenido="Respuesta"))
    assert _consulta_docente_pendiente(mensajes) is False
