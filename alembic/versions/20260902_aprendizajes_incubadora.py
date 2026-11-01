"""aprendizaje curado propio de gobernanza incubadora"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260902_aprendizajes_incubadora"
down_revision: Union[str, Sequence[str], None] = "20260826_proyectos_ia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_events_incubadora",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos_ia.id"), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=40), nullable=False, server_default="propuesto"),
        sa.Column("tema", sa.String(length=60), nullable=True),
        sa.Column("metadata_evento", postgresql.JSONB(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_learning_events_incubadora_proyecto_id", "learning_events_incubadora", ["proyecto_id"])
    op.create_index("ix_learning_events_incubadora_usuario_id", "learning_events_incubadora", ["usuario_id"])
    op.create_index("ix_learning_events_incubadora_tema", "learning_events_incubadora", ["tema"])


def downgrade() -> None:
    op.drop_index("ix_learning_events_incubadora_tema", table_name="learning_events_incubadora")
    op.drop_index("ix_learning_events_incubadora_usuario_id", table_name="learning_events_incubadora")
    op.drop_index("ix_learning_events_incubadora_proyecto_id", table_name="learning_events_incubadora")
    op.drop_table("learning_events_incubadora")
