"""Antecedentes automáticos de lectura y resultados revisados por separado.

La biblioteca no declara errores ni cambia reglas. Una lectura confirmada y
analizada orienta futuras lecturas; sólo la revisión adicional valida resultados.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import re
from collections import Counter
from types import SimpleNamespace
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

import models
from services import calibracion
from services import interpretacion_previa as ip
from versiones import version_codigo

RESULTADOS = {"senal_justificada", "senal_infundada", "omision", "sin_senal_revisado"}
CONTROLES = {*ip.LENTES, "relaciones"}


class Propuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archivo: str = Field(min_length=1, max_length=250)
    hoja: str = Field(min_length=1, max_length=200)
    bloque: int = Field(ge=1)
    control: str = Field(min_length=1, max_length=80)
    resultado: str
    fundamento: str = Field(min_length=20, max_length=1000)
    fuente_url: str = Field(min_length=12, max_length=1000)
    localizador: str = Field(default="", max_length=200)
    hallazgo_id: Optional[int] = Field(default=None, ge=1)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aprobar: bool
    fundamento: str = Field(min_length=20, max_length=1000)


def url_publica(url: str) -> str:
    """Conserva sólo una referencia HTTP(S); jamás se descarga desde el servidor."""
    u = urlsplit(url.strip())
    host = (u.hostname or "").lower().rstrip(".")
    if u.scheme not in {"http", "https"} or not host or u.username or u.password or u.fragment:
        raise ValueError("Indicá la URL pública original del archivo, sin credenciales ni fragmentos")
    if host in {"localhost", "local"} or host.endswith((".local", ".internal")):
        raise ValueError("La fuente debe ser una publicación accesible públicamente")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("La fuente debe ser una publicación accesible públicamente")
    except ValueError as exc:
        if "publicación" in str(exc):
            raise
    return urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip("/") or "/", u.query, ""))


def _cuadro(informe: models.Informe, archivo: str, hoja: str, bloque: int):
    lectura = ip.exigir(informe)
    unidades = [u for u in lectura["cuadros"] if (u["archivo"], u["hoja"], int(u["bloque"])) == (archivo, hoja, bloque)]
    if len(unidades) != 1:
        raise ValueError("El cuadro no pertenece a la interpretación confirmada")
    cobertura = ((informe.devolucion.cobertura or {}).get("excel") or {}) if informe.devolucion else {}
    bloques = [b for b in cobertura.get("bloques") or []
               if (b.get("archivo"), b.get("hoja"), int(b.get("bloque") or 0)) == (archivo, hoja, bloque)]
    if len(bloques) != 1:
        raise ValueError("El cuadro no tiene un análisis terminado y trazable")
    return unidades[0], bloques[0]


def _fuente(informe: models.Informe, archivo: str):
    fuentes = [f for f in ((informe.saneamiento or {}).get("proveniencia") or {}).get("fuentes", [])
               if f.get("nombre_original") == archivo and re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256_bruto") or ""))]
    if len(fuentes) != 1:
        raise ValueError("No se pudo vincular el cuadro con una única copia original")
    return fuentes[0]


def _mismo_cuadro_control(h: models.Hallazgo, unidad: dict, p: Propuesta) -> bool:
    ev = h.evidencia or {}
    mismo_cuadro = (ev.get("archivo_origen") or ev.get("archivo")) == p.archivo and ev.get("hoja") == p.hoja
    if ev.get("bloque_excel") is not None:
        mismo_cuadro = mismo_cuadro and int(ev["bloque_excel"]) == p.bloque
    elif ev.get("celda") and p.control == "relaciones":
        fila = re.search(r"\d+$", str(ev["celda"]))
        mismo_cuadro = mismo_cuadro and bool(fila) and int(fila.group()) in set(unidad.get("filas_origen") or [])
    else:
        mismo_cuadro = False
    mismo_control = (h.lente == p.control or
                     (p.control == "relaciones" and h.lente == "conciliador" and
                      ev.get("regla") in {"relacion_leida_no_cierra", "plausibilidad_leida"}))
    return mismo_cuadro and mismo_control


def _senal(db: Session, informe: models.Informe, unidad: dict, p: Propuesta):
    if p.resultado not in {"senal_justificada", "senal_infundada"}:
        if p.hallazgo_id:
            raise ValueError("Una omisión o un cuadro sin señal se revisan con localizador, no con una señal")
        if len(p.localizador.strip()) < 3:
            raise ValueError("Indicá las celdas o filas revisadas para una omisión o un cuadro sin señal")
        if p.resultado == "sin_senal_revisado" and any(
                _mismo_cuadro_control(h, unidad, p) for h in informe.hallazgos):
            raise ValueError("Este control sí produjo señales en el cuadro; revisalas antes de registrarlo sin señal")
        return {"localizador": p.localizador.strip()}
    if not p.hallazgo_id:
        raise ValueError("La revisión de una señal requiere identificar la señal y su respuesta humana")
    h = db.query(models.Hallazgo).filter_by(id=p.hallazgo_id, informe_id=informe.id).first()
    if not h:
        raise ValueError("La señal no pertenece al informe")
    ev = h.evidencia or {}
    if not _mismo_cuadro_control(h, unidad, p):
        raise ValueError("La señal no corresponde a este cuadro y control")
    r = (db.query(models.RespuestaSenal).filter_by(informe_id=informe.id, hallazgo_id=h.id)
         .order_by(models.RespuestaSenal.id.desc()).first())
    esperado = "error_real" if p.resultado == "senal_justificada" else "dato_correcto"
    if not r or r.respuesta != esperado or r.usuario_id != informe.usuario_id:
        raise ValueError("Primero quien hizo el informe debe responder esa señal con el mismo resultado")
    return {"hallazgo_id": h.id, "respuesta_id": r.id, "regla": ev.get("regla"),
            "celda": ev.get("celda"), "localizador": p.localizador.strip()}


def proponer(db: Session, informe: models.Informe, p: Propuesta, usuario_id: int):
    if p.control not in CONTROLES or p.resultado not in RESULTADOS:
        raise ValueError("Elegí un control y un resultado del catálogo")
    unidad, bloque = _cuadro(informe, p.archivo, p.hoja, p.bloque)
    traza = (bloque.get("trazabilidad_controles") or {}).get(p.control) or {}
    if not traza.get("seleccionado") or traza.get("estado") != "ejecutado":
        raise ValueError("Sólo se incorpora un control efectivamente ejecutado en el cuadro")
    perfil = calibracion.PerfilCuadro(**calibracion.perfil_confirmado(unidad)).model_dump()
    fuente = _fuente(informe, p.archivo)
    url = url_publica(p.fuente_url)
    evidencia = _senal(db, informe, unidad, p)
    grupo = hashlib.sha256(urlsplit(url)._replace(query="").geturl().encode()).hexdigest()
    existente = db.query(models.CasoBiblioteca).filter_by(informe_id=informe.id, archivo=p.archivo,
        hoja=p.hoja, bloque=p.bloque, control=p.control, resultado=p.resultado, hallazgo_id=p.hallazgo_id).filter(
        models.CasoBiblioteca.estado != "rechazado").first()
    if existente:
        raise ValueError("Ya hay una propuesta activa para este resultado, control y cuadro")
    caso = models.CasoBiblioteca(informe_id=informe.id, propuesto_por_id=usuario_id,
        hallazgo_id=p.hallazgo_id, estado="pendiente", archivo=p.archivo, hoja=p.hoja, bloque=p.bloque,
        control=p.control, resultado=p.resultado, fundamento=p.fundamento.strip(), fuente_url=url,
        fuente_sha256=fuente["sha256_bruto"], grupo_fuente=grupo, perfil_cuadro=perfil,
        evidencia=evidencia, version_codigo=version_codigo())
    db.add(caso)
    db.flush()
    return caso


def decidir(db: Session, caso: models.CasoBiblioteca, decision: Decision, usuario_id: int):
    if caso.estado != "pendiente":
        raise ValueError("El caso ya fue revisado; las decisiones quedan registradas y no se sobrescriben")
    if decision.aprobar:
        # Rechazar una propuesta obsoleta debe seguir siendo posible; aprobarla, no.
        informe = db.get(models.Informe, caso.informe_id)
        if not informe:
            raise ValueError("El informe original ya no existe")
        unidad, bloque = _cuadro(informe, caso.archivo, caso.hoja, caso.bloque)
        if (_fuente(informe, caso.archivo)["sha256_bruto"] != caso.fuente_sha256
                or calibracion.perfil_confirmado(unidad) != caso.perfil_cuadro
                or ((bloque.get("trazabilidad_controles") or {}).get(caso.control) or {}).get("estado") != "ejecutado"):
            raise ValueError("Cambió la evidencia del caso; volvé a proponerlo desde el informe actual")
        if caso.hallazgo_id:
            p = Propuesta(archivo=caso.archivo, hoja=caso.hoja, bloque=caso.bloque, control=caso.control,
                         resultado=caso.resultado, fundamento=caso.fundamento, fuente_url=caso.fuente_url,
                         hallazgo_id=caso.hallazgo_id)
            if _senal(db, informe, unidad, p).get("respuesta_id") != caso.evidencia.get("respuesta_id"):
                raise ValueError("Cambió la respuesta humana de la señal; volvé a proponer el caso")
    caso.estado = "aprobado" if decision.aprobar else "rechazado"
    caso.revisado_por_id = usuario_id
    caso.decidido_en = dt.datetime.utcnow()
    caso.evidencia = {**caso.evidencia, "decision_fundamento": decision.fundamento.strip()}
    db.flush()
    return caso


def observados(db: Session, usuario_id: int | None = None) -> list:
    """Recupera lecturas confirmadas con análisis terminado, sin cargar cifras.

La confirmación pertenece al flujo del informe; no se exige una aprobación
adicional para usar su perfil como pista. No se infiere que sus señales acierten.
"""
    casos = []
    consulta = db.query(models.Informe.id, models.Informe.saneamiento, models.Devolucion.cobertura).join(
        models.Devolucion, models.Devolucion.informe_id == models.Informe.id)
    if usuario_id is not None:
        consulta = consulta.filter(models.Informe.usuario_id == usuario_id)
    filas = consulta.all()
    for _id, saneamiento, cobertura in filas:
        base = saneamiento or {}
        lectura = base.get(ip.CAMPO) or {}
        if lectura.get("version") != ip.VERSION or lectura.get("estado") != "confirmada":
            continue
        cuadros = lectura.get("cuadros") or []
        decisiones = [{k: u.get(k) for k in ("id", "confirmada", "plan")} for u in cuadros]
        if not cuadros or (lectura.get("confirmacion") or {}).get("decision_huella") != ip.huella(decisiones):
            continue
        fuentes = {f.get("nombre_original"): f.get("sha256_bruto") for f in
                   ((base.get("proveniencia") or {}).get("fuentes") or [])
                   if re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256_bruto") or ""))}
        bloques = {(b.get("archivo"), b.get("hoja"), str(b.get("bloque"))): b for b in
                   (((cobertura or {}).get("excel") or {}).get("bloques") or [])}
        for u in cuadros:
            if not u.get("confirmada") or u.get("plan") != ip.plan(u["confirmada"]):
                continue
            sha = fuentes.get(u.get("archivo"))
            bloque = bloques.get((u.get("archivo"), u.get("hoja"), str(u.get("bloque"))))
            if not sha or not bloque:
                continue
            controles = tuple(k for k, v in (bloque.get("trazabilidad_controles") or {}).items()
                              if k in CONTROLES and v.get("estado") == "ejecutado")
            casos.append(SimpleNamespace(fuente_sha256=sha, grupo_fuente=sha,
                perfil_cuadro=calibracion.perfil_confirmado(u), controles=controles,
                resultado=None, revisado=False))
    return casos


def indice(db: Session, usuario_id: int | None = None) -> dict:
    """Indexa perfiles observados; resultados aprobados enriquecen el mismo caso."""
    index: dict[tuple, dict[str, object]] = {}
    for caso in observados(db, usuario_id):
        for control in caso.controles:
            key = (control, calibracion.firma_perfil(caso.perfil_cuadro))
            index.setdefault(key, {}).setdefault(caso.fuente_sha256, caso)
    for caso in db.query(models.CasoBiblioteca).filter_by(estado="aprobado").order_by(models.CasoBiblioteca.id):
        key = (caso.control, calibracion.firma_perfil(caso.perfil_cuadro))
        index.setdefault(key, {})[caso.fuente_sha256] = caso
    return index


def experiencia(index: dict, unidad: dict, control: str, sha_actual: str | None = None) -> dict:
    perfil = calibracion.firma_perfil(calibracion.perfil_confirmado(unidad))
    vistos = [c for c in index.get((control, perfil), {}).values() if c.fuente_sha256 != sha_actual]
    return {"control": control, "coincidencia": "estructura_y_roles_confirmados",
            "casos_comparables": len(vistos),
            "revisados_por_persona": sum(bool(c.resultado) for c in vistos),
            "resultados": dict(Counter(c.resultado for c in vistos if c.resultado)),
            "limite": "Lecturas confirmadas y analizadas con igual estructura y roles; sólo los resultados revisados tienen evaluación humana. Ningún caso mide acierto en este informe ni cambia las cuentas."}


def antecedentes_interpretacion(casos: list, columnas: list[str], sha_actual: str | None = None) -> dict:
    """Pista débil con cabeceras específicas iguales; nunca una decisión automática."""
    nombres = tuple(sorted(calibracion._normalizar(c) for c in columnas))
    if len(nombres) < 3 or len(set(nombres)) < 3:
        return {"casos": 0, "orientacion": None}
    por_fuente = {}
    sha_vistos = set()
    for caso in casos:
        if caso.fuente_sha256 == sha_actual:
            continue
        headers = tuple(sorted(calibracion._normalizar(c) for c in (caso.perfil_cuadro.get("columnas") or {})))
        if headers == nombres and caso.fuente_sha256 not in sha_vistos:
            por_fuente[caso.grupo_fuente or caso.fuente_sha256] = caso
            sha_vistos.add(caso.fuente_sha256)
    if not por_fuente:
        return {"casos": len(por_fuente), "orientacion": None}
    perfiles = {str((c.perfil_cuadro["institucion"], c.perfil_cuadro["regimen"], c.perfil_cuadro["tipo"],
                     c.perfil_cuadro["eje"], tuple(sorted((calibracion._normalizar(k), v)
                                                          for k, v in c.perfil_cuadro["columnas"].items()))))
               for c in por_fuente.values()}
    if len(perfiles) != 1:
        return {"casos": len(por_fuente), "orientacion": None}
    p = next(iter(por_fuente.values())).perfil_cuadro
    if p["tipo"] in {"otro", "desconocido"}:
        return {"casos": len(por_fuente), "orientacion": None}
    return {"casos": len(por_fuente), "orientacion": {k: p[k] for k in ("institucion", "regimen", "tipo", "eje", "columnas")}}


def resumen(db: Session):
    contadores = Counter(c.estado for c in db.query(models.CasoBiblioteca.estado).all())
    return {"observados": len(observados(db)), "aprobados": contadores["aprobado"], "pendientes": contadores["pendiente"],
            "rechazados": contadores["rechazado"],
            "limite": "Las lecturas confirmadas orientan sin aprobación adicional; sólo los resultados aprobados tienen revisión humana. No es entrenamiento de pesos ni validación externa ciega."}
