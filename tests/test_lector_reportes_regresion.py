"""Regresiones de la revisión del 21/10: señal real, descargas y fallas visibles."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

import models
from config import settings
from services import interpretacion_previa as ip
from services import jobs
from services import lector_mapa as lm
from services.reportes.markdown import (
    _con_lector_cuadro,
    render_comprobante_controles_markdown,
    render_reporte_markdown,
    render_reporte_pdf,
)
from tests.flujo_confirmado import respuesta_fixture
from tests.test_lector_punta_a_punta import NETO, _cargar, _libro

pytest_plugins = ["tests.test_ejemplos_zip"]


def _pdf_texto(markdown):
    pdf = render_reporte_pdf(markdown)
    assert pdf.startswith(b"%PDF")
    return " ".join(" ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages).split())


@pytest.mark.parametrize("historico", [False, True])
def test_senal_del_lector_se_exporta_en_todas_las_piezas(flujo, monkeypatch, historico):
    client, factory, _ = flujo
    monkeypatch.setattr(settings, "lector_ia", "activo")
    monkeypatch.setattr(lm, "llamar", lambda p, q: ({**respuesta_fixture(p, q)[0], "relaciones": [NETO]}, p))
    monkeypatch.setattr(lm, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"])
    informe_id = _cargar(client)
    assert jobs._process_one()
    with factory() as db:
        informe = db.get(models.Informe, informe_id)
        senales = [h for h in informe.hallazgos if h.modo == "relacion_leida_no_cierra"]
        assert len(senales) == 1 and senales[0].evidencia["celda"] == "D9"
        if historico:
            senales[0].limites = dict(senales[0].limites, fundamento_regla="relación conservada de lector 1.3")
        else:
            assert isinstance(senales[0].limites["fundamento_regla"], dict)
        for pieza in ("ejecutivo", "completo", "anexo"):
            md = render_reporte_markdown(informe, informe.hallazgos, True, True, pieza=pieza)
            texto = _pdf_texto(md)
            assert "D9" in texto and "Lector del cuadro" in texto
        assert "D9" in _pdf_texto(render_comprobante_controles_markdown(informe))


def test_falla_interna_de_verificacion_se_declara_en_pantalla_y_pdf(flujo, monkeypatch):
    client, factory, _ = flujo
    monkeypatch.setattr(settings, "lector_ia", "activo")
    def falla(*args, **kwargs):
        raise RuntimeError("credencial-privada-no-exportar")
    etapa = "analizar"
    monkeypatch.setattr(ip, "verificar_relaciones", falla)
    monkeypatch.setattr(lm, "llamar", respuesta_fixture)
    monkeypatch.setattr(lm, "lectoras_habilitadas", lambda: ["gpt", "gemini", "deepseek"])
    informe_id = _cargar(client)
    assert jobs._process_one()
    with factory() as db:
        informe = db.get(models.Informe, informe_id)
        mapa = informe.saneamiento["mapa_lectura"]
        assert lm.resumen_lectura(mapa)["estado"] == "no_completada"
        assert mapa["fallo"]["etapa"] == etapa
        assert mapa["senales"] == 0
        publico = lm.saneamiento_publico(informe.saneamiento)
        assert publico["mapa_lectura"]["fallo"]["etapa"] == etapa
        assert "credencial-privada" not in str(publico)
        for pieza in ("ejecutivo", "completo", "anexo"):
            md = render_reporte_markdown(informe, informe.hallazgos, True, True, pieza=pieza)
            assert "NO COMPLETADA" in md and "No se pudo" in md
            assert "credencial-privada" not in md
            assert "NO COMPLETADA" in _pdf_texto(md)


def test_falla_de_grilla_impide_confirmar_y_no_ejecuta_controles(flujo, monkeypatch):
    client, factory, _ = flujo
    def falla(*args):
        raise RuntimeError("credencial-privada-no-exportar")
    monkeypatch.setattr(lm, "grillas", falla)
    r = client.post("/api/analisis-rapido", data={"modo_revision": "profunda"}, files={"archivos": ("altas.xlsx", _libro(), "application/octet-stream")})
    assert r.status_code == 503
    assert "No se ejecutaron controles" in r.text and "credencial-privada" not in r.text
    with factory() as db:
        assert db.query(models.AnalysisJob).count() == 0
        assert db.query(models.Hallazgo).count() == 0


def test_limite_de_cinco_declara_todas_las_diferencias_sin_ocultar_el_total():
    celdas = {}
    for fila in range(2, 42):
        celdas.update({f"A{fila}": 10., f"B{fila}": 20., f"C{fila}": 50. if fila < 10 else 30.})
    relacion = dict(tipo="columnas", destino="C", expresion="A+B", filas=[2, 41])
    def fn(p, q):
        return {"relaciones": [relacion]}, p
    san = {"grillas_lectura": [dict(archivo="prueba.xlsx", hoja="H", celdas=celdas)]}
    lectura = lm.analizar(san, fn, ["gpt", "gemini"], "activo")
    assert len(lectura["senales"]) == 5
    mapa = lectura["estado"]
    assert len(mapa["hojas"][0]["grupos"][0]["fallas"]) == 8
    resumen = lm.resumen_lectura(mapa)
    assert (resumen["diferencias_total"], resumen["diferencias_mostradas"], resumen["diferencias_no_mostradas"]) == (8, 5, 3)
    for senal in lectura["senales"]:
        assert senal["evidencia"]["diferencias_total"] == 8
        assert "5 de 8" in senal["descripcion"]
    md = _con_lector_cuadro("# Informe\n\nResultado", SimpleNamespace(saneamiento={"mapa_lectura": mapa}))
    assert "5 de 8" in md and "3 adicionales" in md
    assert "5 de 8" in _pdf_texto(md)
    publico = lm.saneamiento_publico(dict(san, mapa_lectura=mapa))
    assert publico["mapa_lectura"]["resumen"]["limites_de_muestra"] == [
        dict(archivo="prueba.xlsx", hoja="H", relacion="C = A+B", total=8, mostradas=5)]
    for celda in (f"C{f}" for f in range(2, 10)):
        celdas[celda] = 30.
    restaurada = lm.analizar(san, fn, ["gpt", "gemini"], "activo")
    assert restaurada["senales"] == []
    assert lm.resumen_lectura(restaurada["estado"])["diferencias_total"] == 0


def test_recuperar_un_lector_fallido_conserva_historial_y_restaura_cobertura():
    san = {"mapa_lectura": {"confirmaciones": {"otra": {"confirma": False}},
                            "historial_confirmaciones": [{"id": "otra", "confirma": False}]},
           "grillas_lectura": [dict(archivo="a.xlsx", hoja="H", celdas={"A1": 12., "B1": 34.})]}
    san["mapa_lectura"] = lm.lectura_fallida(san, "analizar")["estado"]
    assert san["mapa_lectura"]["confirmaciones"]["otra"]["confirma"] is False
    lectura = lm.analizar(san, lambda p, q: ({"relaciones": []}, p), ["gpt", "gemini"], "activo")
    assert "fallo" not in lectura["estado"]
    assert lectura["estado"]["historial_confirmaciones"] == [{"id": "otra", "confirma": False}]
    assert lm.resumen_lectura(lectura["estado"])["estado"] == "completada"
