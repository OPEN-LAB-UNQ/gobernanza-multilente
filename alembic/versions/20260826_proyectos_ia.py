"""proyectos individuales con ia"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260826_proyectos_ia"
down_revision: Union[str, Sequence[str], None] = "20260825_idx_jobs_estado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proyectos_ia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False, unique=True),
        sa.Column("titulo", sa.String(length=220), nullable=True),
        sa.Column("organismo_area", sa.String(length=220), nullable=True),
        sa.Column("situacion", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=30), nullable=False, server_default="en_proceso"),
        sa.Column("entrega_final", sa.Text(), nullable=True),
        sa.Column("retro_docente", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_proyectos_ia_usuario_id", "proyectos_ia", ["usuario_id"])
    op.create_index("ix_proyectos_ia_estado_actualizado", "proyectos_ia", ["estado", "actualizado_en"])
    op.create_table(
        "mensajes_proyecto_ia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("remitente", sa.String(length=30), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_mensajes_proyecto_ia_proyecto_id", "mensajes_proyecto_ia", ["proyecto_id"])
    op.create_index("ix_mensajes_proyecto_ia_usuario_id", "mensajes_proyecto_ia", ["usuario_id"])
    op.create_index("ix_mensajes_proyecto_ia_creado_en", "mensajes_proyecto_ia", ["creado_en"])


def downgrade() -> None:
    op.drop_index("ix_mensajes_proyecto_ia_creado_en", table_name="mensajes_proyecto_ia")
    op.drop_index("ix_mensajes_proyecto_ia_usuario_id", table_name="mensajes_proyecto_ia")
    op.drop_index("ix_mensajes_proyecto_ia_proyecto_id", table_name="mensajes_proyecto_ia")
    op.drop_table("mensajes_proyecto_ia")
    op.drop_index("ix_proyectos_ia_estado_actualizado", table_name="proyectos_ia")
    op.drop_index("ix_proyectos_ia_usuario_id", table_name="proyectos_ia")
    op.drop_table("proyectos_ia")
