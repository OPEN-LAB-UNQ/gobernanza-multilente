"""Ejecuta la suite y fija en static/public-evidence.json el corte ensayado.

Registra fecha, conteos y la huella Python (versiones.version_codigo) del código
que produjo esos resultados. Solo escribe si la suite no tiene fallos.
Uso: ./venv/bin/python scripts/actualizar_evidencia_publica.py
"""
import datetime as dt
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from versiones import version_codigo  # noqa: E402


def datos_de_uso() -> dict:
    """Foto de los conteos de uso; la página los calcula en vivo y usa esta foto de respaldo."""
    from database import SessionLocal
    from services import uso_publico

    with SessionLocal() as db:
        return uso_publico.calcular(db)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"], cwd=ROOT)
        suite = ET.parse(junit).getroot()
        suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
        casos = list(suite.iter("testcase"))
    failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    xfailed = sum(1 for c in casos for s in c.findall("skipped") if s.get("type") == "pytest.xfail")
    skipped = int(suite.get("skipped", 0)) - xfailed
    collected = int(suite.get("tests", 0))
    if failed:
        print(f"La suite tiene {failed} fallo(s): no se actualiza la evidencia pública.")
        return 1
    evidencia = {
        "tests": {"date": dt.date.today().strftime("%d/%m/%Y"), "collected": collected,
                  "passed": collected - skipped - xfailed, "failed": 0, "skipped": skipped, "xfailed": xfailed},
        "code_fingerprint": version_codigo(),
        "uso": datos_de_uso(),
    }
    (ROOT / "static" / "public-evidence.json").write_text(json.dumps(evidencia, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidencia, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
