"""segunda vuelta de proyectos ia"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260912_votos_segunda"
down_revision: Union[str, Sequence[str], None] = "20260907_votos_ia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "votos_segunda_vuelta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("usuario_id", name="uq_votos_segunda_vuelta_usuario"),
    )
    op.create_index("ix_votos_segunda_vuelta_proyecto_id", "votos_segunda_vuelta", ["proyecto_id"])
    op.create_index("ix_votos_segunda_vuelta_usuario_id", "votos_segunda_vuelta", ["usuario_id"])
    op.create_index(
        "ix_votos_segunda_vuelta_proyecto_fecha",
        "votos_segunda_vuelta",
        ["proyecto_id", "actualizado_en"],
    )


def downgrade() -> None:
    op.drop_index("ix_votos_segunda_vuelta_proyecto_fecha", table_name="votos_segunda_vuelta")
    op.drop_index("ix_votos_segunda_vuelta_usuario_id", table_name="votos_segunda_vuelta")
    op.drop_index("ix_votos_segunda_vuelta_proyecto_id", table_name="votos_segunda_vuelta")
    op.drop_table("votos_segunda_vuelta")
