"""자유 텍스트 소비 태그 테이블 추가 (기록용, 감정 태그와 별개, 충동 점수 미반영)

Revision ID: b2e6c8f1a3d5
Revises: a8d4f2b6c9e1
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e6c8f1a3d5'
down_revision: Union[str, Sequence[str], None] = 'a8d4f2b6c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'transaction_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_transaction_tags_transaction_id'), 'transaction_tags', ['transaction_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_transaction_tags_transaction_id'), table_name='transaction_tags')
    op.drop_table('transaction_tags')
