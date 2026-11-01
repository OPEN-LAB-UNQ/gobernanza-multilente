"""Casos públicos revisados, separados de corridas técnicas y validación ciega."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20261022_biblioteca_casos"
down_revision = "20261021_respuestas_senal"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "casos_biblioteca",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informe_id", sa.Integer(), sa.ForeignKey("informes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("propuesto_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("revisado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("hallazgo_id", sa.Integer(), sa.ForeignKey("hallazgos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("archivo", sa.String(250), nullable=False),
        sa.Column("hoja", sa.String(200), nullable=False),
        sa.Column("bloque", sa.Integer(), nullable=False),
        sa.Column("control", sa.String(80), nullable=False),
        sa.Column("resultado", sa.String(30), nullable=False),
        sa.Column("fundamento", sa.Text(), nullable=False),
        sa.Column("fuente_url", sa.String(1000), nullable=False),
        sa.Column("fuente_sha256", sa.String(64), nullable=False),
        sa.Column("grupo_fuente", sa.String(64), nullable=False),
        sa.Column("perfil_cuadro", JSONB(), nullable=False),
        sa.Column("evidencia", JSONB(), nullable=False),
        sa.Column("version_codigo", sa.String(64), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("decidido_en", sa.DateTime(), nullable=True),
        sa.CheckConstraint("estado IN ('pendiente', 'aprobado', 'rechazado')", name="ck_caso_biblioteca_estado"),
        sa.CheckConstraint("resultado IN ('senal_justificada', 'senal_infundada', 'omision', 'sin_senal_revisado')", name="ck_caso_biblioteca_resultado"),
    )
    op.create_index("ix_casos_biblioteca_informe_id", "casos_biblioteca", ["informe_id"])
    op.create_index("ix_casos_biblioteca_estado_control", "casos_biblioteca", ["estado", "control"])


def downgrade():
    op.drop_index("ix_casos_biblioteca_estado_control", table_name="casos_biblioteca")
    op.drop_index("ix_casos_biblioteca_informe_id", table_name="casos_biblioteca")
    op.drop_table("casos_biblioteca")
