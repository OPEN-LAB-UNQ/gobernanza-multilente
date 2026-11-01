"""Genera la demo pública en una base temporal, sin usuarios ni modelos externos.

Reutiliza el recorrido de integración del catálogo para asegurar que los PDF
proceden del motor real y que ninguno de los 16 análisis toca producción.
"""

from __future__ import annotations

import re
import runpy
from pathlib import Path
from zipfile import ZipFile

from pytest import MonkeyPatch

import models
from services.reportes.markdown import _periodo_observado

DESTINO = Path(__file__).resolve().parents[1] / "static" / "public-samples"


def main() -> None:
    suite = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests" / "test_ejemplos_zip.py"))
    monkeypatch = MonkeyPatch()
    recorrido = suite["flujo"].__wrapped__(monkeypatch)
    DESTINO.mkdir(parents=True, exist_ok=True)
    try:
        cliente, factory, _actual = next(recorrido)
        for caso in range(1, 9):
            ids = suite["ejecutar_par"](cliente, caso)
            # El fixture de pruebas declara un mes fijo. En la demo, el período
            # de referencia debe coincidir con el último mes observado cuando
            # el archivo contiene una serie mensual identificable.
            with factory() as db:
                for informe_id in ids.values():
                    informe = db.get(models.Informe, informe_id)
                    observado = _periodo_observado(informe.datos)
                    rango = re.fullmatch(r"(\d{4}-\d{2}) a (\d{4}-\d{2})", observado)
                    if rango:
                        informe.periodo = rango[2]
                db.commit()
            respuesta = cliente.post(f"/api/ejemplos/{caso}/zip", json=ids)
            if respuesta.status_code != 200:
                raise RuntimeError(f"Caso {caso}: {respuesta.status_code} {respuesta.text}")
            destino = DESTINO / f"caso-{caso}.zip"
            destino.write_bytes(respuesta.content)
            with ZipFile(destino) as archivo:
                assert len(archivo.namelist()) == 4 and archivo.testzip() is None
            print(f"{destino.name}: {destino.stat().st_size} bytes")
    finally:
        try:
            next(recorrido)
        except StopIteration:
            pass
        monkeypatch.undo()


if __name__ == "__main__":
    main()
