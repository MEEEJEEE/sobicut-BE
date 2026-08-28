"""add users.last_budget_bonus_month (월간 예산 준수 보너스 exp 중복 지급 방지)

Revision ID: e5a9d2c6f8b1
Revises: d1f6b8c4a7e2
Create Date: 2026-08-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a9d2c6f8b1'
down_revision: Union[str, Sequence[str], None] = 'd1f6b8c4a7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('last_budget_bonus_month', sa.String(length=7), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'last_budget_bonus_month')
