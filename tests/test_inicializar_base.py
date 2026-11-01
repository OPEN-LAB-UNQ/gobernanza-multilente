"""La instalación desde cero carga las definiciones vigentes de los protocolos."""
import json
from pathlib import Path

DATOS = Path(__file__).resolve().parents[1] / "sql" / "datos_referencia_protocolos.json"


def test_datos_de_referencia_tienen_los_protocolos_vigentes():
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    versiones = {(v["codigo"], v["version"]): v for v in datos["versiones_protocolo"]}
    activos = sorted((c, v) for (c, v), fila in versiones.items() if fila["activo"])
    assert activos == [("B-1", "1.2"), ("R-1", "1.1")]
    controles = {}
    for control in datos["definiciones_control"]:
        controles.setdefault(control["protocolo_id"], []).append(control["codigo"])
    assert len(controles[versiones[("B-1", "1.2")]["id"]]) == 11
    assert len(controles[versiones[("R-1", "1.1")]["id"]]) == 15
    for fila in datos["versiones_protocolo"]:
        assert isinstance(fila["model_policy"], dict)


def test_datos_de_referencia_no_traen_informacion_de_usuarios():
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    assert set(datos) == {"descripcion", "exportado", "versiones_protocolo", "definiciones_control"}
    texto = DATOS.read_text(encoding="utf-8")
    assert "@" not in texto


def test_requirements_incluye_alembic_para_instalar():
    requisitos = (DATOS.parents[1] / "requirements.txt").read_text(encoding="utf-8")
    assert any(linea.startswith("alembic==") for linea in requisitos.splitlines())
