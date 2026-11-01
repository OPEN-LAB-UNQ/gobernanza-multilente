"""Sesiones revocables: usuarios.sesiones_desde. No modifica datos existentes."""
from alembic import op
import sqlalchemy as sa

revision = "20260929_sesiones"
down_revision = "20260925_sugerencias"
branch_labels = depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("sesiones_desde", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("usuarios", "sesiones_desde")
