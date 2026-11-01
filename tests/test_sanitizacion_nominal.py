"""Rótulos nominales y teléfonos no llegan a los proveedores de IA."""
import pytest

from routers.carga_rapida import _limpiar_orientacion_analisis
from services.sanitizacion import columna_sensible, redactar_texto_libre


@pytest.mark.parametrize("nombre", [
    "nombre_agente", "dni_agente", "email_agentes", "Apellido y nombre del agente",
    "legajo", "Domicilio", "telefono_contacto",
])
def test_rotulo_nominal_se_excluye_aunque_mencione_agentes(nombre):
    assert columna_sensible(nombre)


@pytest.mark.parametrize("nombre", ["agentes", "cantidad_agentes", "dotacion", "Credito vigente"])
def test_conteos_agregados_se_conservan(nombre):
    assert not columna_sensible(nombre)


@pytest.mark.parametrize("texto", ["tel 11-4555-1234", "llamar al 0351-455-1234", "cel: +54 9 11 4555 1234"])
def test_telefonos_se_redactan(texto):
    assert "[TELEFONO_REDACTADO]" in redactar_texto_libre(texto)


@pytest.mark.parametrize("texto", ["fecha 2026-09-28", "monto 1.234.567", "programa 16-01-00", "partida 3.4.9"])
def test_codigos_y_montos_no_se_tocan(texto):
    assert redactar_texto_libre(texto) == texto


def test_orientacion_del_participante_se_redacta():
    limpia = _limpiar_orientacion_analisis("Revisar el total; consultas a juan@x.com o DNI 30123456")
    assert "juan@x.com" not in limpia and "30123456" not in limpia
    assert limpia.startswith("Revisar el total")
