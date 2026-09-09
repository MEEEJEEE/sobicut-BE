"""LLM 소비 처방 캐시 테이블 추가 (주기별 개선 제안 3개, user/period 조합당 1건)

Revision ID: d7e2f5a9c1b4
Revises: b2e6c8f1a3d5
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e2f5a9c1b4'
down_revision: Union[str, Sequence[str], None] = 'b2e6c8f1a3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'llm_prescriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('model_name', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'period_type', 'period_start', name='uq_llm_prescription_period'),
    )
    op.create_index(
        op.f('ix_llm_prescriptions_user_id'), 'llm_prescriptions', ['user_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_llm_prescriptions_user_id'), table_name='llm_prescriptions')
    op.drop_table('llm_prescriptions')
