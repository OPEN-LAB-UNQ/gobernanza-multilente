"email de notificaciones por usuario"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260824_email_notificaciones"
down_revision: Union[str, Sequence[str], None] = "20260824_usuarios_cola"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("email_notificaciones", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "email_notificaciones")
