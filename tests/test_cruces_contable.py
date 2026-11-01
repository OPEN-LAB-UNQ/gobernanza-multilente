"""Regla contable interdocumental de Orquesta: defectos K6–K9 de la evaluación del 2026-10-03.

El archivo de origen se inyecta en cada fila (como k_inyectado.py): mide la regla, no la carga.
"""
from services.lentes import orquesta

META = {"periodo": "2024", "entidad": "Cooperativa Ejemplo", "moneda": "ARS", "unidad": "pesos", "escala": "miles"}


def filas(archivo, conceptos, columnas=("importe",), meta=META):
    out = []
    for concepto, *valores in conceptos:
        out.append({"archivo_origen": archivo, "concepto": concepto, **dict(zip(columnas, valores)), **meta})
    return out


def reglas(datos):
    return {h["evidencia"]["regla"]: h for h in orquesta._coherencia_interdocumental(datos)}


def test_k6_resultado_del_ejercicio_no_toma_el_del_ejercicio_anterior():
    datos = filas("balance_situacion_patrimonial_2024.csv", [
        ("Caja y bancos", 1520), ("Resultados no asignados", 800),
        ("Resultado del ejercicio anterior", 1210), ("Resultado del ejercicio", 1590),
    ]) + filas("estado_de_resultados_2024.csv", [("Ventas", 18200), ("Resultado neto del ejercicio", 1590)])
    assert "resultado_concilia_con_patrimonio" not in reglas(datos)
    # Y si el del ejercicio difiere, la señal compara el concepto correcto.
    datos[3]["importe"] = 1350
    h = reglas(datos)["resultado_concilia_con_patrimonio"]
    assert h["evidencia"]["conceptos"]["balance_situacion_patrimonial_2024.csv"] == "resultado del ejercicio"
    assert h["evidencia"]["valores"]["balance_situacion_patrimonial_2024.csv"] == 1350


def test_k7_estado_comparativo_usa_la_columna_del_periodo():
    cols = ("2023", "2024")
    balance = filas("balance_situacion_patrimonial_2024.csv", [("Caja y bancos", 1100, 1520), ("Resultado del ejercicio", 1210, 1590)], cols)
    resultados = filas("estado_de_resultados_2024.csv", [("Ventas", 15000, 18200), ("Resultado neto del ejercicio", 1210, 1700)], cols)
    h = reglas(balance + resultados)["resultado_concilia_con_patrimonio"]
    assert h["evidencia"]["columnas"] == ["2024", "2024"]
    assert h["evidencia"]["valores"]["estado_de_resultados_2024.csv"] == 1700


def test_k8_tipo_de_estado_por_contenido_y_no_por_nombre_de_archivo():
    datos = filas("ESP_2024.csv", [("Caja y bancos", 1520), ("Resultado del ejercicio", 1350)]) + filas(
        "ER_2024.csv", [("Ventas", 18200), ("Resultado neto del ejercicio", 1590)])
    assert "resultado_concilia_con_patrimonio" in reglas(datos)
    sin_nombre = [{**f, "archivo_origen": f["archivo_origen"].replace("ESP", "anexo1").replace("ER", "anexo2")} for f in datos]
    assert "resultado_concilia_con_patrimonio" in reglas(sin_nombre)


def test_k9_concepto_por_rotulo_y_no_por_textos_concatenados():
    balance = filas("balance_situacion_patrimonial_2024.csv", [
        ("Efectivo restringido (garantías)", 300), ("Efectivo y equivalentes", 1520), ("Resultado del ejercicio", 1590)])
    flujo = filas("estado_flujo_de_efectivo_2024.csv", [
        ("Saldo inicial de efectivo", 1100), ("Flujo neto operativo", 420), ("Saldo final de efectivo", 1520)])
    assert orquesta._buscar_concepto(balance, orquesta._EFECTIVO_PATRIMONIAL, orquesta._EFECTIVO_EXCLUIDO)[0] == 1520
    assert "efectivo_final_concilia_con_estado_patrimonial" not in reglas(balance + flujo)
    flujo[2]["importe"] = 1600
    h = reglas(balance + flujo)["efectivo_final_concilia_con_estado_patrimonial"]
    assert h["evidencia"]["conceptos"]["balance_situacion_patrimonial_2024.csv"] == "efectivo y equivalentes"
