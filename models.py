from __future__ import annotations

import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Usuario(Base):
    """Usuario real de la aplicacion. Reemplaza la clave compartida como identidad operativa."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    email_notificaciones: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    rol: Mapped[str] = mapped_column(String(40), nullable=False, default="analista")  # admin | analista | lector
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    # Las sesiones emitidas antes de este momento dejan de valer (cerrar sesiones,
    # cambiar la contraseña o desactivar al usuario). UTC sin zona, como el resto.
    sesiones_desde: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    # Grupo de cursada (0.10.62): cada participante ve los proyectos y la votación de su grupo. Sin grupo es el de las
    # comisiones originales; la cuenta administradora ve todos.
    grupo: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)

    informes: Mapped[list[Informe]] = relationship("Informe", back_populates="usuario")
    trabajos_analisis: Mapped[list[AnalysisJob]] = relationship("AnalysisJob", back_populates="usuario")
    learning_events: Mapped[list[LearningEvent]] = relationship("LearningEvent", back_populates="usuario")
    proyectos_ia: Mapped[list[ProyectoIA]] = relationship("ProyectoIA", back_populates="usuario")
    mensajes_proyecto_ia: Mapped[list[MensajeProyectoIA]] = relationship("MensajeProyectoIA", back_populates="usuario")
    aprendizajes_incubadora: Mapped[list["AprendizajeIncubadora"]] = relationship("AprendizajeIncubadora", back_populates="usuario")
    eventos_actividad: Mapped[list["ActivityEvent"]] = relationship("ActivityEvent", back_populates="usuario")
    votos_proyecto_ia: Mapped[list["VotoProyectoIA"]] = relationship("VotoProyectoIA", back_populates="usuario")
    evaluaciones_certificacion: Mapped[list["EvaluacionCertificacion"]] = relationship(
        "EvaluacionCertificacion",
        foreign_keys="EvaluacionCertificacion.creado_por_id",
        back_populates="creado_por",
    )


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    contacto_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    informes: Mapped[list[Informe]] = relationship("Informe", back_populates="area")


class Informe(Base):
    """Carga de información agregada de una unidad para un período dado."""

    __tablename__ = "informes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_id: Mapped[int] = mapped_column(Integer, ForeignKey("areas.id"), nullable=False, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    periodo: Mapped[str] = mapped_column(String(50), nullable=False)
    dominio: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    modo: Mapped[str] = mapped_column(String(20), nullable=False, default="intraarea")  # intraarea | interareas
    datos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)  # lista de registros tabulares, ya saneados
    saneamiento: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # columnas excluidas / valores redactados
    creado_por: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    area: Mapped[Area] = relationship("Area", back_populates="informes")
    usuario: Mapped[Optional[Usuario]] = relationship("Usuario", back_populates="informes")
    hallazgos: Mapped[list[Hallazgo]] = relationship("Hallazgo", back_populates="informe")
    interpretaciones: Mapped[list[InterpretacionModelo]] = relationship("InterpretacionModelo", back_populates="informe")
    triangulacion: Mapped[Optional[Triangulacion]] = relationship("Triangulacion", back_populates="informe", uselist=False)
    devolucion: Mapped[Optional[Devolucion]] = relationship("Devolucion", back_populates="informe", uselist=False)
    trabajos_analisis: Mapped[list[AnalysisJob]] = relationship(
        "AnalysisJob",
        back_populates="informe",
        order_by="AnalysisJob.creado_en.desc()",
    )
    learning_events: Mapped[list[LearningEvent]] = relationship("LearningEvent", back_populates="informe")
    evaluaciones_certificacion: Mapped[list["EvaluacionCertificacion"]] = relationship(
        "EvaluacionCertificacion", back_populates="informe"
    )


class Hallazgo(Base):
    """Salida estructurada de una lente sobre un informe."""

    __tablename__ = "hallazgos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), nullable=False, index=True)
    lente: Mapped[str] = mapped_column(String(30), nullable=False)  # conciliador | ajedrecista | cronista | orquesta | radiologo | rizoma | matematico
    modo: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # p.ej. imposibilidad | priorizacion
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False, default="media")  # baja | media | alta
    evidencia: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    tipo_evidencia: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    alcance: Mapped[str] = mapped_column(String(60), nullable=False, default="agregado")
    metodo: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    incertidumbre: Mapped[str] = mapped_column(String(20), nullable=False, default="media")
    estado_validacion: Mapped[str] = mapped_column(String(60), nullable=False, default="pendiente_decision_humana")
    pregunta_institucional: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # «Qué pasó» en una frase llana (plantillas, no IA). Los hallazgos anteriores no la tienen:
    # se arma al mostrarlos, sin reescribir la base.
    resumen_llano: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limites: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    informe: Mapped[Informe] = relationship("Informe", back_populates="hallazgos")


class RespuestaSenal(Base):
    """Qué resultó ser una señal, según quien hizo el informe: error real, dato correcto o no sabe.

    Cada respuesta es una fila nueva (nada se borra): vale la última. Sirve para medir la herramienta con casos reales;
    nunca para evaluar a la persona ni al área.
    """

    __tablename__ = "respuestas_senal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Al reanalizar, las señales se regeneran: la respuesta queda (con la copia de su señal) y el vínculo en NULL.
    hallazgo_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("hallazgos.id", ondelete="SET NULL"), nullable=True, index=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    respuesta: Mapped[str] = mapped_column(String(20), nullable=False)  # error_real | dato_correcto | no_se
    comentario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Copia de la señal respondida: sigue sirviendo para medir aunque la señal se regenere.
    lente: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    regla: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    hoja: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    celda: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    # Prioridad del caso y versión del motor al momento de responder: la precisión por prioridad no cambia cuando
    # cambia el código (antes se recalculaba con el código vigente). NULL en las respuestas anteriores.
    prioridad: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    version_motor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    creado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=now)


class InterpretacionModelo(Base):
    """Lectura de un modelo de IA sobre el conjunto de hallazgos de un informe."""

    __tablename__ = "interpretaciones_modelo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), nullable=False, index=True)
    modelo: Mapped[str] = mapped_column(String(50), nullable=False)  # claude | gpt | mock
    identificador_version: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contenido: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    informe: Mapped[Informe] = relationship("Informe", back_populates="interpretaciones")


class Triangulacion(Base):
    """Consolidación entre las interpretaciones de los distintos modelos de IA."""

    __tablename__ = "triangulaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), unique=True, nullable=False)
    coincidencias: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    divergencias: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    hallazgos_singulares: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    convergencia_multilente: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)  # lentes distintas que senalan el mismo locus (ver services/convergencia.py)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    informe: Mapped[Informe] = relationship("Informe", back_populates="triangulacion")


class Devolucion(Base):
    """Mensaje directo y comprensible dirigido al responsable de decisión, previo a cualquier escalamiento."""

    __tablename__ = "devoluciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), unique=True, nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    hay_hallazgos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estado: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDIENTE")
    cobertura: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    informe: Mapped[Informe] = relationship("Informe", back_populates="devolucion")
    decision: Mapped[Optional[DecisionDirector]] = relationship("DecisionDirector", back_populates="devolucion", uselist=False)


class DecisionDirector(Base):
    """Decisión trazable del responsable humano. Se registra siempre."""

    __tablename__ = "decisiones_director"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    devolucion_id: Mapped[int] = mapped_column(Integer, ForeignKey("devoluciones.id"), unique=True, nullable=False)
    escalar: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tipo_decision: Mapped[str] = mapped_column(String(40), nullable=False, default="sin_escalamiento")
    pregunta_institucional: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hallazgo_ids: Mapped[Optional[list[int]]] = mapped_column(JSONB, nullable=True)
    comentario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decidido_por: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    decidido_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    devolucion: Mapped[Devolucion] = relationship("Devolucion", back_populates="decision")
    documentos: Mapped[list[DocumentoEnrutamiento]] = relationship("DocumentoEnrutamiento", back_populates="decision")


class DocumentoEnrutamiento(Base):
    """Devolución formal generada para la unidad responsable, tras la decisión de escalar."""

    __tablename__ = "documentos_enrutamiento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(Integer, ForeignKey("decisiones_director.id"), nullable=False)
    area_destino_id: Mapped[int] = mapped_column(Integer, ForeignKey("areas.id"), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    decision: Mapped[DecisionDirector] = relationship("DecisionDirector", back_populates="documentos")
    area_destino: Mapped[Area] = relationship("Area")


class LearningEvent(Base):
    """Registro estructurado de aprendizajes curados para consulta y métricas."""

    __tablename__ = "learning_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("informes.id"), nullable=True, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="propuesto")
    lente_afectada: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    hallazgo_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    metadata_evento: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    informe: Mapped[Optional[Informe]] = relationship("Informe", back_populates="learning_events")
    usuario: Mapped[Optional[Usuario]] = relationship("Usuario", back_populates="learning_events")


class AprendizajeIncubadora(Base):
    """Registro estructurado de aprendizajes curados de Gobernanza Incubadora."""

    __tablename__ = "learning_events_incubadora"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proyecto_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=True, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="propuesto")
    tema: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    metadata_evento: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    proyecto: Mapped[Optional["ProyectoIA"]] = relationship("ProyectoIA")
    usuario: Mapped[Optional[Usuario]] = relationship("Usuario", back_populates="aprendizajes_incubadora")


class ActivityEvent(Base):
    """Bitacora operativa para reconstruir recorridos de uso y aprendizaje."""

    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    informe_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("informes.id"), nullable=True, index=True)
    proyecto_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=True, index=True)
    modulo: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    accion: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resumen: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    metadata_evento: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, index=True)

    usuario: Mapped[Optional[Usuario]] = relationship("Usuario", back_populates="eventos_actividad")
    informe: Mapped[Optional[Informe]] = relationship("Informe")
    proyecto: Mapped[Optional["ProyectoIA"]] = relationship("ProyectoIA")

    __table_args__ = (
        Index("ix_activity_events_modulo_accion_fecha", "modulo", "accion", "creado_en"),
    )


class AnalysisJob(Base):
    """Trabajo persistente de analisis. Permite cola secuencial y notificacion al finalizar."""

    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), nullable=False, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="pendiente")  # pendiente | procesando | finalizado | error
    modelos: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    notify_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resultado: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    notificacion_estado: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    notificacion_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    iniciado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    finalizado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    informe: Mapped[Informe] = relationship("Informe", back_populates="trabajos_analisis")
    usuario: Mapped[Optional[Usuario]] = relationship("Usuario", back_populates="trabajos_analisis")

    @property
    def progreso(self) -> list[dict[str, Any]]:
        """Eventos verificables producidos durante el análisis.

        Se guardan dentro de ``resultado`` para mantener compatibilidad con los
        trabajos históricos sin agregar una tabla o una migración solo para la
        presentación del progreso.
        """
        resultado = self.resultado or {}
        progreso = resultado.get("_progreso", []) if isinstance(resultado, dict) else []
        return progreso if isinstance(progreso, list) else []

    @property
    def metricas(self) -> dict[str, Any]:
        resultado = self.resultado or {}
        metricas = resultado.get("_metricas", {}) if isinstance(resultado, dict) else {}
        return metricas if isinstance(metricas, dict) else {}

    @property
    def version_analisis(self) -> Optional[str]:
        resultado = self.resultado or {}
        valor = resultado.get("_version_analisis") if isinstance(resultado, dict) else None
        return str(valor) if valor else None

    __table_args__ = (
        Index("ix_analysis_jobs_estado_cola", "estado", "creado_en", "id"),
    )


class ProyectoIA(Base):
    """Proyecto individual de aplicacion responsable de IA desarrollado con acompanamiento de IA."""

    __tablename__ = "proyectos_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False, index=True)
    titulo: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    organismo_area: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    situacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="en_proceso")
    entrega_final: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retro_docente: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, onupdate=now)

    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="proyectos_ia")
    mensajes: Mapped[list[MensajeProyectoIA]] = relationship(
        "MensajeProyectoIA",
        back_populates="proyecto",
        cascade="all, delete-orphan",
        order_by="MensajeProyectoIA.creado_en.asc(), MensajeProyectoIA.id.asc()",
    )
    votos_recibidos: Mapped[list["VotoProyectoIA"]] = relationship("VotoProyectoIA", back_populates="proyecto")
    evaluaciones_certificacion: Mapped[list["EvaluacionCertificacion"]] = relationship(
        "EvaluacionCertificacion", back_populates="proyecto"
    )

    __table_args__ = (
        Index("ix_proyectos_ia_estado_actualizado", "estado", "actualizado_en"),
    )


class MensajeProyectoIA(Base):
    """Mensaje trazable dentro del trabajo individual: participante, IA o docente."""

    __tablename__ = "mensajes_proyecto_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=False, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    remitente: Mapped[str] = mapped_column(String(30), nullable=False)  # participante | ia | docente
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, index=True)

    proyecto: Mapped[ProyectoIA] = relationship("ProyectoIA", back_populates="mensajes")
    usuario: Mapped[Optional[Usuario]] = relationship("Usuario", back_populates="mensajes_proyecto_ia")


class VotoProyectoIA(Base):
    """Voto justificado de un participante por un proyecto de otro companero."""

    __tablename__ = "votos_proyecto_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades_votacion.id"), nullable=False, default=1, index=True)
    proyecto_id: Mapped[int] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    justificacion: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, onupdate=now)

    proyecto: Mapped[ProyectoIA] = relationship("ProyectoIA", back_populates="votos_recibidos")
    usuario: Mapped[Usuario] = relationship("Usuario", back_populates="votos_proyecto_ia")

    __table_args__ = (
        UniqueConstraint("actividad_id", "usuario_id", name="uq_voto_actividad_usuario"),
        Index("ix_votos_proyecto_ia_proyecto_fecha", "proyecto_id", "actualizado_en"),
    )


class VotoSegundaVuelta(Base):
    """Preferencia justificada entre finalistas de una actividad pedagógica."""

    __tablename__ = "votos_segunda_vuelta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades_votacion.id"), nullable=False, default=1, index=True)
    justificacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proyecto_id: Mapped[int] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, onupdate=now)

    proyecto: Mapped[ProyectoIA] = relationship("ProyectoIA")
    usuario: Mapped[Usuario] = relationship("Usuario")

    __table_args__ = (
        UniqueConstraint("actividad_id", "usuario_id", name="uq_voto_segunda_actividad_usuario"),
        Index("ix_votos_segunda_vuelta_proyecto_fecha", "proyecto_id", "actualizado_en"),
    )


class RegistroMonitoreo(Base):
    """Seguimiento de la implementacion real de un proyecto de Incubadora: avances, riesgos, decisiones y aprendizajes."""

    __tablename__ = "registros_monitoreo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=False, index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # avance | riesgo | decision | indicador | aprendizaje
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="abierto")  # abierto | en_curso | resuelto | descartado
    valor_indicador: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # solo para tipo=indicador
    metadata_evento: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, index=True)

    proyecto: Mapped["ProyectoIA"] = relationship("ProyectoIA")
    usuario: Mapped[Optional[Usuario]] = relationship("Usuario")

    __table_args__ = (
        Index("ix_registros_monitoreo_proyecto_tipo", "proyecto_id", "tipo"),
    )


class VersionProtocolo(Base):
    """Versión inmutable de un protocolo de revisión y emisión de sellos."""

    __tablename__ = "versiones_protocolo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_objeto: Mapped[str] = mapped_column(String(30), nullable=False)  # informe | proyecto_ia
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    model_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    matriz_lentes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    controles: Mapped[list["DefinicionControl"]] = relationship(
        "DefinicionControl", back_populates="protocolo", order_by="DefinicionControl.orden"
    )
    evaluaciones: Mapped[list["EvaluacionCertificacion"]] = relationship(
        "EvaluacionCertificacion", back_populates="protocolo"
    )

    __table_args__ = (
        UniqueConstraint("codigo", "version", name="uq_versiones_protocolo_codigo_version"),
        CheckConstraint("tipo_objeto IN ('informe', 'proyecto_ia')", name="ck_protocolo_tipo_objeto"),
    )


class DefinicionControl(Base):
    """Control estable perteneciente a una versión concreta del protocolo."""

    __tablename__ = "definiciones_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocolo_id: Mapped[int] = mapped_column(Integer, ForeignKey("versiones_protocolo.id"), nullable=False, index=True)
    codigo: Mapped[str] = mapped_column(String(40), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    lente: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    obligatorio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criticidad: Mapped[str] = mapped_column(String(20), nullable=False, default="media")
    condicion_aplicabilidad: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    evidencia_requerida: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    protocolo: Mapped[VersionProtocolo] = relationship("VersionProtocolo", back_populates="controles")
    resultados: Mapped[list["ResultadoControl"]] = relationship("ResultadoControl", back_populates="control")

    __table_args__ = (
        UniqueConstraint("protocolo_id", "codigo", name="uq_definiciones_control_protocolo_codigo"),
        CheckConstraint("criticidad IN ('baja', 'media', 'alta', 'critica')", name="ck_control_criticidad"),
    )


class EvaluacionCertificacion(Base):
    """Instancia trazable de aplicación de un protocolo sobre un objeto."""

    __tablename__ = "evaluaciones_certificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocolo_id: Mapped[int] = mapped_column(Integer, ForeignKey("versiones_protocolo.id"), nullable=False, index=True)
    informe_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("informes.id"), nullable=True, index=True)
    proyecto_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("proyectos_ia.id"), nullable=True, index=True)
    creado_por_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="en_revision")
    hash_objeto: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_objeto: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifiesto_modelos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    conclusion_r1: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    fundamento_conclusion_r1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    reevaluado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    protocolo: Mapped[VersionProtocolo] = relationship("VersionProtocolo", back_populates="evaluaciones")
    informe: Mapped[Optional[Informe]] = relationship("Informe", back_populates="evaluaciones_certificacion")
    proyecto: Mapped[Optional[ProyectoIA]] = relationship("ProyectoIA", back_populates="evaluaciones_certificacion")
    creado_por: Mapped[Usuario] = relationship(
        "Usuario", foreign_keys=[creado_por_id], back_populates="evaluaciones_certificacion"
    )
    resultados: Mapped[list["ResultadoControl"]] = relationship(
        "ResultadoControl",
        back_populates="evaluacion",
        cascade="all, delete-orphan",
        order_by="ResultadoControl.id",
    )
    sello: Mapped[Optional["SelloCertificacion"]] = relationship(
        "SelloCertificacion", back_populates="evaluacion", uselist=False
    )

    __table_args__ = (
        CheckConstraint(
            "(informe_id IS NOT NULL AND proyecto_id IS NULL) OR "
            "(informe_id IS NULL AND proyecto_id IS NOT NULL)",
            name="ck_evaluacion_un_objeto",
        ),
        CheckConstraint(
            "estado IN ('en_revision', 'con_observaciones', 'lista_para_emision', 'sellada', 'reemplazada')",
            name="ck_evaluacion_estado",
        ),
    )


class ResultadoControl(Base):
    """Resultado revisable de un control; conserva acción y reevaluación."""

    __tablename__ = "resultados_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluacion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluaciones_certificacion.id"), nullable=False, index=True
    )
    control_id: Mapped[int] = mapped_column(Integer, ForeignKey("definiciones_control.id"), nullable=False, index=True)
    aplica: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    justificacion_aplicabilidad: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="no_evaluable")
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accion_requerida: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revisado_por_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    reevaluado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    evaluacion: Mapped[EvaluacionCertificacion] = relationship("EvaluacionCertificacion", back_populates="resultados")
    control: Mapped[DefinicionControl] = relationship("DefinicionControl", back_populates="resultados")
    revisado_por: Mapped[Optional[Usuario]] = relationship("Usuario", foreign_keys=[revisado_por_id])
    evidencias: Mapped[list["EvidenciaControl"]] = relationship(
        "EvidenciaControl", back_populates="resultado", cascade="all, delete-orphan"
    )
    historial: Mapped[list["HistorialResultadoControl"]] = relationship(
        "HistorialResultadoControl", back_populates="resultado", cascade="all, delete-orphan",
        order_by="HistorialResultadoControl.id",
    )

    __table_args__ = (
        UniqueConstraint("evaluacion_id", "control_id", name="uq_resultado_evaluacion_control"),
        CheckConstraint("estado IN ('conforme', 'observado', 'no_evaluable')", name="ck_resultado_estado"),
    )


class EvidenciaControl(Base):
    """Evidencia aportada para sostener un resultado de control."""

    __tablename__ = "evidencias_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resultado_id: Mapped[int] = mapped_column(Integer, ForeignKey("resultados_control.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, default="nota")
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    referencia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_evidencia: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    agregado_por_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    resultado: Mapped[ResultadoControl] = relationship("ResultadoControl", back_populates="evidencias")
    agregado_por: Mapped[Usuario] = relationship("Usuario", foreign_keys=[agregado_por_id])


class HistorialResultadoControl(Base):
    """Registro append-only de cada revisión de un control."""

    __tablename__ = "historial_resultados_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resultado_id: Mapped[int] = mapped_column(Integer, ForeignKey("resultados_control.id"), nullable=False, index=True)
    modificado_por_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    estado_anterior: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    estado_nuevo: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    resultado: Mapped[ResultadoControl] = relationship("ResultadoControl", back_populates="historial")
    modificado_por: Mapped[Usuario] = relationship("Usuario", foreign_keys=[modificado_por_id])


class HipotesisExploratoria(Base):
    """Salida de la capa exploratoria (services/exploratorio.py): una hipotesis
    no validada, nunca un hallazgo.

    Deliberadamente sin relacion con EvaluacionCertificacion ni con Hallazgo
    -- ni clave foranea, ni relacion ORM, ni campo de referencia cruzada. Cuelga
    del informe y de nada mas. Tampoco tiene campo de "promocion a hallazgo":
    si alguien quiere convertir una hipotesis en hallazgo, que escriba un
    hallazgo nuevo a mano, con su propia evidencia."""

    __tablename__ = "hipotesis_exploratorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(Integer, ForeignKey("informes.id"), nullable=False, index=True)
    tipo_pista: Mapped[str] = mapped_column(String(40), nullable=False)  # preguntas_no_formuladas | correlaciones_no_declaradas
    texto_hipotesis: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str] = mapped_column(String(80), nullable=False)
    version_modelo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="HIPOTESIS_NO_VALIDADA")
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)

    __table_args__ = (
        CheckConstraint("estado = 'HIPOTESIS_NO_VALIDADA'", name="ck_hipotesis_estado_unico"),
    )


class SelloCertificacion(Base):
    """Constancia emitida sobre un snapshot inmutable y públicamente verificable."""

    __tablename__ = "sellos_certificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluacion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evaluaciones_certificacion.id"), unique=True, nullable=False
    )
    identificador_publico: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="vigente")
    hash_objeto: Mapped[str] = mapped_column(String(64), nullable=False)
    resumen_alcance: Mapped[str] = mapped_column(Text, nullable=False)
    limitaciones: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    emitido_por_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    emitido_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now)
    revocado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    motivo_revocacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revocado_por_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True)

    evaluacion: Mapped[EvaluacionCertificacion] = relationship("EvaluacionCertificacion", back_populates="sello")
    emitido_por: Mapped[Usuario] = relationship("Usuario", foreign_keys=[emitido_por_id])
    revocado_por: Mapped[Optional[Usuario]] = relationship("Usuario", foreign_keys=[revocado_por_id])

    __table_args__ = (
        CheckConstraint("estado IN ('vigente', 'reemplazado', 'suspendido', 'revocado')", name="ck_sello_estado"),
    )


class EjecucionAnalisis(Base):
    """Manifiesto inmutable de una corrida, independiente del comprobante y de B-1."""
    __tablename__ = "ejecuciones_analisis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(ForeignKey("informes.id"), nullable=False, index=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, nullable=False)
    dominio: Mapped[str] = mapped_column(String(50), nullable=False)
    version_aplicacion: Mapped[str] = mapped_column(String(30), nullable=False)
    version_protocolo: Mapped[str] = mapped_column(String(60), nullable=False)
    version_codigo: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifiesto: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    requiere_reevaluacion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    incidencias: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)


class CalibrationRun(Base):
    """Contraste registrado de casos; los resultados externos no se inventan."""
    __tablename__ = "corridas_calibracion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, nullable=False)
    responsable_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    dominio: Mapped[str] = mapped_column(String(50), nullable=False)
    version_protocolo: Mapped[str] = mapped_column(String(60), nullable=False)
    version_codigo: Mapped[str] = mapped_column(String(64), nullable=False)
    control: Mapped[str] = mapped_column(String(80), nullable=False)
    version_control: Mapped[str] = mapped_column(String(64), nullable=False)
    bateria: Mapped[str] = mapped_column(String(200), nullable=False)
    casos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    tolerancia: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    categoria_incidencia: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    desde: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    hasta: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    observaciones: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (
        CheckConstraint("estado IN ('aprobada', 'fallida')", name="ck_calibracion_estado"),
        CheckConstraint("tolerancia >= 0", name="ck_calibracion_tolerancia"),
    )


class CasoBiblioteca(Base):
    """Caso de un cuadro real: propuesto y luego revisado antes de contar como antecedente."""

    __tablename__ = "casos_biblioteca"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    informe_id: Mapped[int] = mapped_column(ForeignKey("informes.id", ondelete="CASCADE"), nullable=False, index=True)
    propuesto_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    revisado_por_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    hallazgo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hallazgos.id", ondelete="SET NULL"), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    archivo: Mapped[str] = mapped_column(String(250), nullable=False)
    hoja: Mapped[str] = mapped_column(String(200), nullable=False)
    bloque: Mapped[int] = mapped_column(Integer, nullable=False)
    control: Mapped[str] = mapped_column(String(80), nullable=False)
    resultado: Mapped[str] = mapped_column(String(30), nullable=False)
    fundamento: Mapped[str] = mapped_column(Text, nullable=False)
    fuente_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    fuente_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    grupo_fuente: Mapped[str] = mapped_column(String(64), nullable=False)
    perfil_cuadro: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidencia: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version_codigo: Mapped[str] = mapped_column(String(64), nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(), default=now, nullable=False)
    decidido_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(), nullable=True)
    __table_args__ = (
        CheckConstraint("estado IN ('pendiente', 'aprobado', 'rechazado')", name="ck_caso_biblioteca_estado"),
        CheckConstraint("resultado IN ('senal_justificada', 'senal_infundada', 'omision', 'sin_senal_revisado')", name="ck_caso_biblioteca_resultado"),
    )


class ActividadVotacion(Base):
    """Preferencia pedagógica por cohorte, separada de R-1 y de la evaluación docente."""
    __tablename__ = "actividades_votacion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cohorte: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primera_vuelta_abierta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    segunda_vuelta_abierta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fecha_apertura_1: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    fecha_cierre_1: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    fecha_apertura_2: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    fecha_cierre_2: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    proyectos_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    finalistas: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    grupo: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)  # grupo de cursada que vota (0.10.62)
    actualizado_por_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (
        # Una sola votación activa por grupo (0.10.62); sin grupo cuenta como un grupo más.
        Index("uq_actividad_votacion_activa_grupo", text("coalesce(grupo, '')"), unique=True,
              postgresql_where=activa.is_(True), sqlite_where=activa.is_(True)),
    )


class SugerenciaPantalla(Base):
    """Opiniones de uso identificadas; independientes de las entregas y de la IA."""
    __tablename__ = "sugerencias_pantalla"
    __table_args__ = (UniqueConstraint("usuario_id", "solicitud_id", name="uq_sugerencia_solicitud"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    pantalla: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    solicitud_id: Mapped[str] = mapped_column(String(36), nullable=False)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=now, nullable=False)
