"""Sugerencias de pantalla identificadas, sin modificar datos existentes."""
from alembic import op
import sqlalchemy as sa

revision = "20260925_sugerencias"
down_revision = "20260917_b1_v12"
branch_labels = depends_on = None


def upgrade():
    op.create_table("sugerencias_pantalla",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("pantalla", sa.String(60), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("solicitud_id", sa.String(36), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("usuario_id", "solicitud_id", name="uq_sugerencia_solicitud"))
    op.create_index("ix_sugerencias_pantalla_usuario_id", "sugerencias_pantalla", ["usuario_id"])
    op.create_index("ix_sugerencias_pantalla_pantalla", "sugerencias_pantalla", ["pantalla"])


def downgrade():
    op.drop_table("sugerencias_pantalla")
