"""La vigilancia de la cola destraba sola los casos que el 08/10 la detuvieron."""
import datetime as dt
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("vigilar_cola", Path(__file__).resolve().parents[1] / "scripts" / "vigilar_cola.py")
vigilar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vigilar)

AHORA = dt.datetime(2026, 10, 8, 16, 40)
hace = lambda minutos: AHORA - dt.timedelta(minutes=minutos)  # noqa: E731


def test_pendiente_sin_nada_en_analisis_reinicia():
    # Caso real: el informe 312 esperó 17 minutos con el hilo del worker muerto.
    assert vigilar.decidir([(317, "pendiente", hace(17), None)], AHORA)[0] == "reiniciar"


def test_cola_normal_no_se_toca():
    trabajos = [(1, "procesando", hace(6), hace(5)), (2, "pendiente", hace(5), None)]
    assert vigilar.decidir(trabajos, AHORA)[0] == "nada"
    assert vigilar.decidir([(3, "pendiente", hace(1), None)], AHORA)[0] == "nada"  # recién cargado
    assert vigilar.decidir([], AHORA)[0] == "nada"


def test_analisis_colgado_se_marca_y_reinicia():
    accion, colgados, _ = vigilar.decidir([(9, "procesando", hace(40), hace(30))], AHORA)
    assert accion == "reiniciar" and colgados == [9]
