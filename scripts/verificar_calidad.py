#!/usr/bin/env python3
"""Ejecuta controles en copia temporal, sin .env, credenciales ni base real."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARPETAS = ("core", "routers", "services", "tests", "static", "scripts", "docs", "sql", "alembic", "systemd")
EXCEL = [
    "tests/test_calendario_solicitado.py",
    "tests/test_orden_temporal.py",
    "tests/test_ausencias_adicionales.py",
    "tests/test_unidades_adicionales.py",
    "tests/test_limites_adicionales.py",
    "tests/test_periodos_adicionales.py",
    "tests/test_relaciones_adicionales.py",
    "tests/test_formatos_adicionales.py",
    "tests/test_semantica_cobertura.py",
    "tests/test_semantica_excel.py",
    "tests/test_robustez_estructural.py",
    "tests/test_gpsda214.py",
    "tests/test_deuda_real.py",
    "tests/test_sembrada2023.py", "tests/test_casos_revision.py",
    "tests/test_ensayo_controles.py",
    "tests/test_periodos_ventanas.py",
    "tests/test_benchmark_una_hoja.py",
    "tests/test_controles_tabulares.py",
    "tests/test_benchmark_tabular.py",
    "tests/test_benchmark_integracion.py",
    "tests/test_ispi_regresion.py",
    "tests/test_ispi_integracion.py",
    "tests/test_excel_multihoja.py",
    "tests/test_series_contexto.py",
    "tests/test_formulas_cuadros.py",
    "tests/test_formula_integridad.py",
    "tests/test_revision_ocho_casos.py",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", action="store_true", help="Barrera de regresión Excel para empaquetado")
    args = parser.parse_args()
    # Lista permitida: no heredar claves de proveedores, SMTP ni DATABASE_URL.
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT") if k in os.environ}
    with tempfile.TemporaryDirectory(prefix="gobernanza-calidad-") as temporal:
        stage = Path(temporal)
        for nombre in CARPETAS:
            if (ROOT / nombre).exists():
                shutil.copytree(
                    ROOT / nombre,
                    stage / nombre,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"),
                    symlinks=False,
                )
        for patron in ("*.py", "*.md", "LICENSE", "requirements*.txt", "pyproject.toml", "alembic.ini"):
            for archivo in ROOT.glob(patron):
                shutil.copy2(archivo, stage / archivo.name)
        env.update(
            DATABASE_URL="sqlite://",
            SECRET_KEY="test-only",
            GOBERNANZA_PASSWORD="test-only",
            GOBERNANZA_PYTHON=sys.executable,
        )
        # No se aceptan selecciones externas que omitan pruebas.
        comando = [sys.executable, "-m", "pytest", "-q"] + (EXCEL if args.excel else ["tests"])
        subprocess.run(comando, cwd=stage, env=env, check=True)
        # Cambiar el código cambia las semillas; mismo código reproduce la campaña.
        # Fuera del temporal: un fallo conserva los libros aunque se cierre la suite.
        evidencia = Path(tempfile.mkdtemp(prefix="gobernanza-evidencia-mutaciones-")) / "campana"
        print(f"Evidencia de mutaciones: {evidencia}", flush=True)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from versiones import version_codigo; from scripts.ensayo_controles import ejecutar; "
                "import sys; sys.exit(ejecutar(int(version_codigo()[:8],16),4,sys.argv[1]))",
                str(evidencia),
            ],
            cwd=stage,
            env=env,
            check=True,
        )
        estructural = evidencia.parent / "estructuras"
        subprocess.run(
            [sys.executable, "-c", "from versiones import version_codigo; from scripts.ensayo_estructuras import ejecutar; import sys; sys.exit(ejecutar(int(version_codigo()[8:16],16),4,sys.argv[1]))", str(estructural)],
            cwd=stage, env=env, check=True,
        )
        # Ambas campañas pasaron: la evidencia sólo se conserva cuando algo falla
        # (check=True corta antes de llegar acá); si no, se acumulaba una carpeta por corrida.
        shutil.rmtree(evidencia.parent, ignore_errors=True)
        print("Evidencia de mutaciones descartada: las campañas no registraron fallos.", flush=True)
        if not args.excel:
            subprocess.run(
                ["node", "--test", "tests/ejemplos_zip_ui.cjs", "tests/controles_tabulares_ui.cjs", "tests/incubadora_claridad_ui.cjs", "tests/ocr_ui.cjs", "tests/errores_ui.cjs", "tests/progreso_real_ui.cjs", "tests/contrato_simple_ui.cjs", "tests/recorridos_ui.cjs", "tests/lector_cuadro_ui.cjs", "tests/interpretacion_previa_ui.cjs"],
                cwd=stage,
                env=env,
                check=True,
            )
    print("APROBADO: regresión Excel" if args.excel else "APROBADO: suite completa Python y JavaScript")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print("BLOQUEADO: fallaron los controles. No publicar.", file=sys.stderr)
        raise SystemExit(error.returncode)
