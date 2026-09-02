"""카카오 소셜로그인 지원: users.kakao_id 추가, password nullable로 변경

Revision ID: a8d4f2b6c9e1
Revises: f3c8a1d5e7b2
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d4f2b6c9e1'
down_revision: Union[str, Sequence[str], None] = 'f3c8a1d5e7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('kakao_id', sa.String(length=50), nullable=True))
    op.alter_column('users', 'password', existing_type=sa.String(length=255), nullable=True)
    op.create_index(
        'ix_users_kakao_id_active',
        'users',
        ['kakao_id'],
        unique=True,
        sqlite_where=sa.text('deleted_at IS NULL'),
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_kakao_id_active', table_name='users')
    op.alter_column('users', 'password', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('users', 'kakao_id')
