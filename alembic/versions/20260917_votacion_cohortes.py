"""Configura actividades sin redeploy y conserva votos históricos en la cohorte original."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260917_votacion_cohortes"
down_revision = "20260917_garantias_070"
branch_labels = depends_on = None


def upgrade():
    op.create_table("actividades_votacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cohorte", sa.String(160), nullable=False, unique=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primera_vuelta_abierta", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("segunda_vuelta_abierta", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fecha_apertura_1", sa.DateTime()), sa.Column("fecha_cierre_1", sa.DateTime()),
        sa.Column("fecha_apertura_2", sa.DateTime()), sa.Column("fecha_cierre_2", sa.DateTime()),
        sa.Column("proyectos_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("finalistas", JSONB(), nullable=False, server_default="[]"),
        sa.Column("actualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("uq_actividad_votacion_activa", "actividades_votacion", ["activa"], unique=True, postgresql_where=sa.text("activa IS TRUE"))
    # Estado real anterior: ambas rondas cerradas, finalistas 6 y 16.
    op.execute(sa.text("""INSERT INTO actividades_votacion (id, cohorte, activa, proyectos_ids, finalistas)
        VALUES (1, 'un ministerio · septiembre 2026', true,
                (SELECT coalesce(jsonb_agg(id), '[]'::jsonb) FROM proyectos_ia), '[6,16]'::jsonb)"""))
    op.execute("SELECT setval(pg_get_serial_sequence('actividades_votacion','id'), 1)")
    for tabla, vieja, nueva in (("votos_proyecto_ia", "uq_votos_proyecto_ia_usuario", "uq_voto_actividad_usuario"),
                               ("votos_segunda_vuelta", "uq_votos_segunda_vuelta_usuario", "uq_voto_segunda_actividad_usuario")):
        op.add_column(tabla, sa.Column("actividad_id", sa.Integer(), sa.ForeignKey("actividades_votacion.id"), nullable=False, server_default="1"))
        op.create_index(f"ix_{tabla}_actividad_id", tabla, ["actividad_id"])
        op.drop_constraint(vieja, tabla, type_="unique")
        op.create_unique_constraint(nueva, tabla, ["actividad_id", "usuario_id"])
    op.add_column("votos_segunda_vuelta", sa.Column("justificacion", sa.Text(), nullable=True))


def downgrade():
    # Una reversión no debe colapsar votos de varias cohortes ni destruirlos.
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT count(*) FROM actividades_votacion WHERE id <> 1")).scalar():
        raise RuntimeError("Hay varias cohortes: exportar y revisar antes de revertir esta migración")
    op.drop_column("votos_segunda_vuelta", "justificacion")
    for tabla, vieja, nueva in (("votos_proyecto_ia", "uq_votos_proyecto_ia_usuario", "uq_voto_actividad_usuario"),
                               ("votos_segunda_vuelta", "uq_votos_segunda_vuelta_usuario", "uq_voto_segunda_actividad_usuario")):
        op.drop_constraint(nueva, tabla, type_="unique")
        op.create_unique_constraint(vieja, tabla, ["usuario_id"])
        op.drop_column(tabla, "actividad_id")
    op.drop_table("actividades_votacion")
