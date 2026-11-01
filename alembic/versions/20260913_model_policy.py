"""model_policy por version de protocolo + manifiesto de ejecucion por evaluacion

La política de modelos queda fijada en la fila de `versiones_protocolo`: si en el
futuro cambia de forma sustantiva (modelos habilitados, mínimos, controles con
contraste obligatorio), corresponde crear una nueva fila de versión (p.ej. "1.1"),
nunca editar la existente -- eso es lo que mantiene comparables dos evaluaciones
bajo el mismo "B-1 v1.0".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260913_model_policy"
down_revision: Union[str, Sequence[str], None] = "20260913_certificaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MODEL_POLICY_B1_V1 = {
    "aplica": True,
    "modelos_habilitados": ["claude", "gpt", "gemini", "deepseek", "renderix", "llama"],
    "proveedores": {
        "claude": "Anthropic",
        "gpt": "OpenAI",
        "gemini": "Google",
        "deepseek": "DeepSeek",
        "renderix": "Renderix",
        "llama": "Ollama / autoalojado",
    },
    "modelos_minimos_con_respuesta": 2,
    "controles_con_contraste_obligatorio": ["B1-06", "B1-07"],
    "configuracion_minima": {
        "formato_respuesta": "json_estructurado_validado_contra_esquema",
        "entrada": "hallazgos_estructurados_del_informe_no_microdatos",
    },
    "limite_declarado": (
        "El sistema registra el identificador lógico del proveedor configurado "
        "(p.ej. 'gpt', 'gemini'); todavía no captura el string de versión exacto "
        "que cada API devuelve en tiempo de ejecución. Se documenta como límite "
        "del manifiesto, no se simula un dato que no existe."
    ),
}

MODEL_POLICY_R1_V1 = {
    "aplica": False,
    "motivo": (
        "R-1 evalúa condiciones de preparación de un proyecto de IA declaradas por "
        "personas responsables; no ejecuta triangulación de modelos sobre un objeto "
        "propio, por lo que no corresponde exigir un mínimo de modelos con respuesta."
    ),
}


def upgrade() -> None:
    op.add_column(
        "versiones_protocolo",
        sa.Column("model_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "evaluaciones_certificacion",
        sa.Column("manifiesto_modelos", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )

    protocolos = sa.table(
        "versiones_protocolo",
        sa.column("id", sa.Integer()),
        sa.column("codigo", sa.String()),
        sa.column("model_policy", postgresql.JSONB()),
    )
    # Nota: NO usar json.dumps() acá -- el tipo JSONB de SQLAlchemy ya
    # serializa el dict Python; volver a serializarlo produce una columna
    # con un string JSON escapado en vez de un objeto JSON real.
    op.execute(
        protocolos.update()
        .where(protocolos.c.codigo == "B-1")
        .values(model_policy=MODEL_POLICY_B1_V1)
    )
    op.execute(
        protocolos.update()
        .where(protocolos.c.codigo == "R-1")
        .values(model_policy=MODEL_POLICY_R1_V1)
    )


def downgrade() -> None:
    op.drop_column("evaluaciones_certificacion", "manifiesto_modelos")
    op.drop_column("versiones_protocolo", "model_policy")
