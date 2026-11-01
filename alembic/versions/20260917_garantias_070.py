"""Ejecuciones versionadas y corridas de calibración; no reescribe informes históricos."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260917_garantias_070"
down_revision = "20260915_hipotesis_exploratorias"
branch_labels = depends_on = None


def upgrade():
    op.create_table("ejecuciones_analisis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informe_id", sa.Integer(), sa.ForeignKey("informes.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("dominio", sa.String(50), nullable=False),
        sa.Column("version_aplicacion", sa.String(30), nullable=False),
        sa.Column("version_protocolo", sa.String(60), nullable=False),
        sa.Column("version_codigo", sa.String(64), nullable=False),
        sa.Column("manifiesto", JSONB(), nullable=False),
        sa.Column("requiere_reevaluacion", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("incidencias", JSONB(), nullable=False, server_default="[]"))
    op.create_index("ix_ejecuciones_analisis_informe_id", "ejecuciones_analisis", ["informe_id"])
    op.create_index("ix_ejecuciones_analisis_version_codigo", "ejecuciones_analisis", ["version_codigo"])
    op.create_table("corridas_calibracion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("responsable_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("dominio", sa.String(50), nullable=False),
        sa.Column("version_protocolo", sa.String(60), nullable=False),
        sa.Column("version_codigo", sa.String(64), nullable=False),
        sa.Column("control", sa.String(80), nullable=False),
        sa.Column("version_control", sa.String(64), nullable=False),
        sa.Column("bateria", sa.String(200), nullable=False),
        sa.Column("casos", JSONB(), nullable=False),
        sa.Column("tolerancia", sa.Float(), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False),
        sa.Column("categoria_incidencia", sa.String(40)),
        sa.Column("desde", sa.DateTime(), nullable=False),
        sa.Column("hasta", sa.DateTime(), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=False),
        sa.CheckConstraint("estado IN ('aprobada', 'fallida')", name="ck_calibracion_estado"),
        sa.CheckConstraint("tolerancia >= 0", name="ck_calibracion_tolerancia"))


def downgrade():
    op.drop_table("corridas_calibracion")
    op.drop_table("ejecuciones_analisis")
