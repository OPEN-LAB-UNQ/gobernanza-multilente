import datetime as dt

import models
from routers import proyectos_ia as r


def proyecto():
    p = models.ProyectoIA(titulo="Caso", situacion="Caso inicial", estado="en_proceso")
    p.mensajes = []
    return p


def control(p, clave, estado):
    n = len(p.mensajes) + 1
    p.mensajes.append(
        models.MensajeProyectoIA(
            id=n,
            remitente="control",
            contenido=f"criterio:{clave}:{estado}",
            creado_en=dt.datetime(2026, 9, 26, 0, 0, n),
        )
    )


def test_posponer_persiste_sin_completar_y_se_puede_retomar():
    p = proyecto()
    control(p, "datos", "pospuesto")
    c = next(c for c in r._checkpoint_propuesta(p)["criterios"] if c["clave"] == "datos")
    assert c["pospuesto"] and not c["ok"]
    estado = r._estado_acompanamiento(p)
    assert "datos" not in [c["clave"] for c in estado["necesarios"]]
    assert "datos" in [c["clave"] for c in estado["pospuestos"]]
    assert not estado["listo_para_entregar"]
    assert "POSPUESTO" in r._contexto_progreso_para_ia(p, "Continuemos")
    control(p, "datos", "abierto")
    assert "datos" in [c["clave"] for c in r._estado_acompanamiento(p)["necesarios"]]


def test_esenciales_completos_permiten_cerrar_sin_opcionales():
    p = proyecto()
    for clave in ["problema", "datos", "rol_ia", "supervision", "riesgos", "indicador", "proximo_paso"]:
        control(p, clave, "cerrado")
    e = r._estado_acompanamiento(p)
    assert e["listo_para_entregar"] and not e["necesarios"] and e["opcional"]
    assert "ya podés entregar" in e["mensaje_cierre"]
    assert "?" not in r._respuesta_sin_insistencia("Resumen del caso. ¿Qué más agregarías?", p, "Listo")


def test_entregado_no_reabre_pendientes():
    p = proyecto()
    p.estado = "entregado"
    assert not r._estado_acompanamiento(p)["necesarios"]
    assert "Próximo punto" not in r._fallback_respuesta("seguir", p)


def test_limite_elimina_pregunta_en_vez_de_cambiar_signo():
    salida = r._limitar_preguntas("Resumen útil. ¿Uno? ¿Dos? ¿Tres?")
    assert "Resumen útil." in salida and "Tres" not in salida
    assert salida.count("?") == 2


def test_recuperacion_sin_preguntas_y_siguiente_con_una():
    p = proyecto()
    texto = "Tu avance se conserva. ¿Qué fuente usarás? ¿Quién revisa?"
    assert "?" not in r._respuesta_sin_insistencia(texto, p, "HELP estoy trabado")
    assert r._respuesta_sin_insistencia(texto, p, "Siguiente paso").count("?") == 1


def test_no_repite_pregunta_tras_respuesta_del_alumno():
    p = proyecto()
    pregunta = "¿Quién revisa y valida finalmente las alertas del sistema?"
    p.mensajes = [
        models.MensajeProyectoIA(remitente="ia", contenido=pregunta),
        models.MensajeProyectoIA(remitente="participante", contenido="La directora del área."),
    ]
    salida = r._respuesta_sin_insistencia("La directora queda como responsable. " + pregunta, p, "Continuemos")
    assert "La directora" in salida and "¿Quién" not in salida


def test_posponer_por_endpoint_guarda_evento_y_recarga_estado():
    from sqlalchemy import create_engine
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.compiler import compiles, deregister
    from sqlalchemy.orm import Session

    from database import Base

    @compiles(JSONB, "sqlite")
    def json_sqlite(element, compiler, **kw):
        return "JSON"

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            m.__table__ for m in (models.Usuario, models.ProyectoIA, models.MensajeProyectoIA, models.ActivityEvent)
        ],
    )
    try:
        with Session(engine) as db:
            u = models.Usuario(nombre="Alumno", email="alumno@example.test", password_hash="test", rol="analista")
            db.add(u)
            db.commit()
            p = models.ProyectoIA(usuario_id=u.id, titulo="Caso", situacion="Caso inicial", estado="en_proceso")
            db.add(p)
            db.commit()
            r.cambiar_estado_criterio("datos", "posponer", usuario=u, db=db)
            db.expire_all()
            guardado = db.query(models.ProyectoIA).filter_by(id=p.id).one()
            assert "datos" in [c["clave"] for c in r._estado_acompanamiento(guardado)["pospuestos"]]
            r.cambiar_estado_criterio("datos", "reabrir", usuario=u, db=db)
            db.expire_all()
            assert "datos" in [c["clave"] for c in r._estado_acompanamiento(guardado)["necesarios"]]
    finally:
        engine.dispose()
        deregister(JSONB)
