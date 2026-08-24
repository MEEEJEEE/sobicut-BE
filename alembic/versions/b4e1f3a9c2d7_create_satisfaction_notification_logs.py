"""create satisfaction_notification_logs table

Revision ID: b4e1f3a9c2d7
Revises: f7c2b6a1d9e3
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e1f3a9c2d7'
down_revision: Union[str, Sequence[str], None] = 'f7c2b6a1d9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'satisfaction_notification_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('day_type', sa.String(length=10), nullable=False),
        sa.Column('notified_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id', 'day_type', name='uq_satisfaction_notification_log'),
    )
    op.create_index(
        op.f('ix_satisfaction_notification_logs_transaction_id'),
        'satisfaction_notification_logs',
        ['transaction_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_satisfaction_notification_logs_transaction_id'),
        table_name='satisfaction_notification_logs',
    )
    op.drop_table('satisfaction_notification_logs')
