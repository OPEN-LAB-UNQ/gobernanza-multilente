"""cierre del checklist maestro: versiones 1.1, historial y revocacion trazable"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from services.lens_matrix import LENS_MATRIX


revision: str = "20260913_checklist_maestro"
down_revision: Union[str, Sequence[str], None] = "20260913_model_policy"
branch_labels = None
depends_on = None


def _crear_version(conn, codigo: str, nombre: str, tipo: str, descripcion: str, policy: dict) -> int:
    return conn.execute(sa.text("""
        INSERT INTO versiones_protocolo
            (codigo, version, nombre, tipo_objeto, descripcion, activo, creado_en, model_policy, matriz_lentes)
        VALUES (:codigo, '1.1', :nombre, :tipo, :descripcion, true, CURRENT_TIMESTAMP,
                CAST(:policy AS jsonb), CAST(:matriz AS jsonb))
        RETURNING id
    """), {
        "codigo": codigo, "nombre": nombre, "tipo": tipo, "descripcion": descripcion,
        "policy": __import__("json").dumps(policy, ensure_ascii=False),
        "matriz": __import__("json").dumps(list(LENS_MATRIX) if codigo == "B-1" else [], ensure_ascii=False),
    }).scalar_one()


def upgrade() -> None:
    op.add_column("interpretaciones_modelo", sa.Column("identificador_version", sa.String(200), nullable=True))
    op.add_column("versiones_protocolo", sa.Column("matriz_lentes", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("evaluaciones_certificacion", sa.Column("conclusion_r1", sa.String(40), nullable=True))
    op.add_column("evaluaciones_certificacion", sa.Column("fundamento_conclusion_r1", sa.Text(), nullable=True))
    op.add_column("sellos_certificacion", sa.Column("revocado_por_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_sello_revocado_por", "sellos_certificacion", "usuarios", ["revocado_por_id"], ["id"])
    op.create_table(
        "historial_resultados_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resultado_id", sa.Integer(), sa.ForeignKey("resultados_control.id"), nullable=False),
        sa.Column("modificado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("estado_anterior", postgresql.JSONB(), nullable=False),
        sa.Column("estado_nuevo", postgresql.JSONB(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_historial_resultados_control_resultado_id", "historial_resultados_control", ["resultado_id"])

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE versiones_protocolo SET activo=false WHERE codigo IN ('B-1','R-1')"))
    policy_b1 = {
        "aplica": True,
        "modelos_habilitados": ["claude", "gpt", "gemini", "deepseek", "renderix", "llama"],
        "modelos_minimos_con_respuesta": 0,
        "controles_que_requieren_ia": [],
        "controles_con_contraste_obligatorio": [],
        "criterio_metodologico": "La IA es apoyo interpretativo opcional. La conformidad se funda en reglas, evidencia y decisión humana; si intervienen modelos, todos quedan en el manifiesto.",
        "configuracion_minima": {"formato_respuesta": "json_estructurado_validado", "entrada": "hallazgos_estructurados_no_microdatos"},
    }
    b1 = _crear_version(conn, "B-1", "Gobernanza Multilente B-1", "informe",
        "Protocolo técnico predecisional con controles obligatorios y condicionales, siete anexos versionados y decisión humana.", policy_b1)
    r1 = _crear_version(conn, "R-1", "Preparación para IA Responsable R-1", "proyecto_ia",
        "Protocolo para decidir responsablemente si corresponde IA, otra automatización, una mejora de proceso o no implementar tecnología.", {"aplica": False, "motivo": "R-1 no exige triangulación de modelos para evaluar la preparación declarada del proyecto."})

    controles_b1 = [
        ("B1-01", "Objeto y alcance identificados", "Define qué se revisó, para qué decisión y con qué alcance.", None, True, "alta"),
        ("B1-02", "Integridad y suficiencia", "Comprueba que el material necesario esté presente y declara faltantes concretos.", None, True, "critica"),
        ("B1-03", "Trazabilidad de fuentes", "Vincula afirmaciones y señales con fuentes, ubicaciones y evidencia reproducible.", None, True, "alta"),
        ("B1-04", "Consistencia interna", "Busca contradicciones y tensiones dentro del objeto.", "ajedrecista", False, "alta"),
        ("B1-05", "Coherencia temporal", "Revisa comparabilidad, quiebres y cambios de criterio entre períodos.", "cronista", False, "alta"),
        ("B1-06", "Cálculos reproducibles", "Revisa operaciones, fórmulas y pertinencia del método cuantitativo.", "matematico", False, "alta"),
        ("B1-07", "Relaciones y análisis interdocumental", "Compara documentos relacionados y separa consistencia interna de contraste externo.", "orquesta", False, "alta"),
        ("B1-08", "Cobertura y límites", "Explicita qué fue revisado, qué no y por qué.", "conciliador", True, "alta"),
        ("B1-09", "Corrección y reevaluación", "Registra observación, acción, evidencia y resultado de cada nueva revisión.", None, True, "alta"),
        ("B1-10", "Decisión humana", "Una persona autorizada confirma si el objeto puede continuar.", None, True, "critica"),
        ("B1-11", "Contraste externo autorizado", "Registra por separado si hubo contraste externo, contra qué fuente, fecha, alcance y resultado.", None, False, "alta"),
    ]
    controles_r1 = [
        ("R1-01", "Problema público definido", "Describe problema, población, proceso y resultado público esperado.", True, "alta"),
        ("R1-02", "Necesidad real de IA", "Compara IA con automatización simple, mejora de proceso y no implementación.", True, "critica"),
        ("R1-03", "Datos y legitimidad de uso", "Identifica datos, calidad, procedencia, permisos y límites de utilización.", True, "critica"),
        ("R1-04", "Roles y responsabilidades", "Asigna responsables técnicos, funcionales, institucionales y de incidentes.", True, "alta"),
        ("R1-05", "Supervisión humana", "Define revisión, corrección y autoridad decisoria humana.", True, "critica"),
        ("R1-06", "Riesgos y poblaciones afectadas", "Registra daños plausibles, grupos afectados y mitigaciones.", True, "critica"),
        ("R1-07", "Privacidad", "Define minimización, retención, acceso y tratamiento de datos personales.", True, "critica"),
        ("R1-08", "Seguridad", "Establece acceso, registros, respuesta y continuidad operativa.", True, "critica"),
        ("R1-09", "Métricas y evaluación", "Define línea de base, desempeño, impacto, umbrales y criterio de detención.", True, "alta"),
        ("R1-10", "Incidentes y escalamiento", "Define antes de operar qué se detecta, severidad, responsable, plazo, comunicación, decisión y cierre.", True, "critica"),
        ("R1-11", "Comunicación a usuarios", "Explica cuándo interviene IA, límites y canales de revisión o reclamo.", True, "alta"),
        ("R1-12", "Mantenimiento y retiro", "Define monitoreo, actualizaciones, reevaluación, reversibilidad y retiro.", True, "alta"),
        ("R1-13", "Condiciones organizacionales y RR.HH.", "Incluye capacidades, formación, temores, tareas, responsabilidades, incentivos y gestión del cambio.", True, "alta"),
        ("R1-14", "Modelos abiertos o autoalojados", "Cuando aplica, asigna moderación, logs, retención, seguridad, excepciones y escalamiento a la organización.", False, "alta"),
        ("R1-15", "Mapa jurisdiccional", "Identifica jurisdicciones de organización, usuarios, datos, infraestructura, hechos y proveedores; deriva el análisis jurídico.", True, "critica"),
    ]
    tabla = sa.table("definiciones_control", sa.column("protocolo_id"), sa.column("codigo"), sa.column("nombre"), sa.column("descripcion"), sa.column("lente"), sa.column("obligatorio"), sa.column("criticidad"), sa.column("condicion_aplicabilidad", postgresql.JSONB()), sa.column("evidencia_requerida", postgresql.JSONB()), sa.column("orden"))
    filas = []
    for orden, (codigo, nombre, desc, lente, obligatorio, criticidad) in enumerate(controles_b1, 1):
        evidencia = {"campos": ["fuente", "fecha", "alcance", "resultado"]} if codigo == "B1-11" else None
        filas.append(dict(protocolo_id=b1, codigo=codigo, nombre=nombre, descripcion=desc, lente=lente, obligatorio=obligatorio, criticidad=criticidad, condicion_aplicabilidad=None, evidencia_requerida=evidencia, orden=orden))
    for orden, (codigo, nombre, desc, obligatorio, criticidad) in enumerate(controles_r1, 1):
        evidencia = None
        if codigo == "R1-10": evidencia = {"campos": ["evento", "severidad", "detecta", "escala_a", "responsable", "plazo", "comunicacion", "decision", "cierre"]}
        if codigo == "R1-15": evidencia = {"campos": ["organizacion", "usuarios", "datos", "infraestructura", "lugar_del_hecho", "proveedores", "derivacion_juridica"]}
        filas.append(dict(protocolo_id=r1, codigo=codigo, nombre=nombre, descripcion=desc, lente=None, obligatorio=obligatorio, criticidad=criticidad, condicion_aplicabilidad=None, evidencia_requerida=evidencia, orden=orden))
    conn.execute(tabla.insert(), filas)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM definiciones_control WHERE protocolo_id IN (SELECT id FROM versiones_protocolo WHERE version='1.1' AND codigo IN ('B-1','R-1'))"))
    conn.execute(sa.text("DELETE FROM versiones_protocolo WHERE version='1.1' AND codigo IN ('B-1','R-1')"))
    conn.execute(sa.text("UPDATE versiones_protocolo SET activo=true WHERE version='1.0' AND codigo IN ('B-1','R-1')"))
    op.drop_index("ix_historial_resultados_control_resultado_id", table_name="historial_resultados_control")
    op.drop_table("historial_resultados_control")
    op.drop_constraint("fk_sello_revocado_por", "sellos_certificacion", type_="foreignkey")
    op.drop_column("sellos_certificacion", "revocado_por_id")
    op.drop_column("evaluaciones_certificacion", "fundamento_conclusion_r1")
    op.drop_column("evaluaciones_certificacion", "conclusion_r1")
    op.drop_column("versiones_protocolo", "matriz_lentes")
    op.drop_column("interpretaciones_modelo", "identificador_version")
