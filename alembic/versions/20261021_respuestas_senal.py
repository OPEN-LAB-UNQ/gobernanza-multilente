"""Tabla respuestas_senal: qué resultó ser cada señal, según quien hizo el informe.

Sólo agrega una tabla; no toca los hallazgos guardados. Al reanalizar, las señales se regeneran: la
respuesta queda con la copia de su señal (lente, regla, hoja, celda) y el vínculo pasa a NULL.
"""
import sqlalchemy as sa

from alembic import op

revision = "20261021_respuestas_senal"
down_revision = "20261014_resumen_llano"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "respuestas_senal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hallazgo_id", sa.Integer(), sa.ForeignKey("hallazgos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("informe_id", sa.Integer(), sa.ForeignKey("informes.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("respuesta", sa.String(20), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("lente", sa.String(30), nullable=True),
        sa.Column("regla", sa.String(80), nullable=True),
        sa.Column("hoja", sa.String(200), nullable=True),
        sa.Column("celda", sa.String(40), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_respuestas_senal_hallazgo_id", "respuestas_senal", ["hallazgo_id"])
    op.create_index("ix_respuestas_senal_informe_id", "respuestas_senal", ["informe_id"])


def downgrade():
    op.drop_index("ix_respuestas_senal_informe_id", table_name="respuestas_senal")
    op.drop_index("ix_respuestas_senal_hallazgo_id", table_name="respuestas_senal")
    op.drop_table("respuestas_senal")
