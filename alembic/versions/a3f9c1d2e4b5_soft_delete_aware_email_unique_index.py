"""soft-delete aware unique email index

Revision ID: a3f9c1d2e4b5
Revises: 89312a915d0e
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f9c1d2e4b5'
down_revision: Union[str, Sequence[str], None] = '89312a915d0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(
        'ix_users_email_active',
        'users',
        ['email'],
        unique=True,
        sqlite_where=sa.text('deleted_at IS NULL'),
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_email_active', table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
