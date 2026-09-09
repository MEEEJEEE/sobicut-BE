"""가맹점명 -> 카테고리 LLM 매칭 캐시 테이블 추가

Revision ID: e4b7c2a9f1d3
Revises: d7e2f5a9c1b4
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b7c2a9f1d3'
down_revision: Union[str, Sequence[str], None] = 'd7e2f5a9c1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'merchant_category_map',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('normalized_name', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_merchant_category_map_normalized_name'),
        'merchant_category_map',
        ['normalized_name'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_merchant_category_map_normalized_name'), table_name='merchant_category_map'
    )
    op.drop_table('merchant_category_map')
