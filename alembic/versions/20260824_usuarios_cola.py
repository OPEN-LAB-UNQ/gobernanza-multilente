"usuarios y cola secuencial"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260824_usuarios_cola"
down_revision: Union[str, Sequence[str], None] = "90bee6470721"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=300), nullable=False),
        sa.Column("rol", sa.String(length=40), nullable=False, server_default="analista"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"])
    op.add_column("informes", sa.Column("usuario_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_informes_usuario_id", "informes", "usuarios", ["usuario_id"], ["id"])
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informe_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=30), nullable=False, server_default="pendiente"),
        sa.Column("modelos", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notify_email", sa.String(length=200), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("resultado", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notificacion_estado", sa.String(length=30), nullable=True),
        sa.Column("notificacion_error", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.Column("iniciado_en", sa.DateTime(), nullable=True),
        sa.Column("finalizado_en", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["informe_id"], ["informes.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
    )
    op.create_index("ix_analysis_jobs_informe_id", "analysis_jobs", ["informe_id"])
    op.create_index("ix_analysis_jobs_usuario_id", "analysis_jobs", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_jobs_usuario_id", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_informe_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_constraint("fk_informes_usuario_id", "informes", type_="foreignkey")
    op.drop_column("informes", "usuario_id")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
