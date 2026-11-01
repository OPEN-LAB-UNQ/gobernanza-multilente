"learning events estructurados"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260824_learning_events"
down_revision: Union[str, Sequence[str], None] = "20260824_email_notificaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informe_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=40), nullable=False, server_default="propuesto"),
        sa.Column("lente_afectada", sa.String(length=30), nullable=True),
        sa.Column("hallazgo_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("metadata_evento", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["informe_id"], ["informes.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
    )
    op.create_index("ix_learning_events_informe_id", "learning_events", ["informe_id"])
    op.create_index("ix_learning_events_usuario_id", "learning_events", ["usuario_id"])
    op.create_index("ix_learning_events_lente_afectada", "learning_events", ["lente_afectada"])


def downgrade() -> None:
    op.drop_index("ix_learning_events_lente_afectada", table_name="learning_events")
    op.drop_index("ix_learning_events_usuario_id", table_name="learning_events")
    op.drop_index("ix_learning_events_informe_id", table_name="learning_events")
    op.drop_table("learning_events")
