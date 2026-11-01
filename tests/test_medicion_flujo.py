from scripts.medir_flujo_confirmado import clasificacion_confirmable, senal_en_celda


def test_medicion_no_autoaprueba_fallas_desacuerdos_ni_tipo_distinto_del_etiquetado():
    def propuesta(tipo="pagos", n=3):
        return {"interpretacion": {"cuadros": [{"propuesta": {"tipo": tipo}, "lecturas_validas": n}]}}
    assert clasificacion_confirmable(propuesta(), "pagos")
    assert not clasificacion_confirmable(propuesta(), "presupuesto")
    assert not clasificacion_confirmable(propuesta(n=1))
    assert not clasificacion_confirmable(propuesta("desconocido"))
    assert not clasificacion_confirmable({"interpretacion": {"cuadros": []}})


def test_medicion_exige_celda_y_hoja_y_no_puntua_rangos_amplios_como_deteccion_exacta():
    assert senal_en_celda([{"evidencia": {"hoja": "Hoja", "celda": "E20"}}], "Hoja", "E20")
    assert senal_en_celda([{"evidencia": {"ubicaciones_excel": ["Hoja!E20"]}}], "Hoja", "E20")
    assert not senal_en_celda([{"evidencia": {"hoja": "Otra", "celda": "E20"}}], "Hoja", "E20")
    assert not senal_en_celda([{"evidencia": {"ubicaciones_excel": ["Hoja!A1:Z99"]}}], "Hoja", "E20")
    assert senal_en_celda([], "Hoja", None) is None


def test_medicion_rechaza_base_no_aislada_antes_de_importar_aplicacion(tmp_path, monkeypatch):
    import sys

    import pytest

    from scripts.medir_flujo_confirmado import main
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario:prueba@localhost/produccion")
    monkeypatch.setattr(sys, "argv", ["medir", "--casos", str(tmp_path / "no-existe.json"),
        "--salida", str(tmp_path / "salida"), "--version-codigo", "no-leer-produccion"])
    with pytest.raises(SystemExit, match="base aislada"):
        main()
    assert not (tmp_path / "salida").exists()
