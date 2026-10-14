"""사용자별 가맹점 -> 카테고리 학습 사전 테이블 추가

Revision ID: c5d8e1f4a2b7
Revises: e4b7c2a9f1d3
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d8e1f4a2b7'
down_revision: Union[str, Sequence[str], None] = 'e4b7c2a9f1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_merchant_category',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('merchant_name', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'merchant_name', name='uq_user_merchant_category'),
    )
    op.create_index(
        op.f('ix_user_merchant_category_user_id'), 'user_merchant_category', ['user_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_user_merchant_category_user_id'), table_name='user_merchant_category')
    op.drop_table('user_merchant_category')
