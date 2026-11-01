"""Reglas presupuestarias 0.9.0: compromiso y crédito inicial + modificaciones = vigente."""
from services.lentes import ajedrecista

PROGRAMAS = ["Programa 16", "Programa 17", "Programa 18", "Programa 19", "Programa 20", "Programa 21"]


def tabla(**cambios):
    filas = []
    for i, p in enumerate(PROGRAMAS):
        ini = 1000.0 + 100 * i
        mod = 50.0 * (i % 3) - 20
        vig = ini + mod
        fila = {"Programa": p, "Crédito inicial": ini, "Modificaciones": mod, "Crédito vigente": vig,
                "Comprometido": round(vig * 0.9, 1), "Devengado": round(vig * 0.8, 1), "Pagado": round(vig * 0.7, 1)}
        fila.update(cambios.get(p, {}))
        filas.append(fila)
    return filas


def reglas(datos):
    return {h["evidencia"].get("regla"): h for h in ajedrecista.analizar(datos, None)}


def test_tabla_coherente_no_da_senales_presupuestarias():
    r = reglas(tabla())
    assert not r.keys() & {"devengado_supera_comprometido", "comprometido_supera_vigente",
                           "credito_vigente_no_cierra_con_modificaciones", "devengado_supera_vigente"}


def test_devengado_mayor_que_comprometido():
    r = reglas(tabla(**{"Programa 18": {"Devengado": 1300.0}}))
    h = r["devengado_supera_comprometido"]
    assert h["evidencia"]["filas"] == [2] and h["severidad"] == "alta"


def test_comprometido_mayor_que_vigente():
    r = reglas(tabla(**{"Programa 20": {"Comprometido": 1500.0}}))
    assert r["comprometido_supera_vigente"]["evidencia"]["filas"] == [4]


def test_vigente_que_no_cierra_con_inicial_mas_modificaciones():
    r = reglas(tabla(**{"Programa 17": {"Crédito vigente": 1200.0}}))
    h = r["credito_vigente_no_cierra_con_modificaciones"]
    assert h["evidencia"]["filas"] == [1] and h["severidad"] == "alta"
    assert "1100 + 30 = 1130" in h["descripcion"]


def test_redondeo_no_es_senal():
    r = reglas(tabla(**{"Programa 17": {"Crédito inicial": 1100.4, "Modificaciones": 29.4, "Crédito vigente": 1130.0}}))
    assert "credito_vigente_no_cierra_con_modificaciones" not in r


def test_ejecutado_con_modificaciones_sigue_siendo_devengado():
    from services import perfilado
    datos = [{"Programa": p, "Crédito vigente": 100.0, "Ejecutado con modificaciones": 80.0} for p in PROGRAMAS]
    etapas = perfilado.columnas_etapas_presupuesto(perfilado.perfilar(datos))
    assert etapas.get("devengado") == "Ejecutado con modificaciones" and "modificaciones" not in etapas
