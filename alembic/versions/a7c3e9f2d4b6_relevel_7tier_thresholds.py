"""레벨 체계를 7단계(Lv0~6)로 개편 + 새 exp 임계값으로 기존 사용자 레벨 재계산

이름/멘트는 app/services/level.py의 LEVELS/LEVEL_DESCRIPTIONS 참고 (DB에는 저장 안 함,
숫자 level 컬럼만 저장하고 이름/멘트는 응답 시점에 매핑).

Revision ID: a7c3e9f2d4b6
Revises: e5a9d2c6f8b1
Create Date: 2026-08-25 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f2d4b6'
down_revision: Union[str, Sequence[str], None] = 'e5a9d2c6f8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# app/services/level.py의 LEVELS와 반드시 일치시킬 것
_THRESHOLDS = [(6, 400), (5, 250), (4, 160), (3, 90), (2, 40), (1, 10), (0, 0)]


def _calc_level(exp: int) -> int:
    for lv, required in _THRESHOLDS:
        if exp >= required:
            return lv
    return 0


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('users', 'level', server_default='0')

    conn = op.get_bind()
    users = sa.table('users', sa.column('id', sa.Integer), sa.column('exp', sa.Integer), sa.column('level', sa.Integer))
    for row in conn.execute(sa.select(users.c.id, users.c.exp)).fetchall():
        conn.execute(users.update().where(users.c.id == row.id).values(level=_calc_level(row.exp)))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('users', 'level', server_default='1')
    # 구 5단계 임계값으로 되돌리는 재계산은 하지 않는다 (레벨 숫자 의미가 달라 안전하게 되돌릴 수 없음).
