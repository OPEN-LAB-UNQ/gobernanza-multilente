import models
from services import jobs
from services.reportes.markdown import render_comprobante_controles_markdown


def test_evento_lente_es_descriptivo_y_no_simulado():
    evento = jobs._evento_analisis(
        {"tipo": "lente", "lente": "matematico", "nombre": "Matemático", "cantidad": 2},
        4,
    )

    assert evento["etapa"] == "controles"
    assert evento["paso"] == 4
    assert "Cálculos y métodos" in evento["mensaje"]
    assert "2 señales" in evento["detalle"]


def test_job_expone_traza_metricas_y_version_desde_resultado():
    job = models.AnalysisJob(
        informe_id=1,
        estado="finalizado",
        resultado={
            "_progreso": [{"paso": 1, "etapa": "carga"}],
            "_metricas": {"duracion_segundos": 1.25},
            "_version_analisis": "piloto-prueba",
        },
    )

    assert job.progreso == [{"paso": 1, "etapa": "carga"}]
    assert job.metricas == {"duracion_segundos": 1.25}
    assert job.version_analisis == "piloto-prueba"


def test_job_historico_sin_sobre_es_compatible():
    job = models.AnalysisJob(informe_id=1, estado="finalizado", resultado={"hallazgos": []})

    assert job.progreso == []
    assert job.metricas == {}
    assert job.version_analisis is None


def test_comprobante_automatico_no_se_presenta_como_sello_humano():
    area = models.Area(id=1, nombre="Área de prueba", codigo="PRUEBA")
    informe = models.Informe(
        id=7,
        area_id=1,
        periodo="2026-09",
        dominio="general",
        modo="intraarea",
        datos=[{"periodo": "2026-09", "total": 10}],
        saneamiento={},
    )
    informe.area = area
    informe.devolucion = models.Devolucion(
        informe_id=7,
        mensaje="Sin señales",
        hay_hallazgos=False,
        estado="SIN_SENALES_COMUNICABLES",
        cobertura={"filas_analizadas": 1, "lentes": [{"lente": "ajedrecista", "hallazgos": 0}]},
    )
    informe.hallazgos = []
    job = models.AnalysisJob(
        informe_id=7,
        estado="finalizado",
        resultado={
            "_version_analisis": "piloto-prueba",
            "_metricas": {"lentes_ejecutadas": 7, "duracion_segundos": 0.4},
        },
    )

    comprobante = render_comprobante_controles_markdown(informe, job)

    assert "Comprobante de controles automáticos aplicados" in comprobante
    assert "CONTROLES EJECUTADOS SIN OBSERVACIONES MECÁNICAS" in comprobante
    assert "No certifica la veracidad" in comprobante
    assert "se genera automáticamente al finalizar los controles" in comprobante
