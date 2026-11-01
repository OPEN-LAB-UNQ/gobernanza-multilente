"""El motor debe superar mutaciones nuevas generadas a partir de datos conocidos."""

import json

from scripts.ensayo_controles import casos, ejecutar, evaluar


def test_campana_generada_sin_falsas_alertas(tmp_path):
    out = tmp_path / "campana"
    assert ejecutar(101, 2, out) == 0
    r = json.loads((out / "resumen.json").read_text())
    assert r["casos"] == 64 and r["mutaciones"] == 60
    assert r["detectadas"] == r["mutaciones"] and r["casos_validos_con_alertas"] == 0


def test_evaluador_rechaza_omision_y_falso_positivo():
    verdad = [dict(regla="vacio_interior", hoja="H", celda="D4", localizacion="directa")]
    assert evaluar([], verdad)[1] == ["Mutación no recuperada"]
    h = {"evidencia": dict(naturaleza="control", regla="vacio_interior", hoja="H", celda="D4")}
    assert evaluar([h], [])[1]
    assert not evaluar([h], verdad)[1]
    assert evaluar([h], [{**verdad[0], "celda": "E4"}])[1]


def test_falla_conserva_archivo_y_verdad_independiente(tmp_path, monkeypatch):
    import scripts.ensayo_controles as modulo

    monkeypatch.setattr(modulo, "analizar", lambda data: ([], {"hojas": 1, "cuadros": 1, "filas": 4}))
    out = tmp_path / "fallida"
    assert ejecutar(5, 1, out) == 1
    fallas = list((out / "fallos").glob("*/evidencia.json"))
    assert len(fallas) == 18
    for path in fallas:
        assert path.with_name("original.xlsx").is_file() and path.with_name("variante.xlsx").is_file()
        assert json.loads(path.read_text())["verdad"]


def test_semilla_reproduce_verdad_y_varia_las_posiciones():
    def verdades(seed):
        return [truth for _, _, _, truth in casos(seed, False)]

    assert verdades(7) == verdades(7)
    assert verdades(7) != verdades(8)


def test_textos_regionales_con_error_conservan_cobertura_y_celda():
    from scripts.ensayo_controles import analizar, bytes_libro, libro

    w, mapa = libro(33)
    s = w.active
    for fila in mapa["celdas"]:
        for c in fila:
            s[c] = str(s[c].value).replace(".", ",")
    c = mapa["celdas"][0][5]
    s[c] = str(float(s[c].value.replace(",", ".")) * 10).replace(".", ",")
    hs, cobertura = analizar(bytes_libro(w))
    assert cobertura == {"filas": 4, "hojas": 1, "cuadros": 1}
    assert any(h["evidencia"]["regla"] == "pico_aislado" and h["evidencia"]["celda"] == c for h in hs)


def test_textos_y_fechas_no_son_cuadros_numericos():
    from openpyxl import Workbook

    from scripts.ensayo_controles import analizar, bytes_libro
    from services.excel_cobertura import _es_numero_tabular

    assert all(not _es_numero_tabular(v) for v in ("20/09/2026", "20-09-2026", "Informe 123", "NA", True))
    assert all(_es_numero_tabular(v) for v in ("1.234,56", "1234,56", "1,234.56", "-1234,56", 0))
    w = Workbook()
    w.active.append(["Concepto", 2000, 2001, 2002, 2003])
    w.active.append(["Nota", "uno", "dos", "tres", "cuatro"])
    hs, c = analizar(bytes_libro(w))
    assert not hs and c["filas"] == 0


def test_formula_sin_cache_del_generador_conserva_el_valor_original():
    # Regresión (12/10/2026): el generador escribía «=100+200» sin ajustar el total; desde que el
    # motor evalúa fórmulas sin valor guardado, ese caso «válido» quedaba mal armado y la semilla
    # 1399810747 lo marcaba como error de escala, bloqueando el empaquetado.
    from scripts.ensayo_controles import analizar

    for semilla in (1399810747, 101, 102):
        for vertical in (False, True):
            variante = next(datos for tipo, _, datos, _ in casos(semilla, vertical) if tipo == "formula_sin_cache")
            hallazgos, _ = analizar(variante)
            assert [h for h in hallazgos if h["evidencia"].get("naturaleza") == "control"] == []
