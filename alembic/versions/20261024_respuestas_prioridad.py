"""respuestas_senal: prioridad del caso y versión del motor al momento de responder.

Sólo agrega dos columnas que admiten NULL: las respuestas anteriores quedan como estaban (sin dato) y nada se
borra. Así la precisión por prioridad no cambia cuando cambia el código que calcula la prioridad.
"""
import sqlalchemy as sa

from alembic import op

revision = "20261024_respuestas_prioridad"
down_revision = "20261022_biblioteca_casos"
branch_labels = depends_on = None


def upgrade():
    op.add_column("respuestas_senal", sa.Column("prioridad", sa.String(10), nullable=True))
    op.add_column("respuestas_senal", sa.Column("version_motor", sa.String(64), nullable=True))


def downgrade():
    # En lote: en PostgreSQL son dos ALTER TABLE; en SQLite viejo (sin DROP COLUMN) recrea la tabla con sus filas.
    with op.batch_alter_table("respuestas_senal") as batch:
        batch.drop_column("version_motor")
        batch.drop_column("prioridad")
