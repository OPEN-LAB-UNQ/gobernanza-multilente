from copy import deepcopy

from services.semantica_excel import markdown, presentar_cobertura, resumir


def test_leyenda_historica_no_indica_que_un_csv_es_excel_ni_modifica_registro():
    original = {
        "exploracion_semantica": {
            "estado": "no_evaluada",
            "titulo_estado": "Exploración no iniciada",
            "limites": "Contexto no disponible en esta carga histórica. Volver a cargar el Excel para explorar su contenido semántico.",
            "hallazgos": [],
            "modelos": [],
        }
    }
    before = deepcopy(original)
    result = presentar_cobertura(original)
    assert original == before
    assert "Volver a cargar el Excel" not in markdown(result["exploracion_semantica"])
    assert "CSV" in result["exploracion_semantica"]["limites"]
    assert result["exploracion_semantica"]["estado"] == "no_evaluada"


def test_contexto_nuevo_ausente_y_contexto_valido_se_distinguen():
    empty = resumir({}, [])
    assert "CSV" in empty["limites"] and empty["estado"] == "no_evaluada"
    valid = {
        "exploracion_semantica": {
            "estado": "evaluada",
            "titulo_estado": "Exploración completada",
            "limites": "Cobertura total registrada",
            "hallazgos": [{"id": "real"}],
        }
    }
    assert presentar_cobertura(valid) == valid
