"""bitacora de actividad pedagogica y operativa"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260902_activity_events"
down_revision: Union[str, Sequence[str], None] = "20260902_aprendizajes_incubadora"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("informe_id", sa.Integer(), sa.ForeignKey("informes.id"), nullable=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=True),
        sa.Column("modulo", sa.String(length=40), nullable=False),
        sa.Column("accion", sa.String(length=80), nullable=False),
        sa.Column("resumen", sa.String(length=300), nullable=True),
        sa.Column("metadata_evento", postgresql.JSONB(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_activity_events_usuario_id", "activity_events", ["usuario_id"])
    op.create_index("ix_activity_events_informe_id", "activity_events", ["informe_id"])
    op.create_index("ix_activity_events_proyecto_id", "activity_events", ["proyecto_id"])
    op.create_index("ix_activity_events_modulo", "activity_events", ["modulo"])
    op.create_index("ix_activity_events_accion", "activity_events", ["accion"])
    op.create_index("ix_activity_events_creado_en", "activity_events", ["creado_en"])
    op.create_index("ix_activity_events_modulo_accion_fecha", "activity_events", ["modulo", "accion", "creado_en"])


def downgrade() -> None:
    op.drop_index("ix_activity_events_modulo_accion_fecha", table_name="activity_events")
    op.drop_index("ix_activity_events_creado_en", table_name="activity_events")
    op.drop_index("ix_activity_events_accion", table_name="activity_events")
    op.drop_index("ix_activity_events_modulo", table_name="activity_events")
    op.drop_index("ix_activity_events_proyecto_id", table_name="activity_events")
    op.drop_index("ix_activity_events_informe_id", table_name="activity_events")
    op.drop_index("ix_activity_events_usuario_id", table_name="activity_events")
    op.drop_table("activity_events")
