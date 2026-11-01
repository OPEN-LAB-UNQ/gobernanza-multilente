from __future__ import annotations

import datetime as dt

import models
from routers import aprendizajes


class _QueryEventos:
    def order_by(self, *args, **kwargs):
        return self

    def limit(self, _n):
        return self

    def all(self):
        return []


class _QueryLentes:
    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return [("ajedrecista",)]


class _DB:
    def __init__(self):
        self.added = []
        self.by_id = {}

    def query(self, model_attr):
        if model_attr is models.LearningEvent:
            return _QueryEventos()
        return _QueryLentes()

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        for idx, obj in enumerate(self.added, start=1):
            obj.id = idx
            obj.creado_en = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            self.by_id[obj.id] = obj

    def refresh(self, _obj):
        return None

    def get(self, _model, id_):
        return self.by_id.get(id_)


def test_registrar_aprendizaje_crea_evento_estructurado(tmp_path, monkeypatch):
    path = tmp_path / "APRENDIZAJES.md"
    monkeypatch.setattr(aprendizajes, "APRENDIZAJES_PATH", path)
    db = _DB()
    usuario = models.Usuario(id=7, email="u@example.com", nombre="U", password_hash="x", rol="analista")

    resp = aprendizajes.registrar_aprendizaje(
        {
            "tipo": "falso_positivo",
            "titulo": "Correlación mecánica",
            "contenido": "Rizoma no debe comunicar columnas derivadas.",
            "informe_id": 12,
            "hallazgo_ids": ["34"],
        },
        db,
        usuario,
    )

    evento = db.added[0]
    assert isinstance(evento, models.LearningEvent)
    assert evento.tipo == "falso_positivo"
    assert evento.estado == "propuesto"
    assert evento.usuario_id == 7
    assert evento.informe_id == 12
    assert evento.hallazgo_ids == [34]
    assert evento.lente_afectada == "ajedrecista"
    assert "Estado: propuesto" in path.read_text(encoding="utf-8")
    assert resp["metricas"]["total_eventos"] == 0


def test_metricas_eventos_agrupa_tipo_estado_y_lente():
    eventos = [
        models.LearningEvent(tipo="falso_positivo", titulo="A", contenido="x", estado="validado", lente_afectada="rizoma", hallazgo_ids=[]),
        models.LearningEvent(tipo="falso_positivo", titulo="B", contenido="x", estado="propuesto", lente_afectada="rizoma", hallazgo_ids=[]),
        models.LearningEvent(tipo="regla_validada", titulo="C", contenido="x", estado="validado", lente_afectada=None, hallazgo_ids=[]),
    ]

    metricas = aprendizajes._metricas_eventos(eventos)

    assert metricas["por_tipo"] == {"falso_positivo": 2, "regla_validada": 1}
    assert metricas["por_estado"] == {"validado": 2, "propuesto": 1}
    assert metricas["por_lente"] == {"rizoma": 2, "sin_lente": 1}



def test_lector_no_puede_registrar_aprendizajes(tmp_path, monkeypatch):
    path = tmp_path / "APRENDIZAJES.md"
    monkeypatch.setattr(aprendizajes, "APRENDIZAJES_PATH", path)
    usuario = models.Usuario(id=8, email="l@example.com", nombre="L", password_hash="x", rol="lector")

    try:
        aprendizajes.registrar_aprendizaje(
            {"tipo": "criterio_metodologico", "titulo": "T", "contenido": "C"},
            _DB(),
            usuario,
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("lector no debe poder registrar aprendizajes")


def test_analista_no_puede_crear_aprendizaje_validado(tmp_path, monkeypatch):
    path = tmp_path / "APRENDIZAJES.md"
    monkeypatch.setattr(aprendizajes, "APRENDIZAJES_PATH", path)
    usuario = models.Usuario(id=9, email="a@example.com", nombre="A", password_hash="x", rol="analista")

    try:
        aprendizajes.registrar_aprendizaje(
            {"tipo": "criterio_metodologico", "titulo": "T", "contenido": "C", "estado": "validado"},
            _DB(),
            usuario,
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("analista solo debe proponer aprendizajes")


def test_admin_puede_cambiar_estado_de_aprendizaje():
    db = _DB()
    evento = models.LearningEvent(
        id=1,
        tipo="criterio_metodologico",
        titulo="T",
        contenido="C",
        estado="propuesto",
        hallazgo_ids=[],
        metadata_evento={},
    )
    db.added.append(evento)
    db.by_id[1] = evento
    usuario = models.Usuario(id=1, email="admin@example.com", nombre="Admin", password_hash="x", rol="admin")

    out = aprendizajes.actualizar_estado_aprendizaje(1, {"estado": "validado"}, db, usuario)

    assert out["estado"] == "validado"
    assert evento.metadata_evento["cambios_estado"][0]["de"] == "propuesto"
    assert evento.metadata_evento["cambios_estado"][0]["a"] == "validado"


def test_el_detalle_de_eventos_solo_lo_ve_admin_o_su_autor(tmp_path, monkeypatch):
    monkeypatch.setattr(aprendizajes, "APRENDIZAJES_PATH", tmp_path / "APRENDIZAJES.md")
    eventos = [
        models.LearningEvent(id=1, tipo="falso_positivo", titulo="A", contenido="x", estado="propuesto", usuario_id=7, hallazgo_ids=[]),
        models.LearningEvent(id=2, tipo="falso_positivo", titulo="B", contenido="y", estado="propuesto", usuario_id=9, hallazgo_ids=[]),
    ]

    class _Q:
        def order_by(self, *a):
            return self

        def limit(self, n):
            return self

        def all(self):
            return eventos

    class _DBEventos:
        def query(self, modelo):
            return _Q()

    monkeypatch.setattr(aprendizajes, "_metricas_proyectos_ia", lambda db, usuario=None: {})
    analista = models.Usuario(id=7, email="a@t", nombre="A", password_hash="x", rol="analista")
    admin = models.Usuario(id=1, email="b@t", nombre="B", password_hash="x", rol="admin")
    propio = aprendizajes.aprendizaje(_DBEventos(), analista)
    assert [e["id"] for e in propio["eventos"]] == [1]
    assert propio["metricas"]["total_eventos"] == 2  # las métricas agregadas siguen completas
    assert [e["id"] for e in aprendizajes.aprendizaje(_DBEventos(), admin)["eventos"]] == [1, 2]
