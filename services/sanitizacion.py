"""Filtro de alcance agregado.

El sistema trabaja exclusivamente con información agregada: nunca debe leer
proveedores, contratistas, adjudicatarios, personas, CUIT/CUIL, facturas o expedientes nominales, tal como
establece el documento rector. Esta capa se corre sobre todo informe antes de
guardarlo: excluye columnas que identifican actores o documentos individuales,
y redacta patrones de PII que puedan haber quedado en campos de texto libre.
La exclusión queda registrada junto al informe -- no es un descarte
silencioso, es trazable como cualquier otro paso del sistema.

Los patrones de redacción de valores sueltos (DNI, CUIT) exigen o bien el
formato inequívoco de CUIT con guiones, o bien una etiqueta explícita
("DNI", "CUIT", "CUIL", "documento", con o sin "nro"/"n°" y con o sin puntos)
pegada al número, o bien un CUIT de 11 cifras (con o sin puntos o espacios) cuyo
dígito verificador sea válido. Un número de 7 a 11
dígitos sin esa marca no se toca: en datos agregados de administración
pública es mucho más probable que sea un código de programa, una partida
presupuestaria o un monto que un documento de identidad, y redactarlo a
ciegas corrompe en silencio el dato agregado legítimo que este módulo
existe para proteger.
"""
from __future__ import annotations

import re
from typing import Any

COLUMNA_SENSIBLE_RE = re.compile(
    r"proveedor|contratista|adjudicatari[oa]|cliente|vendor|supplier|beneficiario|raz[oó]n[\s_]*social|"
    r"responsable|funcionario|(?:^|[_\s-])personas?(?:$|[_\s-])|nombre|apellido|"
    r"(?<![a-záéíóúñ])(?:cui[tl]|dni)s?(?![a-záéíóúñ])|"
    r"email|correo|tel[eé]fono|telefono|"
    r"(?:^|[_\s-])(?:comprobantes?|documentos?|expedientes?|facturas?)(?:$|[_\s-])",
    re.IGNORECASE,
)
# Rótulos que identifican a una persona aunque convivan con una palabra de
# conteo agregado ("nombre_agente", "DNI del agente"): se evalúan primero.
COLUMNA_NOMINAL_RE = re.compile(
    r"nombre|apellido|cuit|cuil|dni|e-?mail|correo|tel[eé]fono|celular|legajo|domicilio",
    re.IGNORECASE,
)
# "Nombre del indicador", "nombre del programa": el rótulo nombra una cosa, no a una persona.
NOMBRE_DE_COSA_RE = re.compile(
    r"nombre[\s_]*(?:del?|de[\s_]+la)?[\s_]*(?:indicador|programa|rubro|producto|"
    r"sector|concepto|meta|kpi|servicio|sucursal|categor[ií]a)",
    re.IGNORECASE,
)
# Conteos y montos sobre un conjunto de actores ("Clientes activos", "Cantidad de
# beneficiarios", "Deuda con proveedores", "Facturación"): son datos agregados.
ACTOR_AGREGADO_RE = re.compile(
    r"cantidad|\bcant\b|\bn[°º]|\bnro\b|n[uú]mero[\s_]+de|\btotal|activ[oa]s|nuev[oa]s|atendid[oa]s|"
    r"registrad[oa]s|alcanzad[oa]s|promedio|porcentaje|%|\btasa|"
    r"deudas?[\s_]+con|pagos?[\s_]+a|cuentas?[\s_]+(?:a|por)[\s_]+(?:cobrar|pagar)|acreedores|deudores|"
    r"facturaci[oó]n|facturad[oa]|facturas[\s_]+emitidas|"
    r"(?:[aá]rea|unidad|sector|gerencia|direcci[oó]n|dependencia)[\s_]+responsable",
    re.IGNORECASE,
)
# Un encabezado en plural con valores numéricos cuenta actores; no los identifica.
ACTOR_PLURAL_RE = re.compile(
    r"proveedores|clientes|beneficiari[oa]s|contratistas|adjudicatari[oa]s|personas|funcionari[oa]s|responsables|"
    r"expedientes|comprobantes|documentos|facturas",
    re.IGNORECASE,
)
COLUMNA_AGREGADA_PERMITIDA_RE = re.compile(
    r"personal_disponible|dotaci[oó]n|dotacion|cantidad_?personal|personal_?total|plantel",
    re.IGNORECASE,
)
COLUMNA_PERSONA_PLURAL_RE = re.compile(
    r"(?<![a-záéíóúñ])(?:agentes|emplead[oa]s|titulares|pacientes|docentes|soci[oa]s|"
    r"afiliad[oa]s|alumn[oa]s|destinatari[oa]s|contactos)(?![a-záéíóúñ])",
    re.IGNORECASE,
)
# Rótulos que nombran a una persona («Agente», «Empleados», «Titular», «Paciente»...).
# Valen sólo si sus valores son cifras («Agentes» = 120 es un conteo); con texto
# adentro son nombres de personas y la columna se excluye. Nunca se conservan por
# el rótulo solo.
COLUMNA_PERSONA_RE = re.compile(
    r"(?<![a-záéíóúñ])(?:agentes?|emplead[oa]s?|titular(?:es)?|pacientes?|docentes?|soci[oa]s?|"
    r"afiliad[oa]s?|alumn[oa]s?|destinatari[oa]s?|contactos?)(?![a-záéíóúñ])",
    re.IGNORECASE,
)
COLUMNA_TECNICA_PERMITIDA_RE = re.compile(
    r"^(?:extraccion_pdf|pagina_pdf|pagina_pdf_impresa|tabla_pdf|fila_tabla_pdf|archivo_origen|"
    r"paginas_documento|paginas_pdf_analizadas|limite_paginas_pdf|pdf_truncado_por_paginas|"
    r"tipo_documento|pagina|caracteres_extraidos|cantidad_numeros_detectados|muestra_numeros)$",
    re.IGNORECASE,
)

_SEP = r"[\s:.#-]{0,6}(?:(?:n(?:ro|[°ºo])|n[uú]m(?:ero)?)\.?)?[\s:.#-]{0,3}"

# Forma inequivoca de CUIT (con guiones) -- no necesita etiqueta porque ese
# formato de por si no coincide con un monto ni un codigo de programa.
_CUIT_CON_GUIONES_RE = re.compile(r"\b\d{2}-\d{8}-\d\b")
# CUIT/CUIL sin guiones, pero con la etiqueta pegada al lado.
_CUIT_ETIQUETADO_RE = re.compile(rf"(?i)\b(cuit|cuil)\b{_SEP}(\d{{2}}-?\d{{8}}-?\d|\d{{11}})\b")
# DNI/documento, siempre con etiqueta -- un numero de 7-8 digitos sin marca
# se deja intacto porque en este dominio suele ser un codigo o un monto.
_DNI_ETIQUETADO_RE = re.compile(rf"(?i)\b(dni|documento)\b{_SEP}(\d{{1,2}}\.\d{{3}}\.\d{{3}}|\d{{7,8}})(?![\d.,]\d|\d)")
# CUIT/CUIL sin etiqueta dentro de texto libre, con puntos, espacios o sin separador
# («20.12345678.9», «20 12345678 9», «20123456789»). Sólo se enmascara si el dígito
# verificador es válido: un monto o un código de 11 cifras casi nunca lo cumple.
_CUIT_LIBRE_RE = re.compile(
    r"(?<![\d.,])((?:20|23|24|25|26|27|30|33|34)[\s.-]?\d{2}\.?\d{3}\.?\d{3}[\s.-]?\d)(?![\d]|[.,]\d)"
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
# Teléfonos: con etiqueta, o con el formato de guiones de línea argentina
# (11-4555-1234, 0351-455-1234), que no coincide con montos ni fechas ISO.
_TELEFONO_ETIQUETADO_RE = re.compile(r"(?i)\b(tel[eé]fono|tel|cel(?:ular)?|whatsapp|wsp)\b\.?[\s:#-]{0,4}(\+?[\d()\s-]{8,18}\d)")
# Sin etiqueta, sólo formatos inequívocos: 11-4555-1234, 15-4555-1234, 0351-455-1234.
# Un código presupuestario ("11-001-0001", "16-001-2024") o un rango de años no coincide.
_TELEFONO_GUIONES_RE = re.compile(
    r"(?<![\d-])(?:\+?54[\s-]?(?:9[\s-]?)?)?(?:0?11-[2-9]\d{3}-\d{4}|15-[2-9]\d{3}-\d{4}|0[2-9]\d{1,3}-[2-9]\d{1,3}-\d{4})(?![\d-])"
)
# Con prefijo internacional (+54 9 11 4555 1234): el «+54» lo hace inequívoco.
_TELEFONO_INTERNACIONAL_RE = re.compile(r"(?<![\w+])\+54[\s-]?(?:9[\s-]?)?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{4}(?![\d-])")
# Con característica que empieza en 0 y espacio (011 4555-1234, 0351 455-1234).
_TELEFONO_CARACTERISTICA_RE = re.compile(r"(?<![\d.,/-])0[1-9]\d{1,3}[\s-]{1,2}[2-9]\d{2,3}[\s-]\d{4}(?![\d-]|[.,]\d)")
# Número local de ocho cifras (4555-1234). No se toca si alguna mitad parece un año
# («2019-2020», «ISO 9001-2015») ni si está pegado a otros guiones o puntos (códigos
# presupuestarios como «325-1234-5678» o «1234-5678-2024»).
_TELEFONO_LOCAL_RE = re.compile(
    r"(?<![\d.,/-])(?!(?:19|20)\d{2}-)[2-9]\d{3}-(?!(?:19|20)\d{2}(?!\d))\d{4}(?![\d-]|[.,/]\d)"
)
_DOCUMENTO_RE = re.compile(r"\b(?:expte|expediente|comprobante|factura)\s*[:#-]?\s*[A-Za-z0-9./-]{5,}\b", re.IGNORECASE)


_CUIT_SIN_GUIONES_RE = re.compile(r"(?:20|23|24|25|26|27|30|33|34)\d{9}")
_DNI_CON_PUNTOS_RE = re.compile(r"\d{1,2}\.\d{3}\.\d{3}")


def _parece_documento(valor, monto: bool = False) -> bool:
    """Un CUIT sin guiones o un DNI con puntos, escrito como número o como texto.

    Bajo un rótulo de importe («Deuda con proveedores») un «1.500.000» es un monto: ahí no se
    aplica la forma de DNI, y un número de 11 cifras sólo cuenta como CUIT si su dígito
    verificador es válido.
    """
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    if _CUIT_SIN_GUIONES_RE.fullmatch(texto) and (not monto or _cuit_valido(texto)):
        return True
    return not monto and bool(_DNI_CON_PUNTOS_RE.fullmatch(texto))


# Rótulos de importe: un «1.500.000» ahí es un monto, no un DNI con puntos.
ROTULO_MONTO_RE = re.compile(
    r"deuda|pago|cuenta|factura|monto|importe|saldo|\$|pesos|gasto|venta|cobr|acreedor|deudor",
    re.IGNORECASE,
)


def _cuit_valido(texto: str) -> bool:
    """Dígito verificador del CUIT/CUIL: un monto de 11 cifras casi nunca lo cumple."""
    if not re.fullmatch(r"\d{11}", texto):
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = 11 - sum(int(d) * p for d, p in zip(texto[:10], pesos)) % 11
    verificador = 0 if resto == 11 else 9 if resto == 10 else resto
    return verificador == int(texto[10])


MARCAS_SIN_DATO = frozenset({"-", "--", "---", "\u2013", "\u2014", "///", ".", "..", "...", "\u2026", "s/d", "s/i", "n/d", "s", "x"})


def _solo_numeros(valores, monto: bool = False) -> bool:
    """Valores que son cifras agregadas: números, ninguno con forma de CUIT o DNI.

    Si todos son enteros distintos de 7 u 8 cifras, se leen como documentos: un
    conteo agregado de ese tamaño es posible, pero ante la duda se excluye. Bajo un
    rótulo de importe (`monto`) esa regla no se aplica: son montos.
    """
    # «-», «///», «s/d»: marcas de sin dato en un cuadro de cifras, no nombres. «Contra las personas» con
    # 34, 101 y «-» es un conteo de delitos; sin esto se excluía como si fuera un dato personal.
    no_vacios = [v for v in valores if v is not None and str(v).strip() and str(v).strip().lower() not in MARCAS_SIN_DATO]
    if not no_vacios:
        return False
    enteros_documento = 0
    for valor in no_vacios:
        if isinstance(valor, bool) or _parece_documento(valor, monto):
            return False
        if isinstance(valor, (int, float)):
            numero = valor
        elif re.fullmatch(r"[-+]?[\d.,\s]+%?", str(valor).strip()):
            numero = None
        else:
            return False
        if numero is not None and float(numero).is_integer() and 7 <= len(str(abs(int(numero)))) <= 8:
            enteros_documento += 1
    if not monto and enteros_documento == len(no_vacios) and len(set(map(str, no_vacios))) == len(no_vacios):
        return False
    return True


CATEGORIA_RE = re.compile(r"(?:^|[\s_])tipo[\s_]+de[\s_]", re.IGNORECASE)


def columna_sensible(nombre: str, valores=None) -> bool:
    """Decide si una columna identifica actores o documentos individuales.

    Los rótulos nominales (nombre, DNI, CUIT, correo, teléfono, legajo, domicilio)
    se excluyen siempre. Los rótulos de persona (agente, empleado, titular, paciente,
    docente, socio, afiliado, alumno, destinatario, contacto) se conservan sólo si
    sus valores son cifras. Un rótulo de actor (clientes, proveedores, beneficiarios)
    se conserva sólo si sus valores son cifras agregadas ("Clientes activos": 120,
    135; "Deuda con proveedores": 1.500.000) y el rótulo no nombra a un actor
    individual en singular. El rótulo solo nunca alcanza: "Proveedores nuevos" con
    nombres adentro se excluye. Sin `valores`, se excluye.
    """
    texto = nombre or ""
    if COLUMNA_TECNICA_PERMITIDA_RE.match(texto):
        return False
    if COLUMNA_NOMINAL_RE.search(texto) and not NOMBRE_DE_COSA_RE.search(texto):
        return True
    if CATEGORIA_RE.search(texto) and _solo_numeros(valores or [], monto=True):
        # «Tipo de población usuaria · Cliente oficial», «Tipo de delito · Contra las personas»: el rótulo nombra
        # una categoría de una clasificación y la columna trae cifras; no identifica a nadie.
        return False
    if COLUMNA_PERSONA_RE.search(texto) and not NOMBRE_DE_COSA_RE.search(texto):
        # «Agentes» = 120 es un conteo; «Agente» = «Juan Pérez» es una persona.
        if valores is None:
            # Sin valores (un encabezado suelto) no viaja ningún dato: el plural o un
            # marcador de conteo («Agentes», «Cantidad de pacientes») nombra un conteo;
            # el singular («Agente», «Titular») nombra a alguien.
            return not (ACTOR_AGREGADO_RE.search(texto) or COLUMNA_AGREGADA_PERMITIDA_RE.search(texto)
                        or COLUMNA_PERSONA_PLURAL_RE.search(texto))
        return not _solo_numeros(valores, monto=bool(ROTULO_MONTO_RE.search(texto)))
    if COLUMNA_AGREGADA_PERMITIDA_RE.search(texto):
        return False
    if not COLUMNA_SENSIBLE_RE.search(texto) or NOMBRE_DE_COSA_RE.search(texto):
        return False
    if valores is None or not _solo_numeros(valores, monto=bool(ROTULO_MONTO_RE.search(texto))):
        return True
    return not (ACTOR_AGREGADO_RE.search(texto) or ACTOR_PLURAL_RE.search(texto))


def _cuit_libre(m: re.Match) -> str:
    digitos = re.sub(r"\D", "", m.group(1))
    return "[CUIT_REDACTADO]" if _cuit_valido(digitos) else m.group(0)


def _redactar_valor(valor: Any) -> Any:
    if not isinstance(valor, str):
        return valor
    texto = valor
    texto = _CUIT_CON_GUIONES_RE.sub("[CUIT_REDACTADO]", texto)
    texto = _CUIT_ETIQUETADO_RE.sub(lambda m: f"{m.group(1)} [CUIT_REDACTADO]", texto)
    texto = _CUIT_LIBRE_RE.sub(_cuit_libre, texto)
    texto = _DNI_ETIQUETADO_RE.sub(lambda m: f"{m.group(1)} [DNI_REDACTADO]", texto)
    texto = _EMAIL_RE.sub("[EMAIL_REDACTADO]", texto)
    texto = _TELEFONO_ETIQUETADO_RE.sub(lambda m: f"{m.group(1)} [TELEFONO_REDACTADO]", texto)
    texto = _TELEFONO_INTERNACIONAL_RE.sub("[TELEFONO_REDACTADO]", texto)
    texto = _TELEFONO_GUIONES_RE.sub("[TELEFONO_REDACTADO]", texto)
    texto = _TELEFONO_CARACTERISTICA_RE.sub("[TELEFONO_REDACTADO]", texto)
    texto = _TELEFONO_LOCAL_RE.sub("[TELEFONO_REDACTADO]", texto)
    texto = _DOCUMENTO_RE.sub("[DOCUMENTO_REDACTADO]", texto)
    return texto


def redactar_texto_libre(valor: str) -> str:
    """Segunda barrera para texto libre que abandona una superficie pública.

    La sanitización de carga sigue siendo la defensa principal. Esta función
    reutiliza exactamente los mismos patrones para campos redactados a mano
    que no formaban parte de la tabla cargada.
    """
    return str(_redactar_valor(valor or ""))


def limpiar_nombre_columna(nombre: Any) -> Any:
    """Quita la marca de orden de bytes (BOM) que algunos CSV dejan pegada al primer rótulo."""
    return nombre.replace("\ufeff", "") if isinstance(nombre, str) else nombre


def sanear(datos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict]:
    """Devuelve (datos_saneados, reporte). `reporte` se persiste junto al
    informe para que la exclusión sea auditable.

    Las columnas conservan el orden en que aparecen en el archivo: armarlas con un conjunto
    cambiaba el orden de una corrida a otra.
    """
    if not datos:
        return datos, {"columnas_excluidas": [], "valores_redactados": 0, "redacciones_por_columna": {}}

    if any(isinstance(c, str) and "\ufeff" in c for fila in datos for c in fila):
        datos = [{limpiar_nombre_columna(c): v for c, v in fila.items()} for fila in datos]
    columnas: list[str] = list(dict.fromkeys(c for fila in datos for c in fila))

    excluidas = sorted(c for c in columnas if columna_sensible(c, [fila.get(c) for fila in datos]))
    conservadas = [c for c in columnas if c not in excluidas]

    redactados = 0
    redacciones_por_columna: dict[str, int] = {}
    saneados = []
    for fila in datos:
        nueva = {}
        for col in conservadas:
            valor = fila.get(col)
            if isinstance(valor, str):
                original = valor
                valor = _redactar_valor(valor)
                if valor != original:
                    redactados += 1
                    redacciones_por_columna[col] = redacciones_por_columna.get(col, 0) + 1
            nueva[col] = valor
        saneados.append(nueva)

    return saneados, {
        "columnas_excluidas": excluidas,
        "valores_redactados": redactados,
        "redacciones_por_columna": redacciones_por_columna,
        "etapa_sanitizacion": {
            "ejecutada": True,
            "resultado": "sin_informacion_agregada" if not conservadas else "informacion_agregada_disponible",
            "exclusiones": [{"columna": c, "motivo": "Identifica actores o documentos individuales"} for c in excluidas],
            "valores_enmascarados": redactados,
            "columnas_restantes": sorted(conservadas),
            "filas_restantes": len(saneados),
        },
    }
