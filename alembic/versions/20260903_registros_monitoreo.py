"""registro de seguimiento de gobernanza monitoreo"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260903_registros_monitoreo"
down_revision: Union[str, Sequence[str], None] = "20260902_activity_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registros_monitoreo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=40), nullable=False, server_default="abierto"),
        sa.Column("valor_indicador", sa.Float(), nullable=True),
        sa.Column("metadata_evento", postgresql.JSONB(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_registros_monitoreo_proyecto_id", "registros_monitoreo", ["proyecto_id"])
    op.create_index("ix_registros_monitoreo_usuario_id", "registros_monitoreo", ["usuario_id"])
    op.create_index("ix_registros_monitoreo_proyecto_tipo", "registros_monitoreo", ["proyecto_id", "tipo"])


def downgrade() -> None:
    op.drop_index("ix_registros_monitoreo_proyecto_tipo", table_name="registros_monitoreo")
    op.drop_index("ix_registros_monitoreo_usuario_id", table_name="registros_monitoreo")
    op.drop_index("ix_registros_monitoreo_proyecto_id", table_name="registros_monitoreo")
    op.drop_table("registros_monitoreo")
