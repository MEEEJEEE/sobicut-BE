"""add users.last_impulse_alert_month/tier (월평균 충동 지수 단계별 알림 중복 방지)

Revision ID: f3c8a1d5e7b2
Revises: c2e7a4f9b6d1
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c8a1d5e7b2'
down_revision: Union[str, Sequence[str], None] = 'c2e7a4f9b6d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('last_impulse_alert_month', sa.String(length=7), nullable=True))
    op.add_column('users', sa.Column('last_impulse_alert_tier', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'last_impulse_alert_tier')
    op.drop_column('users', 'last_impulse_alert_month')
