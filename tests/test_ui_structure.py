from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, _tag, attrs):
        element_id = dict(attrs).get("id")
        if element_id:
            self.ids.append(element_id)


def test_index_no_repite_ids_html():
    parser = _Ids()
    parser.feed(Path("static/index.html").read_text(encoding="utf-8"))
    repetidos = [element_id for element_id, total in Counter(parser.ids).items() if total > 1]
    assert repetidos == []


def test_estado_consulta_y_estado_proyecto_docente_son_elementos_distintos():
    html = Path("static/index.html").read_text(encoding="utf-8")
    js = Path("static/app.js").read_text(encoding="utf-8")
    assert html.count('id="proyecto-docente-estado"') == 1
    assert html.count('id="proyecto-docente-proyecto-estado"') == 1
    assert 'getElementById("proyecto-docente-proyecto-estado")' in js


def test_interfaz_carga_y_muestra_matriz_canonica_de_lentes():
    js = Path("static/app.js").read_text(encoding="utf-8")
    assert 'apiFetch("/certificaciones/lentes")' in js
    assert "Ver preguntas y evidencia esperada" in js
    assert "renderGuiaLentesDesdeMatriz" in js
