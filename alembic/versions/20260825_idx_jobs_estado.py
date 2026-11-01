"indice compuesto para cola de analysis_jobs"
from typing import Sequence, Union

from alembic import op

revision: str = "20260825_idx_jobs_estado"
down_revision: Union[str, Sequence[str], None] = "20260824_learning_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_analysis_jobs_estado_cola",
        "analysis_jobs",
        ["estado", "creado_en", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_jobs_estado_cola", table_name="analysis_jobs")
