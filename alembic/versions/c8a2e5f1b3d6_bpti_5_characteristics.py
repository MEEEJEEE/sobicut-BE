"""BPTI 6개 감정태그 -> 5개 심리특성 전환

- emotion_tags/transaction_emotions 기존 데이터 초기화 (6개 태그 체계 폐기,
  다음 앱 기동 시 seed_emotion_tags()가 새 5개 특성으로 재시딩)
- transaction_emotions: 거래당 1개 분류만 허용하도록 유니크 제약 변경
  (transaction_id, emotion_tag_id) -> (transaction_id)
- transaction_emotions.description 컬럼 추가 (사용자가 입력한 구매 결정 설명 저장)

Revision ID: c8a2e5f1b3d6
Revises: b4e1f3a9c2d7
Create Date: 2026-08-24 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a2e5f1b3d6'
down_revision: Union[str, Sequence[str], None] = 'b4e1f3a9c2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 기존 6개 감정태그 체계 데이터 초기화 (destructive — 되돌릴 수 없음)
    op.execute("DELETE FROM transaction_emotions")
    op.execute("DELETE FROM emotion_tags")

    op.add_column('transaction_emotions', sa.Column('description', sa.String(length=300), nullable=True))
    op.drop_constraint('uq_transaction_emotion', 'transaction_emotions', type_='unique')
    op.create_unique_constraint('uq_transaction_emotion_single', 'transaction_emotions', ['transaction_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_transaction_emotion_single', 'transaction_emotions', type_='unique')
    op.create_unique_constraint('uq_transaction_emotion', 'transaction_emotions', ['transaction_id', 'emotion_tag_id'])
    op.drop_column('transaction_emotions', 'description')
    # 삭제된 emotion_tags/transaction_emotions 데이터는 복구되지 않는다.
