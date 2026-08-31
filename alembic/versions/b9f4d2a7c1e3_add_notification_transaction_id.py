"""add notifications.transaction_id (알림 클릭 시 관련 거래로 이동하기 위한 참조)

Revision ID: b9f4d2a7c1e3
Revises: a7c3e9f2d4b6
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9f4d2a7c1e3'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9f2d4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('notifications', sa.Column('transaction_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_notifications_transaction_id', 'notifications', 'transactions', ['transaction_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_notifications_transaction_id', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'transaction_id')
