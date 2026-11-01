"""capa exploratoria: tabla propia hipotesis_exploratorias, sin relacion con evaluaciones ni hallazgos"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260915_hipotesis_exploratorias"
down_revision: Union[str, Sequence[str], None] = "20260913_checklist_maestro"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hipotesis_exploratorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informe_id", sa.Integer(), sa.ForeignKey("informes.id"), nullable=False),
        sa.Column("tipo_pista", sa.String(40), nullable=False),
        sa.Column("texto_hipotesis", sa.Text(), nullable=False),
        sa.Column("modelo", sa.String(80), nullable=False),
        sa.Column("version_modelo", sa.String(200), nullable=True),
        sa.Column("estado", sa.String(30), nullable=False, server_default="HIPOTESIS_NO_VALIDADA"),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("estado = 'HIPOTESIS_NO_VALIDADA'", name="ck_hipotesis_estado_unico"),
    )
    op.create_index(
        "ix_hipotesis_exploratorias_informe_id", "hipotesis_exploratorias", ["informe_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hipotesis_exploratorias_informe_id", table_name="hipotesis_exploratorias")
    op.drop_table("hipotesis_exploratorias")
