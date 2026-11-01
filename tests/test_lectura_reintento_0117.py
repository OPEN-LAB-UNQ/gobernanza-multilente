"""0.10.17: reintento ante fallas pasajeras de una lectora y analogía entre cuadros con los mismos encabezados."""
from services import interpretacion_previa as ip
from services import lector_mapa


def _cuadro(hoja, rotulo, eje_votos, error=None):
    lecturas = {f"m{k}": {"eje": e, "error": None} for k, e in enumerate(eje_votos)}
    if error:
        lecturas["gemini"] = {"error": error}
    return {"hoja": hoja, "columnas": ["2001", "2002", "2003", rotulo], "lecturas": lecturas,
            "propuesta": {"institucion": "organismo_publico", "regimen": "publico", "tipo": "presupuesto",
                          "eje": ip._mayoria(eje_votos, "no_determinado")}}


def test_cuadro_sin_acuerdo_toma_lo_que_acordaron_sus_iguales_si_una_lectora_lo_propuso():
    iguales = [_cuadro(f"P{k}", "Indicador", ["serie_columnas"] * 3) for k in range(3)]
    dudoso = _cuadro("P9", "Clase", ["ninguno", "serie_columnas"], error="El proveedor no completó la lectura")
    ip._por_analogia([*iguales, dudoso])
    assert dudoso["propuesta"]["eje"] == "serie_columnas"
    assert dudoso["por_analogia"] == {"eje": {"valor": "serie_columnas", "cuadros": 3}}
    assert all("por_analogia" not in u for u in iguales)


def test_sin_un_voto_propio_o_con_encabezados_distintos_no_se_completa():
    iguales = [_cuadro(f"P{k}", "Indicador", ["serie_columnas"] * 3) for k in range(3)]
    sin_voto = _cuadro("P8", "Clase", ["ninguno", "serie_filas"])
    otro = _cuadro("P9", "Clase", ["ninguno", "serie_columnas"])
    otro["columnas"] = ["Rubro", "Monto", "Fecha", "Clase"]
    ip._por_analogia([*iguales, sin_voto, otro])
    assert sin_voto["propuesta"]["eje"] == otro["propuesta"]["eje"] == "no_determinado"


def test_una_falla_pasajera_se_reintenta_con_el_proveedor_real(monkeypatch):
    llamadas = {"gemini": 0}

    def llamar(proveedor, prompt):
        llamadas[proveedor] += 1
        if llamadas[proveedor] == 1:
            raise TimeoutError("timed out")
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(lector_mapa, "llamar", llamar)
    monkeypatch.setattr(ip, "ESPERAS_REINTENTO", (0, 0))
    r = ip._leer_cuadro("p", {}, set(), lector_mapa.llamar, ["gemini"])
    assert llamadas["gemini"] == 3
    assert r["gemini"]["error"] == "El proveedor no completó la lectura (límite de uso del proveedor)"
    assert r["gemini"]["intentos"] == 3


def test_con_una_funcion_de_prueba_no_se_reintenta():
    llamadas = []

    def falla(proveedor, prompt):
        llamadas.append(proveedor)
        raise RuntimeError("x")

    r = ip._leer_cuadro("p", {}, set(), falla, ["gpt"])
    assert llamadas == ["gpt"] and r["gpt"]["error"] == "El proveedor no completó la lectura"
