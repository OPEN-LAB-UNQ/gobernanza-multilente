"""La alerta detecta 500, fallos del worker y la caída del servicio (una vez, no en cada corrida)."""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("alerta_errores", RAIZ / "scripts" / "alerta_errores.py")
alerta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alerta)


def test_detecta_fallos_del_worker_que_no_son_500():
    texto = ("sep 29 uvicorn: ERROR fallo el analisis del informe 245: boom\n"
             'sep 29 uvicorn: INFO "GET /api/health HTTP/1.1" 200 OK\n')
    assert len(alerta._extraer_fallos_worker(texto)) == 1
    assert alerta._extraer_500(texto) == []


def test_la_caida_se_avisa_una_vez_y_la_vuelta_tambien(tmp_path, monkeypatch):
    enviados = []
    monkeypatch.setattr(alerta, "VAR_DIR", tmp_path)
    monkeypatch.setattr(alerta, "ESTADO_PATH", tmp_path / "ultimo")
    monkeypatch.setattr(alerta, "CAIDA_PATH", tmp_path / "caido")
    monkeypatch.setattr(alerta, "_journal_entre", lambda d, h: "")
    monkeypatch.setattr(alerta, "_enviar_alerta", lambda lineas, asunto=None, intro=None: enviados.append(asunto))
    monkeypatch.setattr(alerta, "_servicio_activo", lambda: False)
    monkeypatch.setattr(alerta, "_horas_desde_ultimo_backup", lambda ahora: 1.0)  # el backup no es lo que se prueba acá
    alerta.main()
    alerta.main()
    assert enviados == ["Gobernanza: el servicio no está activo"]
    monkeypatch.setattr(alerta, "_servicio_activo", lambda: True)
    alerta.main()
    assert enviados[-1] == "Gobernanza: el servicio volvió" and len(enviados) == 2


def test_antiguedad_del_backup(tmp_path):
    import os
    from datetime import datetime

    from scripts import alerta_errores as alerta
    ahora = datetime.now()
    assert alerta._horas_desde_ultimo_backup(ahora, tmp_path) is None
    dump = tmp_path / "gobernanza-20261001-044500.dump"
    dump.write_bytes(b"x")
    os.utime(dump, (ahora.timestamp() - 30 * 3600,) * 2)
    (tmp_path / "manual-gobernanza-pre-borrado.dump").write_bytes(b"x")  # los manuales no cuentan
    assert 29.5 < alerta._horas_desde_ultimo_backup(ahora, tmp_path) < 30.5
