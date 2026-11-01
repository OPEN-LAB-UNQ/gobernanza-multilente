"""votos justificados de proyectos ia"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260907_votos_ia"
down_revision: Union[str, Sequence[str], None] = "20260903_registros_monitoreo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "votos_proyecto_ia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("usuario_id", name="uq_votos_proyecto_ia_usuario"),
    )
    op.create_index("ix_votos_proyecto_ia_proyecto_id", "votos_proyecto_ia", ["proyecto_id"])
    op.create_index("ix_votos_proyecto_ia_usuario_id", "votos_proyecto_ia", ["usuario_id"])
    op.create_index("ix_votos_proyecto_ia_proyecto_fecha", "votos_proyecto_ia", ["proyecto_id", "actualizado_en"])


def downgrade() -> None:
    op.drop_index("ix_votos_proyecto_ia_proyecto_fecha", table_name="votos_proyecto_ia")
    op.drop_index("ix_votos_proyecto_ia_usuario_id", table_name="votos_proyecto_ia")
    op.drop_index("ix_votos_proyecto_ia_proyecto_id", table_name="votos_proyecto_ia")
    op.drop_table("votos_proyecto_ia")
