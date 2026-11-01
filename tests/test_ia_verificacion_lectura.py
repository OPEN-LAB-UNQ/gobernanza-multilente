"""4. Lecturas libres: cifras, años y dirección de cambio contra la evidencia enviada;
atribución por modelo y línea de estado."""
from __future__ import annotations

from services import triangulacion
from services import triangulacion_validacion as tv
from tests.test_ia_datos_eval import HALLAZGOS_264, HALLAZGOS_265, LECTURAS_265, interpretacion, lectura


def test_direccion_invertida_se_descarta_265():
    c = triangulacion.consolidar(HALLAZGOS_265, [interpretacion(m, LECTURAS_265[m]) for m in ("deepseek", "llama")])
    assert [d["modelo"] for d in c["lecturas_descartadas"]] == ["llama"]
    retirada = c["lecturas_descartadas"][0]["afirmaciones_retiradas"][0]
    assert "88 a 52" in retirada["texto"] and "invertida" in retirada["motivos"][0]
    deepseek = c["hallazgos_singulares"][0]
    assert deepseek["modelo"] == "deepseek" and deepseek["estado_lectura"] == "incorporada"


def test_oracion_con_cifra_o_anio_sin_respaldo_se_retira_y_se_marca():
    texto = ("El valor 0.452 de 2021 (idx 0) rompe la escala de la serie 1500. "
             "En 2015 el mismo rubro había caído a 987654, lo que confirma el patrón.")
    c = triangulacion.consolidar(HALLAZGOS_264, [interpretacion("gpt", lectura(texto, [0]))])
    s = c["hallazgos_singulares"][0]
    assert s["estado_lectura"] == "marcada"
    assert "2015" not in s["lectura"] and "987654" not in s["lectura"]
    assert "Se retiró 1 afirmación" in s["lectura"]
    motivos = " ".join(s["afirmaciones_retiradas"][0]["motivos"])
    assert "2015" in motivos and "987654" in motivos


def test_describir_baja_cuando_las_cifras_suben_se_retira():
    v = tv.validar_lectura(lectura("La serie de pendientes (idx 1) cae de 52 a 88 en febrero.", [1]),
                           [{"idx": 1, **HALLAZGOS_265[1]}], [1], 2)
    assert v["estado"] == "descartada"


def test_cifras_derivadas_y_redondeadas_no_se_retiran():
    texto = "La serie 1500 (idx 0) pasa de 340 a 0,45 y vuelve a 620; el desvío es de unas 1062 veces y la suba posterior es de 280."
    v = tv.validar_lectura(lectura(texto, [0]), [{"idx": 0, **HALLAZGOS_264[0]}], [0], 2)
    assert v["estado"] == "incorporada", v


def test_atribucion_por_modelo_y_senales_leidas_x_de_y():
    its = [
        interpretacion("gpt", lectura("El valor 0.452 de 2021 (idx 0) se aparta de sus vecinos.", [0]), [0], rol="principal"),
    ]
    c = triangulacion.consolidar(HALLAZGOS_264, its)
    s = c["hallazgos_singulares"][0]
    assert s["lectura_atribuida"].startswith("gpt (principal): ")
    assert s["senales_recibidas"] == 1
    assert c["cobertura_lectura"] == {"senales_leidas": 1, "senales_totales": 2}
    assert "respondieron gpt (principal)" in c["linea_estado"]
    assert "Señales leídas por algún modelo: 1 de 2." in c["linea_estado"]
