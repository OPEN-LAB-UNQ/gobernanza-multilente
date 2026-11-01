"""Grupos de cursada: usuarios.grupo y actividades_votacion.grupo (0.10.62).

Dos columnas que admiten NULL: las cuentas y la votación existentes quedan en el grupo por defecto (las comisiones
originales) y nada se borra. Cada participante ve los proyectos y la votación de su grupo.
"""
import sqlalchemy as sa

from alembic import op

revision = "20261029_grupos"
down_revision = "20261024_respuestas_prioridad"
branch_labels = depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("grupo", sa.String(60), nullable=True))
    op.create_index("ix_usuarios_grupo", "usuarios", ["grupo"])
    op.add_column("actividades_votacion", sa.Column("grupo", sa.String(60), nullable=True))
    # Una votación activa por grupo, en lugar de una sola en total.
    op.drop_index("uq_actividad_votacion_activa", table_name="actividades_votacion")
    op.create_index("uq_actividad_votacion_activa_grupo", "actividades_votacion", [sa.text("coalesce(grupo, '')")],
                    unique=True, postgresql_where=sa.text("activa IS TRUE"))


def downgrade():
    # Volver atrás exige que quede a lo sumo una votación activa en total.
    op.drop_index("uq_actividad_votacion_activa_grupo", table_name="actividades_votacion")
    op.create_index("uq_actividad_votacion_activa", "actividades_votacion", ["activa"], unique=True,
                    postgresql_where=sa.text("activa IS TRUE"))
    with op.batch_alter_table("actividades_votacion") as batch:
        batch.drop_column("grupo")
    op.drop_index("ix_usuarios_grupo", table_name="usuarios")
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_column("grupo")
