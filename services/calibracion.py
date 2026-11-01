"""Calibración y alcance retrospectivo. Nunca modifica decisiones ni sellos."""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from collections import Counter
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

import models


class PerfilCuadro(BaseModel):
    """Firma conservadora: sólo los encabezados y roles confirmados comparan casos."""

    model_config = ConfigDict(extra="forbid")
    institucion: str
    regimen: str
    tipo: str
    eje: str
    columnas: dict[str, str] = Field(min_length=1)
    unidad: Optional[str] = None


class RevisionHumana(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resultado: Literal["senal_justificada", "senal_infundada", "omision", "sin_senal_revisado"]
    fundamento: str = Field(min_length=10, max_length=1000)
    fecha: dt.date


class Caso(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=160)
    tipo: Literal["caso_calibracion", "caso_validacion_interna", "caso_validacion_externa_ciega"]
    referencia: str = Field(min_length=5, max_length=500)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    esperado: Any
    obtenido: Any
    usado_para_calibracion: bool = False
    perfil_cuadro: Optional[PerfilCuadro] = None
    revision_humana: Optional[RevisionHumana] = None
    origen: Optional[Literal["informe_publico", "sintetico", "otro"]] = None
    grupo_fuente: Optional[str] = Field(default=None, min_length=3, max_length=160)

    @model_validator(mode="after")
    def aislamiento(self):
        if self.tipo == "caso_validacion_externa_ciega" and self.usado_para_calibracion:
            raise ValueError("Un caso de calibración no puede declararse validación externa ciega")
        if self.tipo == "caso_calibracion":
            self.usado_para_calibracion = True
        if self.revision_humana and (not self.perfil_cuadro or not self.origen):
            raise ValueError("Un caso revisado requiere perfil del cuadro y origen")
        if (self.revision_humana or self.tipo == "caso_validacion_externa_ciega") and not self.grupo_fuente:
            raise ValueError("Un caso revisado o ciego requiere grupo_fuente para separar variantes del mismo informe")
        return self


class CorridaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dominio: str = Field(min_length=1, max_length=50)
    version_protocolo: str = Field(min_length=1, max_length=60)
    version_codigo: str = Field(pattern=r"^[a-f0-9]{64}$")
    control: str = Field(min_length=1, max_length=80)
    version_control: str = Field(pattern=r"^[a-f0-9]{64}$")
    bateria: str = Field(min_length=3, max_length=200)
    casos: list[Caso] = Field(min_length=1, max_length=500)
    tolerancia: float = Field(default=0, ge=0)
    categoria_incidencia: Optional[Literal["cambio_motor", "cambio_entorno_datos", "condiciones_no_satisfechas"]] = None
    desde: dt.datetime
    hasta: dt.datetime
    observaciones: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def intervalo(self):
        for campo in ("desde", "hasta"):
            valor = getattr(self, campo)
            if valor.tzinfo:
                setattr(self, campo, valor.astimezone(dt.timezone.utc).replace(tzinfo=None))
        if self.desde > self.hasta:
            raise ValueError("Intervalo temporal invertido")
        if len({c.id for c in self.casos}) != len(self.casos):
            raise ValueError("IDs de caso duplicados")
        calibrados = {c.sha256 for c in self.casos if c.usado_para_calibracion}
        if any(c.tipo == "caso_validacion_externa_ciega" and c.sha256 in calibrados for c in self.casos):
            raise ValueError("Una batería no puede calibrar y validar externamente el mismo caso")
        grupos_calibrados = {c.grupo_fuente for c in self.casos if c.usado_para_calibracion and c.grupo_fuente}
        if any(c.tipo == "caso_validacion_externa_ciega" and c.grupo_fuente in grupos_calibrados for c in self.casos):
            raise ValueError("Una batería no puede calibrar y validar externamente variantes del mismo informe")
        return self


def dentro_tolerancia(esperado, obtenido, tolerancia):
    if isinstance(esperado, bool) or isinstance(obtenido, bool):
        return type(esperado) is type(obtenido) and esperado == obtenido
    if isinstance(esperado, (int, float)) and isinstance(obtenido, (int, float)):
        return math.isfinite(esperado) and math.isfinite(obtenido) and abs(esperado - obtenido) <= tolerancia
    if isinstance(esperado, dict) and isinstance(obtenido, dict):
        return esperado.keys() == obtenido.keys() and all(dentro_tolerancia(v, obtenido[k], tolerancia) for k, v in esperado.items())
    if isinstance(esperado, list) and isinstance(obtenido, list):
        return len(esperado) == len(obtenido) and all(dentro_tolerancia(a, b, tolerancia) for a, b in zip(esperado, obtenido))
    return type(esperado) is type(obtenido) and esperado == obtenido


def registrar(db: Session, payload: CorridaCreate, responsable_id: int):
    anteriores = db.query(models.CalibrationRun).all()
    for caso in payload.casos:
        # Aislamiento en ambos sentidos y entre corridas: cambiar el ID no hace nuevo al archivo.
        for anterior in anteriores:
            for previo in anterior.casos:
                if (previo.get("sha256") != caso.sha256
                        and not (caso.grupo_fuente and previo.get("grupo_fuente") == caso.grupo_fuente)):
                    continue
                calibrado = previo.get("tipo") == "caso_calibracion" or previo.get("usado_para_calibracion")
                ciego = previo.get("tipo") == "caso_validacion_externa_ciega"
                if caso.tipo == "caso_validacion_externa_ciega" and calibrado:
                    raise ValueError("El caso ya se utilizó para calibración; no es externo ciego")
                if caso.usado_para_calibracion and ciego:
                    raise ValueError("Un caso reservado como validación externa ciega no puede usarse para calibrar")
    casos = [{**c.model_dump(), "dentro_tolerancia": dentro_tolerancia(c.esperado, c.obtenido, payload.tolerancia),
              "origen_resultado": "aportado_por_responsable"} for c in payload.casos]
    corrida = models.CalibrationRun(**payload.model_dump(exclude={"casos"}), casos=casos,
                                    estado="aprobada" if all(c["dentro_tolerancia"] for c in casos) else "fallida",
                                    responsable_id=responsable_id)
    db.add(corrida)
    db.flush()
    return corrida


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\d+(?:[.,]\d+)*", "#", texto)
    return re.sub(r"\s+", " ", re.sub(r"[^\w#]+", " ", texto)).strip()


def perfil_confirmado(unidad: dict) -> dict:
    lectura = unidad.get("confirmada") or {}
    return {"institucion": lectura.get("institucion"), "regimen": lectura.get("regimen"),
            "tipo": lectura.get("tipo"), "eje": lectura.get("eje"),
            "columnas": lectura.get("roles") or {}, "unidad": lectura.get("unidad")}


def firma_perfil(perfil: dict) -> tuple:
    """Coincidencia estricta, no una probabilidad ni una inferencia de error."""
    return (perfil.get("institucion"), perfil.get("regimen"), perfil.get("tipo"), perfil.get("eje"),
            _normalizar(perfil.get("unidad") or ""),
            tuple(sorted((_normalizar(nombre), rol) for nombre, rol in (perfil.get("columnas") or {}).items())))


def indice_experiencia(corridas) -> dict:
    """Indexa una vez para no recorrer todo el banco por cada cuadro y control."""
    indice: dict[tuple, dict[str, dict]] = {}
    for corrida in corridas:
        for caso in corrida.casos or []:
            if (caso.get("tipo") != "caso_calibracion" or caso.get("origen") != "informe_publico"
                    or not caso.get("revision_humana") or not caso.get("perfil_cuadro")):
                continue
            # Variantes del mismo informe no inflan el respaldo aunque cambie el SHA.
            clave = (corrida.control, firma_perfil(caso["perfil_cuadro"]))
            indice.setdefault(clave, {})[caso.get("grupo_fuente") or caso["sha256"]] = caso
    return indice


def experiencia_comparable(indice: dict, unidad: dict, control: str) -> dict:
    """Cuenta sólo informes públicos con revisión humana registrados para calibración.

    Una firma igual no demuestra equivalencia semántica: se comunica como
    coincidencia estructural y nunca se traduce a confianza o tasa de acierto.
    """
    firma = firma_perfil(perfil_confirmado(unidad))
    vistos = indice.get((control, firma), {})
    resultados = Counter(c["revision_humana"]["resultado"] for c in vistos.values())
    return {"control": control, "coincidencia": "estructura_y_roles_confirmados",
            "casos_comparables": len(vistos), "revisados_por_persona": len(vistos),
            "resultados": dict(resultados),
            "limite": "Coincidencia estructural estricta de casos públicos revisados; no mide acierto en este informe ni garantiza significado equivalente."}


def potencialmente_afectadas(db: Session, corrida):
    if corrida.estado != "fallida":
        return []
    candidatos = db.query(models.EjecucionAnalisis).filter(
        models.EjecucionAnalisis.dominio == corrida.dominio,
        models.EjecucionAnalisis.version_codigo == corrida.version_codigo,
        models.EjecucionAnalisis.version_protocolo == corrida.version_protocolo,
        models.EjecucionAnalisis.creado_en >= corrida.desde,
        models.EjecucionAnalisis.creado_en <= corrida.hasta,
    ).all()
    return [e for e in candidatos if any(c.get("lente") == corrida.control and c.get("version_control") == corrida.version_control
                                        and c.get("ejecutado") for c in e.manifiesto.get("controles", []))]
