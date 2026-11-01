import datetime as dt
from types import SimpleNamespace

from routers import proyectos_ia


def proyecto(proyecto_id: int, titulo: str, situacion: str = ""):
    return SimpleNamespace(
        id=proyecto_id,
        titulo=titulo,
        organismo_area="Área de prueba",
        situacion=situacion,
        entrega_final="",
        mensajes=[],
        actualizado_en=dt.datetime(2026, 9, proyecto_id),
    )


def test_conexiones_tipifica_cada_punto_de_contacto():
    assert proyectos_ia.TEMAS_RIZOMA
    assert all(tema.get("tipo") for tema in proyectos_ia.TEMAS_RIZOMA)
    assert all(tema.get("tipo_label") for tema in proyectos_ia.TEMAS_RIZOMA)


def test_oportunidad_destacada_une_expediente_presupuesto_y_acto():
    proyectos = [
        proyecto(1, "Vinculación automatizada en sistema de expedientes", "Ordenar el ingreso de expedientes"),
        proyecto(2, "Verificar Modificaciones presupuestarias", "Controlar una modificación presupuestaria"),
        proyecto(3, "Asistente para redacción de actos administrativos", "Preparar el acto administrativo"),
    ]

    oportunidades = proyectos_ia._oportunidades_cartera(proyectos)

    destacada = oportunidades[0]
    assert destacada["id"] == "expediente_decision"
    assert destacada["destacada"] is True
    assert destacada["cantidad"] == 3
    assert len(destacada["casos"]) == 3
    assert all(caso["aporte"] for caso in destacada["casos"])
    assert "prueba" in destacada
    assert "claves" not in destacada


def test_no_publica_oportunidad_con_un_unico_proyecto():
    oportunidades = proyectos_ia._oportunidades_cartera([
        proyecto(1, "Asistente para analizar la prensa extranjera"),
    ])

    assert not any(item["id"] == "observatorio_publico" for item in oportunidades)


def test_nucleo_fiscal_propone_capacidad_compartida():
    oportunidades = proyectos_ia._oportunidades_cartera([
        proyecto(1, "Análisis de Recaudación Nacional"),
        proyecto(2, "Informe de Subsidios de la APN"),
        proyecto(3, "Verificar Modificaciones presupuestarias"),
    ])

    fiscal = next(item for item in oportunidades if item["id"] == "nucleo_fiscal")
    assert fiscal["cantidad"] == 3
    assert "controles" in fiscal["resultado"].lower()


def test_subsidios_prioriza_categoria_presupuesto_aunque_mencione_normativa():
    etiqueta = proyectos_ia._etiqueta_caso(
        "Sistema Asistido sobre el Informe de Subsidios de la APN",
        "Dirección de Análisis de Política Fiscal",
        "Revisa subsidios y las resoluciones relacionadas.",
    )

    assert etiqueta == "Presupuesto"


def test_selector_recibe_todos_los_proyectos_y_vinculos(monkeypatch):
    proyectos=[proyecto(i,'Vinculación de expedientes en sistema de expedientes') for i in range(1,12)]
    proyectos.append(proyecto(12,'Propuesta sin afinidad conocida'))
    monkeypatch.setattr(proyectos_ia,'_proyectos_visibles',lambda db, **_:proyectos)
    data=proyectos_ia.conexiones_casos_companeros(_usuario=None,db=None)
    assert len(data['proyectos'])==12
    assert all(set(p)=={'id','titulo','etiqueta','cohorte'} for p in data['proyectos'])
    # Sin base para leer las actividades, cada proyecto lo dice en vez de quedar sin cohorte.
    assert all(p['cohorte']==proyectos_ia.SIN_COHORTE for p in data['proyectos'])
    assert any(len(c['casos'])==11 for c in data['cruces'])
    assert any(len(c['casos'])==11 for c in data['oportunidades'])
    assert all(len(c['casos'])==c['cantidad'] for c in data['cruces']+data['oportunidades'])


class _ConsultaCohortes:
    def __init__(self, filas):
        self.filas = filas

    def all(self):
        return self.filas


class _BaseCohortes:
    """Base mínima: sólo responde la consulta de cohortes de las actividades de la cursada."""

    def __init__(self, filas):
        self.filas = filas

    def query(self, *columnas):
        return _ConsultaCohortes(self.filas)


def test_cohorte_de_cada_proyecto_sale_de_las_actividades():
    base = _BaseCohortes([("Cohorte septiembre 2026", [1, 2]), ("Cohorte noviembre 2026", [2, 3])])
    cohortes = proyectos_ia._cohortes_por_proyecto(base)
    assert cohortes[1] == "Cohorte septiembre 2026"
    # Un proyecto que figura en dos actividades muestra ambas, no una elegida al azar.
    assert cohortes[2] == "Cohorte noviembre 2026 · Cohorte septiembre 2026"
    assert 4 not in cohortes


def test_conexiones_cruza_cohortes_y_etiqueta_cada_proyecto(monkeypatch):
    proyectos = [
        proyecto(1, "Vinculación automatizada en sistema de expedientes", "Ordenar el ingreso de expedientes"),
        proyecto(2, "Vinculación de expedientes en sistema de expedientes", "Normalizar expedientes"),
        proyecto(3, "Propuesta sin afinidad conocida"),
    ]
    monkeypatch.setattr(proyectos_ia, "_proyectos_visibles", lambda db, **_: proyectos)
    monkeypatch.setattr(proyectos_ia, "_registrar_consulta", lambda db, usuario, accion: None)
    base = _BaseCohortes([("Cohorte A", [1]), ("Cohorte B", [2])])
    data = proyectos_ia.conexiones_casos_companeros(_usuario=None, db=base)
    por_id = {p["id"]: p["cohorte"] for p in data["proyectos"]}
    assert por_id == {1: "Cohorte A", 2: "Cohorte B", 3: proyectos_ia.SIN_COHORTE}
    # El cruce reúne proyectos de cohortes distintas y declara cuáles.
    cruce = next(c for c in data["cruces"] if {caso["id"] for caso in c["casos"]} >= {1, 2})
    assert cruce["cohortes"] == ["Cohorte A", "Cohorte B"]
    assert all(caso["cohorte"] for caso in cruce["casos"])
    for oportunidad in data["oportunidades"]:
        assert all("cohorte" in caso for caso in oportunidad["casos"])


def test_si_no_puede_leer_cohortes_conexiones_responde_igual():
    class BaseRota:
        def query(self, *columnas):
            raise RuntimeError("sin conexión")

        def rollback(self):
            pass

    assert proyectos_ia._cohortes_por_proyecto(BaseRota()) == {}
