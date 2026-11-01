"""La consulta declara qué columnas son códigos y eso tiene que cambiar el análisis."""

from types import SimpleNamespace

from services import columnas_declaradas as cd
from services import perfilado
from services.lentes import matematico
from services.reportes import markdown as m

CONSULTA = (
    "Archivo público de instituto de estadística con importaciones. Cada fila combina año, mes, posición arancelaria "
    "(NCM, código de 8 dígitos que puede aparecer sin el cero inicial) y país de origen (Porg, código "
    "numérico de instituto de estadística). Pnet es el peso neto en kg; FOB y CIF están en dólares. Los códigos NCM y de "
    "país son identificadores, no cantidades: no los sumes ni les asignes una descripción."
)
FILAS = [{"NCM": 85171200, "Porg": 203, "Pnet(kg)": 12.5, "FOB(USD)": 980.4}]


def test_reconoce_las_columnas_declaradas_con_su_fragmento():
    r = cd.detectar(CONSULTA, FILAS)
    assert r["columnas"] == ["NCM", "Porg"]
    assert "identificadores" in r["motivos"]["NCM"]
    assert "código numérico" in r["motivos"]["Porg"]


def test_no_inventa_restricciones():
    assert cd.detectar("Quiero verificar que el total cierre en cada mes.", FILAS)["columnas"] == []
    # Nombrar la columna no alcanza: hace falta que la consulta la declare como código.
    assert cd.detectar("Revisar la evolución mensual de NCM y de FOB(USD).", FILAS)["columnas"] == []
    # Una columna declarada que no está en los datos no se inventa.
    assert cd.detectar("La columna Expediente es un identificador.", FILAS)["columnas"] == []
    assert cd.detectar(CONSULTA, [])["columnas"] == []


def test_la_declaracion_saca_la_columna_de_los_controles_numericos():
    datos = [{"NCM": 85171200 + i, "FOB(USD)": 10.5 * (i + 1)} for i in range(60)]
    assert "NCM" in perfilado.columnas_numericas(datos)
    testigo = perfilado.declarar_identificadores(["NCM"])
    try:
        assert perfilado.columnas_numericas(datos) == ["FOB(USD)"]
    finally:
        perfilado.restaurar_identificadores(testigo)
    assert "NCM" in perfilado.columnas_numericas(datos)


def test_la_declaracion_pesa_aunque_los_valores_parezcan_cantidades():
    """Una columna con decimales y varias escalas pasa el filtro por valores; la declaración manda."""
    import random

    random.seed(5)
    datos = [{"padron": round(random.uniform(480, 520), 2)} for _ in range(200)]
    regla = "primer_digito_no_conforme_benford"
    assert [h for h in matematico.analizar(datos) if h["evidencia"].get("regla") == regla]
    testigo = perfilado.declarar_identificadores(["padron"])
    try:
        assert not [h for h in matematico.analizar(datos) if h["evidencia"].get("regla") == regla]
    finally:
        perfilado.restaurar_identificadores(testigo)


def test_el_reporte_declara_la_restriccion_aplicada():
    informe = SimpleNamespace(
        saneamiento={"orientacion_analisis": "Revisar importaciones"},
        devolucion=SimpleNamespace(
            cobertura={"restricciones_declaradas": {"columnas": ["NCM", "Porg"], "motivos": {}}, "lentes": []}
        ),
    )
    salida = m._encabezar_consulta("# Reporte\n## Cómo leer\nDetalle", informe, [object()])
    assert "Restricción declarada" in salida and "«NCM»" in salida
    assert salida.index("Restricción declarada") < salida.index("## Cómo leer")


def test_sin_restricciones_no_aparece_la_linea():
    informe = SimpleNamespace(saneamiento={}, devolucion=SimpleNamespace(cobertura={"lentes": []}))
    assert "Restricción declarada" not in m._encabezar_consulta("# R\nD", informe, [])
