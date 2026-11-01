"""Columna resumen_llano en hallazgos: la frase «Qué pasó» de cada observación.

Nullable: los hallazgos anteriores no se reescriben; la frase se arma al mostrarlos.
"""
import sqlalchemy as sa

from alembic import op

revision = "20261014_resumen_llano"
down_revision = "20261002_alineacion"
branch_labels = depends_on = None


def upgrade():
    op.add_column("hallazgos", sa.Column("resumen_llano", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("hallazgos", "resumen_llano")
