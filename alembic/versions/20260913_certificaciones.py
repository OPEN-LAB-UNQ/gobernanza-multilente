"""motor común de protocolos, controles, evidencias y sellos"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260913_certificaciones"
down_revision: Union[str, Sequence[str], None] = "20260912_votos_segunda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


B1_CONTROLES = [
    ("B1-01", "Objeto y alcance identificados", "Define qué se revisó, para qué decisión y con qué alcance.", None, True, "alta"),
    ("B1-02", "Integridad y suficiencia", "Comprueba que el material necesario esté presente y permite declarar faltantes.", None, True, "critica"),
    ("B1-03", "Trazabilidad de fuentes", "Vincula afirmaciones y señales con fuentes, ubicaciones y evidencia reproducible.", None, True, "alta"),
    ("B1-04", "Consistencia interna", "Busca contradicciones, reglas explícitas incumplidas y tensiones dentro del objeto.", "ajedrecista", True, "alta"),
    ("B1-05", "Coherencia temporal", "Revisa cortes de serie, cambios de criterio y comparabilidad entre períodos.", "cronista", True, "alta"),
    ("B1-06", "Cálculos reproducibles", "Revisa operaciones y método mediante planes de cálculo seguros.", "matematico", True, "alta"),
    ("B1-07", "Relaciones y contraste", "Distingue consistencia interna, contraste autorizado y análisis interdocumental.", "orquesta", True, "media"),
    ("B1-08", "Cobertura y límites", "Explicita qué fue revisado, qué no y por qué.", "conciliador", True, "alta"),
    ("B1-09", "Corrección y reevaluación", "Registra observación, acción, evidencia aportada y resultado de la nueva revisión.", None, True, "alta"),
    ("B1-10", "Decisión humana", "Una persona autorizada confirma si el objeto puede continuar a la instancia correspondiente.", None, True, "critica"),
]

R1_CONTROLES = [
    ("R1-01", "Problema público definido", "Describe el problema, población, proceso y resultado público esperado.", True, "alta"),
    ("R1-02", "Necesidad real de IA", "Justifica la IA frente a alternativas más simples y admite concluir que no corresponde usarla.", True, "critica"),
    ("R1-03", "Datos y legitimidad de uso", "Identifica datos, calidad, procedencia, permisos y límites de utilización.", True, "critica"),
    ("R1-04", "Roles y responsabilidades", "Asigna responsables técnicos, funcionales, institucionales y de respuesta ante incidentes.", True, "alta"),
    ("R1-05", "Supervisión humana", "Define intervención, revisión, posibilidad de corrección y autoridad decisoria humana.", True, "critica"),
    ("R1-06", "Riesgos y poblaciones afectadas", "Registra daños plausibles, grupos afectados y medidas de mitigación.", True, "critica"),
    ("R1-07", "Privacidad", "Define minimización, retención, acceso y tratamiento de datos personales.", True, "critica"),
    ("R1-08", "Seguridad", "Establece controles de acceso, registros, respuesta y continuidad operativa.", True, "critica"),
    ("R1-09", "Métricas y evaluación", "Define desempeño, impacto, umbrales, línea de base y criterio de éxito o detención.", True, "alta"),
    ("R1-10", "Incidentes y escalamiento", "Describe detección, comunicación, responsables, tiempos y decisiones excepcionales.", True, "alta"),
    ("R1-11", "Comunicación a usuarios", "Explica cuándo interviene IA, sus límites y los canales de revisión o reclamo.", True, "alta"),
    ("R1-12", "Mantenimiento y retiro", "Define monitoreo, actualizaciones, reevaluación, reversibilidad y salida ordenada.", True, "alta"),
    ("R1-13", "Condiciones organizacionales", "Incluye capacidades, recursos humanos, formación y gestión del cambio.", True, "alta"),
    ("R1-14", "Modelos abiertos o autoalojados", "Cuando aplica, define jurisdicción, logs, retención, excepciones y operación responsable.", False, "alta"),
]


def upgrade() -> None:
    op.create_table(
        "versiones_protocolo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("tipo_objeto", sa.String(30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("codigo", "version", name="uq_versiones_protocolo_codigo_version"),
        sa.CheckConstraint("tipo_objeto IN ('informe', 'proyecto_ia')", name="ck_protocolo_tipo_objeto"),
    )
    op.create_table(
        "definiciones_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("protocolo_id", sa.Integer(), sa.ForeignKey("versiones_protocolo.id"), nullable=False),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("lente", sa.String(30), nullable=True),
        sa.Column("obligatorio", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criticidad", sa.String(20), nullable=False, server_default="media"),
        sa.Column("condicion_aplicabilidad", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidencia_requerida", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("protocolo_id", "codigo", name="uq_definiciones_control_protocolo_codigo"),
        sa.CheckConstraint("criticidad IN ('baja', 'media', 'alta', 'critica')", name="ck_control_criticidad"),
    )
    op.create_index("ix_definiciones_control_protocolo_id", "definiciones_control", ["protocolo_id"])
    op.create_table(
        "evaluaciones_certificacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("protocolo_id", sa.Integer(), sa.ForeignKey("versiones_protocolo.id"), nullable=False),
        sa.Column("informe_id", sa.Integer(), sa.ForeignKey("informes.id"), nullable=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=True),
        sa.Column("creado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False, server_default="en_revision"),
        sa.Column("hash_objeto", sa.String(64), nullable=False),
        sa.Column("snapshot_objeto", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("reevaluado_en", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(informe_id IS NOT NULL AND proyecto_id IS NULL) OR (informe_id IS NULL AND proyecto_id IS NOT NULL)",
            name="ck_evaluacion_un_objeto",
        ),
        sa.CheckConstraint(
            "estado IN ('en_revision', 'con_observaciones', 'lista_para_emision', 'sellada', 'reemplazada')",
            name="ck_evaluacion_estado",
        ),
    )
    for column in ("protocolo_id", "informe_id", "proyecto_id", "creado_por_id"):
        op.create_index(f"ix_evaluaciones_certificacion_{column}", "evaluaciones_certificacion", [column])
    op.create_table(
        "resultados_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluacion_id", sa.Integer(), sa.ForeignKey("evaluaciones_certificacion.id"), nullable=False),
        sa.Column("control_id", sa.Integer(), sa.ForeignKey("definiciones_control.id"), nullable=False),
        sa.Column("aplica", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("justificacion_aplicabilidad", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(30), nullable=False, server_default="no_evaluable"),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("accion_requerida", sa.Text(), nullable=True),
        sa.Column("revisado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("reevaluado_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("evaluacion_id", "control_id", name="uq_resultado_evaluacion_control"),
        sa.CheckConstraint("estado IN ('conforme', 'observado', 'no_evaluable')", name="ck_resultado_estado"),
    )
    op.create_index("ix_resultados_control_evaluacion_id", "resultados_control", ["evaluacion_id"])
    op.create_index("ix_resultados_control_control_id", "resultados_control", ["control_id"])
    op.create_table(
        "evidencias_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resultado_id", sa.Integer(), sa.ForeignKey("resultados_control.id"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False, server_default="nota"),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("referencia", sa.Text(), nullable=True),
        sa.Column("metadata_evidencia", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("agregado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_evidencias_control_resultado_id", "evidencias_control", ["resultado_id"])
    op.create_table(
        "sellos_certificacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluacion_id", sa.Integer(), sa.ForeignKey("evaluaciones_certificacion.id"), unique=True, nullable=False),
        sa.Column("identificador_publico", sa.String(36), unique=True, nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="vigente"),
        sa.Column("hash_objeto", sa.String(64), nullable=False),
        sa.Column("resumen_alcance", sa.Text(), nullable=False),
        sa.Column("limitaciones", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("emitido_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("emitido_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revocado_en", sa.DateTime(), nullable=True),
        sa.Column("motivo_revocacion", sa.Text(), nullable=True),
        sa.CheckConstraint("estado IN ('vigente', 'reemplazado', 'suspendido', 'revocado')", name="ck_sello_estado"),
    )
    op.create_index("ix_sellos_certificacion_identificador_publico", "sellos_certificacion", ["identificador_publico"], unique=True)

    protocolos = sa.table(
        "versiones_protocolo",
        sa.column("id", sa.Integer()),
        sa.column("codigo", sa.String()),
        sa.column("version", sa.String()),
        sa.column("nombre", sa.String()),
        sa.column("tipo_objeto", sa.String()),
        sa.column("descripcion", sa.Text()),
        sa.column("activo", sa.Boolean()),
    )
    op.bulk_insert(protocolos, [
        {
            "id": 1,
            "codigo": "B-1",
            "version": "1.0",
            "nombre": "Gobernanza Multilente B-1",
            "tipo_objeto": "informe",
            "descripcion": "Constancia de revisión documental bajo protocolo multilente, con evidencia y decisión humana.",
            "activo": True,
        },
        {
            "id": 2,
            "codigo": "R-1",
            "version": "1.0",
            "nombre": "Preparación para IA Responsable R-1",
            "tipo_objeto": "proyecto_ia",
            "descripcion": "Constancia de preparación de un proyecto de IA para continuar hacia la instancia humana correspondiente.",
            "activo": True,
        },
    ])
    op.execute(
        "SELECT setval(pg_get_serial_sequence('versiones_protocolo', 'id'), "
        "(SELECT MAX(id) FROM versiones_protocolo))"
    )
    controles = sa.table(
        "definiciones_control",
        sa.column("protocolo_id", sa.Integer()),
        sa.column("codigo", sa.String()),
        sa.column("nombre", sa.String()),
        sa.column("descripcion", sa.Text()),
        sa.column("lente", sa.String()),
        sa.column("obligatorio", sa.Boolean()),
        sa.column("criticidad", sa.String()),
        sa.column("orden", sa.Integer()),
    )
    filas = [
        {
            "protocolo_id": 1,
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": descripcion,
            "lente": lente,
            "obligatorio": obligatorio,
            "criticidad": criticidad,
            "orden": orden,
        }
        for orden, (codigo, nombre, descripcion, lente, obligatorio, criticidad) in enumerate(B1_CONTROLES, 1)
    ]
    filas.extend(
        {
            "protocolo_id": 2,
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": descripcion,
            "lente": None,
            "obligatorio": obligatorio,
            "criticidad": criticidad,
            "orden": orden,
        }
        for orden, (codigo, nombre, descripcion, obligatorio, criticidad) in enumerate(R1_CONTROLES, 1)
    )
    op.bulk_insert(controles, filas)


def downgrade() -> None:
    op.drop_index("ix_sellos_certificacion_identificador_publico", table_name="sellos_certificacion")
    op.drop_table("sellos_certificacion")
    op.drop_index("ix_evidencias_control_resultado_id", table_name="evidencias_control")
    op.drop_table("evidencias_control")
    op.drop_index("ix_resultados_control_control_id", table_name="resultados_control")
    op.drop_index("ix_resultados_control_evaluacion_id", table_name="resultados_control")
    op.drop_table("resultados_control")
    for column in ("creado_por_id", "proyecto_id", "informe_id", "protocolo_id"):
        op.drop_index(f"ix_evaluaciones_certificacion_{column}", table_name="evaluaciones_certificacion")
    op.drop_table("evaluaciones_certificacion")
    op.drop_index("ix_definiciones_control_protocolo_id", table_name="definiciones_control")
    op.drop_table("definiciones_control")
    op.drop_table("versiones_protocolo")
