"""거래당 감정 태그 다중 선택으로 되돌리기 (프론트 실제 UI: 태그 클릭 다중선택, 최대 4개)

이전 마이그레이션(c8a2e5f1b3d6)에서 "자유 텍스트 + 자동분류 + 거래당 1개" 구조로
바꿨으나, 실제 프론트 UI는 자유 텍스트 입력이 없고 태그를 최대 4개까지 다중 선택해서
그대로 emotion_tag_id 목록으로 보내는 구조였다. 이를 반영해 원상복구한다.

- transaction_emotions: 유니크 제약 (transaction_id) -> (transaction_id, emotion_tag_id)
- transaction_emotions.description 컬럼 제거 (더 이상 사용 안 함)

Revision ID: d1f6b8c4a7e2
Revises: c8a2e5f1b3d6
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f6b8c4a7e2'
down_revision: Union[str, Sequence[str], None] = 'c8a2e5f1b3d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('uq_transaction_emotion_single', 'transaction_emotions', type_='unique')
    op.create_unique_constraint('uq_transaction_emotion', 'transaction_emotions', ['transaction_id', 'emotion_tag_id'])
    op.drop_column('transaction_emotions', 'description')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('transaction_emotions', sa.Column('description', sa.String(length=300), nullable=True))
    op.drop_constraint('uq_transaction_emotion', 'transaction_emotions', type_='unique')
    op.create_unique_constraint('uq_transaction_emotion_single', 'transaction_emotions', ['transaction_id'])
