"""충동 점수 로직 재설정: transactions에 subjective_burden, low_impulse_bonus_granted 추가

"설문조사 기반 충동 점수 로직 재설정" 문서 반영:
- subjective_burden: 구매 시점 체감 경제 부담(1~5), 금액부담(β2) 계산용
- low_impulse_bonus_granted: 신중한 소비 보너스 exp 중복 지급 방지

Revision ID: c2e7a4f9b6d1
Revises: b9f4d2a7c1e3
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2e7a4f9b6d1'
down_revision: Union[str, Sequence[str], None] = 'b9f4d2a7c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transactions', sa.Column('subjective_burden', sa.Integer(), nullable=True))
    op.add_column(
        'transactions',
        sa.Column('low_impulse_bonus_granted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('transactions', 'low_impulse_bonus_granted', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transactions', 'low_impulse_bonus_granted')
    op.drop_column('transactions', 'subjective_burden')
