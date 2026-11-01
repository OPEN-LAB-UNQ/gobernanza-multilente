"""Ningún texto que lee una persona escribe la forma abreviada «señal(es)», «hoja(s)», «fila(s)».

Los cursantes la marcaron como jerga y descuido. Se corrigió a mano varias veces y volvió a
aparecer: esta prueba la busca donde vive, en los literales de texto, para que no vuelva.
"""
import re
import tokenize
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ABREVIADA = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]\(s\)")
PYTHON = ["services", "routers", "core"]
EXCEPCIONES = {
    # Reparación de descripciones ya emitidas: reconocen la forma vieja, no la escriben.
    ("services/reportes/markdown.py", "retrocesos en 2 serie(s) acumuladas"),
    ("services/reportes/markdown.py", "1 paso(s)"),
    ("services/reportes/markdown.py", r"retrocesos en (?:\d+ series?|\d+ serie\(s\)|dos series) acumuladas"),
}


def _literales_python(ruta: Path):
    with ruta.open("rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type == tokenize.STRING:
                yield tok.start[0], tok.string


def test_ningun_literal_de_python_usa_la_forma_abreviada():
    encontrados = []
    for carpeta in PYTHON:
        for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
            if "__pycache__" in ruta.parts:
                continue
            relativa = str(ruta.relative_to(RAIZ)).replace("\\", "/")
            for linea, literal in _literales_python(ruta):
                if not ABREVIADA.search(literal):
                    continue
                if any(relativa == r and clave in literal for r, clave in EXCEPCIONES):
                    continue
                encontrados.append(f"{relativa}:{linea}: {literal[:90]}")
    assert not encontrados, "Usar services.plural.contar en lugar de la forma abreviada:\n" + "\n".join(encontrados)


def test_ningun_texto_de_la_pantalla_usa_la_forma_abreviada():
    encontrados = []
    for ruta in sorted((RAIZ / "static").glob("*.js")):
        texto = ruta.read_text(encoding="utf-8")
        # Sólo lo que es una palabra suelta: «hoja(s)» en un texto, no una llamada como f(s).
        for m in re.finditer(r"(?:^|[\s>·])([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\(s\)", texto):
            linea = texto[:m.start()].count("\n") + 1
            encontrados.append(f"static/{ruta.name}:{linea}: {m.group(0).strip()}")
    assert not encontrados, "Usar contar() en lugar de la forma abreviada:\n" + "\n".join(encontrados)


def test_el_html_tampoco():
    encontrados = []
    for ruta in sorted((RAIZ / "static").glob("*.html")):
        texto = ruta.read_text(encoding="utf-8")
        for m in ABREVIADA.finditer(texto):
            linea = texto[:m.start()].count("\n") + 1
            encontrados.append(f"static/{ruta.name}:{linea}")
    assert not encontrados, "Escribir el plural completo:\n" + "\n".join(encontrados)
