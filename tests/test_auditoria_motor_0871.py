"""Hallazgos de la auditoría del motor corregidos en multilente-0.8.71."""
from __future__ import annotations

import pytest

from services import ambito, perfilado, triangulacion
from services.lentes import (
    ajedrecista,
    aplicar_conciliador,
    conciliador,
    cronista,
    matematico,
    orquesta,
    radiologo,
    rizoma,
)
from services.lentes.util import columna_etiqueta_fila
from services.sanitizacion import columna_sensible, redactar_texto_libre, sanear


@pytest.fixture
def organizacion():
    testigo = ambito.declarar(ambito.ORGANIZACION)
    yield
    ambito.restaurar(testigo)


@pytest.fixture
def publico():
    testigo = ambito.declarar(ambito.PUBLICO)
    yield
    ambito.restaurar(testigo)


# 1. Privacidad -------------------------------------------------------------

PERSONAS = ["Agente", "Agentes", "Empleado", "Empleados", "Titular", "Titulares", "Paciente", "Pacientes",
            "Docente", "Docentes", "Socio", "Socios", "Afiliado", "Afiliados", "Alumno", "Alumnos",
            "Destinatario", "Destinatarios", "Contacto", "Contactos"]


@pytest.mark.parametrize("nombre", PERSONAS)
def test_columna_de_persona_con_texto_se_excluye(nombre):
    assert columna_sensible(nombre, ["Juan Pérez", "María Gómez"])


@pytest.mark.parametrize("nombre", ["Agentes", "Pacientes atendidos", "Docentes", "Socios activos", "Cantidad de alumnos"])
def test_columna_de_persona_con_cifras_se_conserva(nombre):
    assert not columna_sensible(nombre, [120, 135, 150])


def test_agentes_solo_vale_con_valores_numericos():
    assert not columna_sensible("agentes", [10, 12])
    assert columna_sensible("agentes", ["Juan Pérez", "Ana Ruiz"])


@pytest.mark.parametrize("texto,marca", [
    ("DNI 12.345.678", "[DNI_REDACTADO]"),
    ("Documento: 30.123.456", "[DNI_REDACTADO]"),
    ("dni nro 12345678", "[DNI_REDACTADO]"),
    ("DNI n° 12345678", "[DNI_REDACTADO]"),
    ("CUIT del titular 20.12345678.6", "[CUIT_REDACTADO]"),
    ("referencia 20 12345678 6 en el legajo", "[CUIT_REDACTADO]"),
    ("cargado con 20123456786 por error", "[CUIT_REDACTADO]"),
    ("llamar al +54 9 11 4555 1234", "[TELEFONO_REDACTADO]"),
    ("llamar al 011 4555-1234", "[TELEFONO_REDACTADO]"),
    ("llamar al 4555-1234 por la tarde", "[TELEFONO_REDACTADO]"),
])
def test_pii_en_texto_libre_se_enmascara(texto, marca):
    assert marca in redactar_texto_libre(texto)


@pytest.mark.parametrize("texto", [
    "monto 20123456789",  # 11 cifras con dígito verificador inválido: es un monto
    "período 2019-2020", "serie 2001-2020", "ISO 9001-2015", "año 2024",
    "Partida 11-001-0001", "SAF 325-1234-5678", "Resolución 1234-5678-2024",
    "monto 1.234.567", "Total 30.123.456.789", "EX-2024-12345678-APN-DGA",
])
def test_codigos_anios_montos_y_rangos_no_se_enmascaran(texto):
    assert redactar_texto_libre(texto) == texto


def test_rotulo_de_persona_nunca_es_rotulo_de_fila():
    datos = [{"Agente": f"Persona {i}", "Monto": 100 + i} for i in range(4)]
    assert columna_etiqueta_fila(datos) != "Agente"


def test_nombre_y_dni_no_llegan_al_prompt_del_llm(publico):
    crudo = [
        {"Agente": "Juan Pérez", "Observación": "Contactar a Juan Pérez, DNI 12.345.678, tel 011 4555-1234",
         "Monto": 100 + i, "Devengado": 10 * i}
        for i in range(6)
    ]
    crudo[3]["Devengado"] = -500
    datos, reporte = sanear(crudo)
    assert "Agente" in reporte["columnas_excluidas"]
    hallazgos = [{**h, "lente": "ajedrecista"} for h in ajedrecista.imposibilidad(datos)]
    hallazgos += [{**h, "lente": "cronista"} for h in cronista.analizar(datos)]
    hallazgos += [{**h, "lente": "orquesta"} for h in orquesta.analizar(datos, [])]
    hallazgos += [{**h, "lente": "rizoma"} for h in rizoma.analizar(datos)]
    hallazgos += [{**h, "lente": "matematico"} for h in matematico.analizar(datos)]
    hallazgos = aplicar_conciliador(hallazgos, conciliador.analizar(datos, hallazgos))
    assert hallazgos, "el negativo en Devengado debe seguir detectándose"
    prompt = triangulacion._prompt_usuario({"dominio": "presupuestario", "periodo": "2024"}, hallazgos)
    for dato in ("Juan", "Pérez", "12.345.678", "4555"):
        assert dato not in prompt


# 2. Total de filas con columna temporal constante ----------------------------

def test_total_de_filas_con_columna_ejercicio_constante():
    datos = [
        {"Concepto": "Sueldos", "Presupuesto": 100, "Real": 90, "Ejercicio": 2024},
        {"Concepto": "Insumos", "Presupuesto": 200, "Real": 210, "Ejercicio": 2024},
        {"Concepto": "Servicios", "Presupuesto": 300, "Real": 280, "Ejercicio": 2024},
        {"Concepto": "Total", "Presupuesto": 600, "Real": 700, "Ejercicio": 2024},
    ]
    hallazgos = [h for h in ajedrecista.imposibilidad(datos) if h["evidencia"].get("regla") == "total_de_filas_no_cierra"]
    assert len(hallazgos) == 1
    assert hallazgos[0]["evidencia"]["columna"] == "Real"


# 3. Roles de columna por palabra completa ------------------------------------

@pytest.mark.parametrize("nombre", ["Recursos humanos", "Gasto mano de obra", "Transporte", "Daños", "Comestibles"])
def test_no_son_temporales(nombre):
    assert perfilado.inferir_rol(nombre, [1.5, 2, 3]) != "temporal"


@pytest.mark.parametrize("nombre", ["Personal", "Gasto en personal", "Personal ocupado", "Número de casos", "Documentos tramitados"])
def test_no_son_identificadores(nombre):
    assert perfilado.inferir_rol(nombre, [10, 20, 30]) != "identificador"


@pytest.mark.parametrize("nombre", ["Cantidad de unidades vendidas", "Proyectos aprobados", "Centros de salud"])
def test_conteos_numericos_no_son_dimension(nombre):
    assert perfilado.inferir_rol(nombre, [10, 20, 30]) != "dimension"


@pytest.mark.parametrize("nombre,valores,rol", [
    ("Ejercicio", [2024], "temporal"), ("Mes", ["enero"], "temporal"), ("Personas", ["Juan"], "identificador"),
    ("Número de expediente", [1, 2], "identificador"), ("Programa", [16, 17], "dimension"),
])
def test_roles_que_se_mantienen(nombre, valores, rol):
    assert perfilado.inferir_rol(nombre, valores) == rol


def test_negativo_en_gasto_en_personal_es_hallazgo(publico):
    datos = [{"Programa": f"P{i}", "Gasto en personal": v} for i, v in enumerate([100, 120, -50, 130, 110])]
    reglas = [h["evidencia"].get("regla") for h in ajedrecista.imposibilidad(datos)]
    assert "valor_negativo_en_magnitud_no_negativa" in reglas


def test_gasto_entero_en_negativo_en_organizacion_es_convencion(organizacion):
    datos = [{"Rubro": f"R{i}", "Gasto": v} for i, v in enumerate([-100, -120, -50, -130])]
    reglas = [h["evidencia"].get("regla") for h in ajedrecista.imposibilidad(datos)]
    assert "valor_negativo_en_magnitud_no_negativa" not in reglas


# 4. Conciliador: sólo modula con pistas reales -------------------------------

def _imposibilidad_presupuestaria():
    return {"lente": "ajedrecista", "modo": "imposibilidad", "severidad": "alta",
            "descripcion": "El devengado supera al crédito vigente en el total.", "evidencia": {"filas": [0]}}


def test_conciliador_no_baja_severidad_sin_artefacto_tecnico(publico):
    datos = [{"Programa": f"P{i}", "Credito vigente": 100 + i, "Devengado": 90 + i, "Pagado": 80 + i} for i in range(5)]
    crudos = [_imposibilidad_presupuestaria()]
    resultado = aplicar_conciliador(crudos, conciliador.analizar(datos, crudos))
    assert resultado[0]["severidad"] == "alta"
    assert "contexto_tecnico" not in (resultado[0].get("limites") or {})


def test_conciliador_no_usa_vocabulario_presupuestario_en_organizacion(organizacion):
    datos = [{"Rubro": f"R{i}", "nota": "dato preliminar sujeto a revisión", "Presupuesto": 100 + i, "Real": 90 + i, "Otro": i}
             for i in range(5)]
    crudos = [_imposibilidad_presupuestaria()]
    resultado = aplicar_conciliador(crudos, conciliador.analizar(datos, crudos))
    assert resultado[0]["severidad"] == "alta"


# 5. «Presupuesto» como crédito vigente en el ámbito público ------------------

def test_presupuesto_simple_es_credito_vigente_en_publico(publico):
    datos = [
        {"Programa": "Salud", "Presupuesto": 1000, "Ejecutado": 900},
        {"Programa": "Educación", "Presupuesto": 2000, "Ejecutado": 2600},
        {"Programa": "Obras", "Presupuesto": 500, "Ejecutado": 450},
    ]
    reglas = [h["evidencia"].get("regla") for h in ajedrecista.imposibilidad(datos)]
    assert "devengado_supera_vigente" in reglas


# 6. Radiólogo: pocos casos casi iguales --------------------------------------

def _banco(valores):
    periodos = ["2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01"]
    return [{"periodo": p, "datos": [{"periodo": p, "credito_devengado": v}]} for p, v in zip(periodos, valores)]


def test_radiologo_no_alarma_por_un_tres_por_ciento():
    banco = _banco([1000.0, 1001.0, 999.0, 1000.0])
    datos = [{"periodo": "2026-03", "credito_devengado": 1030.0}]
    assert radiologo.analizar("presupuestario", "2026-03", datos, banco) == []


def test_radiologo_con_pocos_casos_no_da_alta():
    banco = _banco([1000.0, 1001.0, 999.0, 1000.0])
    datos = [{"periodo": "2026-03", "credito_devengado": 2000.0}]
    hallazgos = radiologo.analizar("presupuestario", "2026-03", datos, banco)
    assert hallazgos and hallazgos[0]["severidad"] == "media"


# 7. Orquesta: qué es un porcentaje -------------------------------------------

@pytest.mark.parametrize("col,valores,esperado", [
    ("produccion", [40, 55, 80], False),
    ("monto_ejecutado", [45.5, 60.2], False),
    ("indicador", [45.5, 60.2], True),
    ("tasa_cobertura", [120, 130], True),
    ("participacion", [10, 20], True),
    ("avance_fisico", [10, 20, 35], True),
])
def test_orquesta_es_porcentaje(col, valores, esperado):
    assert orquesta._es_porcentaje(col, valores) is esperado


# 8. Cronista: serie plana con un ×10 -----------------------------------------

def test_cronista_detecta_salto_en_serie_plana():
    datos = [{"periodo": f"2024-{m:02d}", "monto": 100.0} for m in range(1, 8)]
    datos.append({"periodo": "2024-08", "monto": 1000.0})
    hallazgos = [h for h in cronista.analizar(datos) if h["modo"] == "corte_temporal"]
    assert hallazgos


# 9. Total verificado: «% del total» no es una parte -------------------------

def test_total_verificado_excluye_porcentaje_del_total():
    datos = [
        {"Rubro": "A", "Uno": 10, "Dos": 20, "Total": 30, "% del total": 10.0},
        {"Rubro": "B", "Uno": 30, "Dos": 40, "Total": 70, "% del total": 23.3},
        {"Rubro": "C", "Uno": 50, "Dos": 50, "Total": 100, "% del total": 33.3},
        {"Rubro": "D", "Uno": 40, "Dos": 40, "Total": 100, "% del total": 33.3},
    ]
    numericas = perfilado.columnas_numericas(datos)
    total, partes = ajedrecista._total_verificado(datos, numericas)
    assert total == "Total" and "% del total" not in partes
    reglas = [h["evidencia"].get("regla") for h in ajedrecista.imposibilidad(datos)]
    assert "partes_no_suman_total" in reglas
