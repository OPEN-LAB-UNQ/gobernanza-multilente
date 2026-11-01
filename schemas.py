import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from enums import Lente, Severidad


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    email_notificaciones: Optional[str] = None
    nombre: str
    rol: str
    activo: bool = True
    grupo: Optional[str] = None


class UsuarioEstadoUpdate(BaseModel):
    activo: bool


class CambioPassword(BaseModel):
    actual: str
    nueva: str


class UsuarioCreate(BaseModel):
    email: str
    email_notificaciones: Optional[str] = None
    nombre: str
    password: str
    rol: str = "analista"
    grupo: Optional[str] = Field(default=None, max_length=60)  # grupo de cursada; vacío es el grupo por defecto


class UsuarioNotificacionesUpdate(BaseModel):
    email_notificaciones: Optional[str] = None


class AnalysisJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    informe_id: int
    usuario_id: Optional[int] = None
    estado: str
    modelos: Optional[list[str]] = None
    notify_email: Optional[str] = None
    error: Optional[str] = None
    notificacion_estado: Optional[str] = None
    notificacion_error: Optional[str] = None
    progreso: list[dict[str, Any]] = Field(default_factory=list)
    metricas: dict[str, Any] = Field(default_factory=dict)
    version_analisis: Optional[str] = None
    creado_en: datetime.datetime
    iniciado_en: Optional[datetime.datetime] = None
    finalizado_en: Optional[datetime.datetime] = None


class EnqueueAnalisisOut(BaseModel):
    informe_id: int
    job: AnalysisJobOut


class InterpretacionPreviaOut(BaseModel):
    informe_id: int
    estado: Literal["interpretando", "pendiente_confirmacion"] = "pendiente_confirmacion"
    interpretacion: dict[str, Any]
    job: Optional[AnalysisJobOut] = None


class AreaCreate(BaseModel):
    nombre: str
    codigo: str
    contacto_email: Optional[str] = None


class AreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    codigo: str
    contacto_email: Optional[str] = None


class ContextoValidacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condiciones_criticas: list[str] = Field(default_factory=list, max_length=9)
    campos_requeridos: list[str] = Field(default_factory=list, max_length=100)
    esquema_esperado: Optional[dict[str, Any]] = None

    @field_validator("condiciones_criticas")
    @classmethod
    def dimensiones_validas(cls, valor):
        from services.validez import DIMENSIONES
        if set(valor) - set(DIMENSIONES):
            raise ValueError("condición de validez desconocida")
        return valor

    @field_validator("esquema_esperado")
    @classmethod
    def esquema_valido(cls, valor):
        if valor is not None:
            columnas = valor.get("columnas")
            if not isinstance(columnas, dict) or not columnas or len(columnas) > 200:
                raise ValueError("el esquema debe declarar columnas y sus tipos")
            for tipos in columnas.values():
                if not isinstance(tipos, list) or not tipos or set(tipos) - {"numero", "texto", "booleano", "nulo", "estructura"}:
                    raise ValueError("tipos de esquema inválidos")
        return valor


class InformeCreate(BaseModel):
    area_id: int
    periodo: str
    dominio: str = "general"
    modo: str = "intraarea"
    datos: list[dict[str, Any]]
    creado_por: Optional[str] = None
    contexto_validacion: ContextoValidacion = Field(default_factory=ContextoValidacion)
    informe_anterior_id: Optional[int] = None
    # «publico» (por defecto) u «organizacion»: define qué reglas se aplican (services/ambito.py).
    ambito: Literal["publico", "organizacion"] = "publico"


class InformeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    area_id: int
    periodo: str
    dominio: str
    modo: str
    creado_en: datetime.datetime
    saneamiento: Optional[dict] = None


class InformeResumenOut(BaseModel):
    """Fila de historial: lo minimo para decidir cual informe abrir sin
    entrar a cada uno. Se arma a mano en el router (no via from_attributes)
    porque combina campos calculados de hallazgos y devolucion."""
    id: int
    area_id: int
    periodo: str
    dominio: str
    modo: str
    creado_en: datetime.datetime
    usuario_id: Optional[int] = None
    creado_por: Optional[str] = None
    n_hallazgos: int
    n_casos: Optional[int] = None
    archivos_origen: list[str] = Field(default_factory=list)
    interpretacion_estado: Optional[str] = None
    severidad_max: Optional[str] = None
    estado_devolucion: Optional[str] = None
    decision_tomada: bool = False
    tipo_decision: Optional[str] = None
    analysis_job_id: Optional[int] = None
    analysis_status: Optional[str] = None
    # «rapida» o «profunda»; un informe anterior a las dos revisiones fue una profunda.
    modo_revision: str = "profunda"
    # Marcado «es una prueba» al cargar: no cuenta para las mediciones.
    es_prueba: bool = False
    # Analizado, de quien mira y sin la pregunta de cierre respondida («¿Corregiste algo del informe?»).
    cierre_pendiente: bool = False


class HallazgoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lente: Lente
    modo: Optional[str] = None
    descripcion: str
    severidad: Severidad
    evidencia: Optional[dict] = None
    tipo_evidencia: Optional[str] = None
    alcance: str = "agregado"
    metodo: Optional[str] = None
    incertidumbre: str = "media"
    estado_validacion: str = "pendiente_decision_humana"
    pregunta_institucional: Optional[str] = None
    resumen_llano: Optional[str] = None
    # Sólo presentación: funciones de Excel en castellano. descripcion y evidencia conservan el original.
    descripcion_es: Optional[str] = None
    pregunta_es: Optional[str] = None
    limites: Optional[dict] = None
    # Qué resultó ser la señal, según quien hizo el informe (la última respuesta) y si quien mira puede responder.
    respuesta: Optional[dict] = None
    puede_responder: bool = False

    @model_validator(mode="after")
    def _resumen_para_hallazgos_anteriores(self):
        # Hallazgos guardados antes de la frase «Qué pasó»: se arma al mostrarlos, sin tocar la base.
        if not self.resumen_llano:
            from services.guardrails import sanitizar_texto
            from services.reportes.lenguaje_llano import resumen_llano

            lente = getattr(self.lente, "value", self.lente)
            self.resumen_llano = sanitizar_texto(resumen_llano({"lente": lente, "evidencia": self.evidencia or {}}))
        from services.reportes.lenguaje_llano import traducir_en_texto

        self.descripcion_es = traducir_en_texto(self.descripcion)
        self.pregunta_es = traducir_en_texto(self.pregunta_institucional) if self.pregunta_institucional else None
        return self


class DevolucionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    informe_id: int
    mensaje: str
    hay_hallazgos: bool
    estado: str = "PENDIENTE"
    cobertura: Optional[dict] = None


class AnalisisOut(BaseModel):
    """Resultado completo de someter un informe al barrido de las lentes disponibles."""

    informe_id: int
    hallazgos: list[HallazgoOut]
    coincidencias: list[str]
    divergencias: list[str]
    hallazgos_singulares: list[dict]
    modelos_consultados: list[dict] = Field(default_factory=list)
    convergencia_multilente: list[dict] = Field(default_factory=list)
    devolucion: DevolucionOut


class DecisionCreate(BaseModel):
    escalar: bool = False
    tipo_decision: Optional[str] = None
    pregunta_institucional: Optional[str] = None
    hallazgo_ids: list[int] = Field(default_factory=list)
    comentario: Optional[str] = None
    decidido_por: Optional[str] = None
    areas_destino_ids: list[int] = Field(default_factory=list)


class DocumentoEnrutamientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    area_destino_id: int
    contenido: str


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    escalar: bool
    tipo_decision: str = "sin_escalamiento"
    pregunta_institucional: Optional[str] = None
    hallazgo_ids: list[int] = Field(default_factory=list)
    comentario: Optional[str] = None

    @field_validator("hallazgo_ids", mode="before")
    @classmethod
    def _hallazgo_ids_compat(cls, value):
        return [] if value is None else value
    decidido_por: Optional[str] = None
    documentos: list[DocumentoEnrutamientoOut] = Field(default_factory=list)


class InformeDetalleOut(BaseModel):
    """Estado completo y trazable de un informe: para reabrirlo sin re-analizarlo."""

    id: int
    area_id: int
    periodo: str
    dominio: str
    modo: str
    creado_en: datetime.datetime
    n_filas: int
    saneamiento: Optional[dict] = None
    hallazgos: list[HallazgoOut] = Field(default_factory=list)
    coincidencias: list[str] = Field(default_factory=list)
    divergencias: list[str] = Field(default_factory=list)
    hallazgos_singulares: list[dict] = Field(default_factory=list)
    modelos_consultados: list[dict] = Field(default_factory=list)
    convergencia_multilente: list[dict] = Field(default_factory=list)
    devolucion: Optional[DevolucionOut] = None
    decision: Optional[DecisionOut] = None
    job: Optional[AnalysisJobOut] = None
    evaluacion_piloto: Optional[dict[str, Any]] = None
    # Pregunta de cierre del informe: {puede_responder, pendiente, es_prueba, respuesta}.
    cierre_informe: Optional[dict[str, Any]] = None
    revision: dict = Field(default_factory=dict)


class DefinicionControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    descripcion: str
    lente: Optional[str] = None
    obligatorio: bool
    criticidad: str
    condicion_aplicabilidad: Optional[dict[str, Any]] = None
    evidencia_requerida: Optional[dict[str, Any]] = None
    orden: int


class VersionProtocoloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    version: str
    nombre: str
    tipo_objeto: str
    descripcion: str
    activo: bool
    model_policy: dict[str, Any] = Field(default_factory=dict)
    matriz_lentes: list[dict[str, Any]] = Field(default_factory=list)
    controles: list[DefinicionControlOut] = Field(default_factory=list)


class EvidenciaControlCreate(BaseModel):
    tipo: str = Field(default="nota", min_length=1, max_length=40)
    descripcion: str = Field(min_length=3, max_length=5000)
    referencia: Optional[str] = Field(default=None, max_length=4000)
    metadata_evidencia: Optional[dict[str, Any]] = None


class EvidenciaControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    descripcion: str
    referencia: Optional[str] = None
    metadata_evidencia: Optional[dict[str, Any]] = None
    agregado_por_id: int
    creado_en: datetime.datetime


class ResultadoControlUpdate(BaseModel):
    aplica: bool = True
    justificacion_aplicabilidad: Optional[str] = Field(default=None, max_length=5000)
    estado: str = Field(pattern="^(conforme|observado|no_evaluable)$")
    observacion: Optional[str] = Field(default=None, max_length=10000)
    accion_requerida: Optional[str] = Field(default=None, max_length=10000)


class HistorialResultadoControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    modificado_por_id: int
    estado_anterior: dict[str, Any]
    estado_nuevo: dict[str, Any]
    creado_en: datetime.datetime


class ResultadoControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    aplica: bool
    justificacion_aplicabilidad: Optional[str] = None
    estado: str
    observacion: Optional[str] = None
    accion_requerida: Optional[str] = None
    revisado_por_id: Optional[int] = None
    creado_en: datetime.datetime
    actualizado_en: datetime.datetime
    reevaluado_en: Optional[datetime.datetime] = None
    control: DefinicionControlOut
    evidencias: list[EvidenciaControlOut] = Field(default_factory=list)
    historial: list[HistorialResultadoControlOut] = Field(default_factory=list)


class SelloCertificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    identificador_publico: str
    estado: str
    hash_objeto: str
    resumen_alcance: str
    limitaciones: list[str] = Field(default_factory=list)
    emitido_por_id: int
    emitido_en: datetime.datetime
    revocado_en: Optional[datetime.datetime] = None
    motivo_revocacion: Optional[str] = None
    revocado_por_id: Optional[int] = None


class EvaluacionCertificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    informe_id: Optional[int] = None
    proyecto_id: Optional[int] = None
    creado_por_id: int
    estado: str
    hash_objeto: str
    snapshot_objeto: dict[str, Any]
    creado_en: datetime.datetime
    actualizado_en: datetime.datetime
    reevaluado_en: Optional[datetime.datetime] = None
    protocolo: VersionProtocoloOut
    resultados: list[ResultadoControlOut] = Field(default_factory=list)
    sello: Optional[SelloCertificacionOut] = None
    manifiesto_modelos: list[dict[str, Any]] = Field(default_factory=list)
    conclusion_r1: Optional[str] = None
    fundamento_conclusion_r1: Optional[str] = None


class EmisionSelloCreate(BaseModel):
    alcance_del_analisis: str = Field(min_length=20, max_length=5000)
    excluidos_del_analisis: list[str] = Field(default_factory=list, max_length=30)


class RevocacionSelloCreate(BaseModel):
    motivo: str = Field(min_length=10, max_length=5000)


class ConclusionR1Update(BaseModel):
    conclusion: str = Field(pattern="^(ia_justificada|automatizacion_simple|mejora_de_proceso|no_implementar|informacion_insuficiente)$")
    fundamento: str = Field(min_length=20, max_length=10000)


class VerificacionSelloOut(BaseModel):
    identificador_publico: str
    estado: str
    estado_evaluacion_visible: str = "Sellada"
    protocolo: str
    version: str
    tipo_objeto: str
    objeto_id: int
    hash_objeto: str
    alcance_del_analisis: str
    analisis_excluidos: list[str] = Field(default_factory=list)
    resumen_alcance: str
    limitaciones: list[str] = Field(default_factory=list)
    emitido_en: datetime.datetime
    emitido_por: str
    responsables_revision: int = 0
    ultima_revision_en: Optional[datetime.datetime] = None
    revision_emision_separadas: bool = False
    revocado_por: Optional[str] = None
    revocado_en: Optional[datetime.datetime] = None
    motivo_revocacion: Optional[str] = None
    controles_conformes: int
    controles_no_aplicables: int
    controles_totales: int
    lentes: list[dict[str, Any]] = Field(default_factory=list)
    model_policy_cumplida: bool = True
    conclusion_r1: Optional[str] = None
    fundamento_conclusion_r1: Optional[str] = None
    declaracion: str



class ProyectoIAMensajeCreate(BaseModel):
    mensaje: str = Field(min_length=1, max_length=12000)


class ProyectoIAUpdate(BaseModel):
    titulo: Optional[str] = Field(default=None, max_length=220)
    organismo_area: Optional[str] = Field(default=None, max_length=220)
    situacion: Optional[str] = None
    entrega_final: Optional[str] = None
    estado: Optional[str] = Field(default=None, max_length=30)


class ProyectoIADocenteMensajeCreate(BaseModel):
    # El tope real (30.000) lo aplica el router con un mensaje claro en castellano; este
    # techo amplio sólo frena cuerpos desmesurados. Con max_length=30000 acá, pydantic
    # respondía un 422 genérico (en inglés y como lista) que la pantalla no podía explicar,
    # y contaba los espacios del principio y del final que el servidor después descarta.
    mensaje: str = Field(min_length=1, max_length=200_000)


class ProyectoIARetroUpdate(BaseModel):
    retro_docente: Optional[str] = None
    estado: Optional[str] = Field(default=None, max_length=30)


class MensajeProyectoIAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    proyecto_id: int
    usuario_id: Optional[int] = None
    remitente: str
    contenido: str
    creado_en: datetime.datetime


class ProyectoIAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    titulo: Optional[str] = None
    organismo_area: Optional[str] = None
    situacion: Optional[str] = None
    estado: str
    entrega_final: Optional[str] = None
    retro_docente: Optional[str] = None
    creado_en: datetime.datetime
    actualizado_en: datetime.datetime
    mensajes: list[MensajeProyectoIAOut] = Field(default_factory=list)


class ProyectoIAResumenOut(BaseModel):
    id: int
    usuario_id: int
    email: str
    nombre: str
    titulo: Optional[str] = None
    organismo_area: Optional[str] = None
    estado: str
    mensajes_total: int = 0
    mensajes_participante: int = 0
    mensajes_ia: int = 0
    consultas_docente: int = 0
    respuestas_docente: int = 0
    ultimo_movimiento: Optional[datetime.datetime] = None
    entrega_final: bool = False
