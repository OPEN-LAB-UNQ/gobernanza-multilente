"""La matriz acordada debe ser única, completa y consumible por el producto."""
from services.lens_matrix import LENS_BY_ID, LENS_MATRIX, lens_profiles_for_control


def test_matriz_contiene_las_siete_lentes_sin_duplicados():
    ids = [item["id"] for item in LENS_MATRIX]
    assert len(ids) == 7
    assert len(set(ids)) == 7
    assert set(ids) == {
        "ajedrecista", "matematico", "cronista", "orquesta",
        "radiologo", "rizoma", "conciliador",
    }
    for item in LENS_MATRIX:
        assert item["pregunta_central"]
        assert len(item["preguntas"]) >= 5
        assert item["evidencia_minima"]
        assert set(item["criterios"]) == {"conforme", "observado", "no_evaluable"}
        assert item["limites"]


def test_fronteras_acordadas_quedan_explicitas():
    ajedrecista = LENS_BY_ID["ajedrecista"]
    matematico = LENS_BY_ID["matematico"]
    radiologo = LENS_BY_ID["radiologo"]
    orquesta = LENS_BY_ID["orquesta"]
    assert "estadística" in " ".join(ajedrecista["limites"])
    assert any("Benford" in pregunta for pregunta in matematico["preguntas"])
    assert any("preinformes" in pregunta for pregunta in radiologo["preguntas"])
    assert "historial interno" in " ".join(radiologo["limites"])
    assert any("archivos" in pregunta for pregunta in orquesta["preguntas"])


def test_control_interdocumental_b1_incluye_tres_lentes_complementarias():
    perfiles = lens_profiles_for_control("B1-07", "orquesta")
    assert [perfil["id"] for perfil in perfiles] == ["orquesta", "radiologo", "rizoma"]
