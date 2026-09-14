"""좋은 소비 습관에 대한 보너스 exp 배치 (매일 1회 실행).

매월 1일에, 방금 끝난 지난달 예산을 초과하지 않고 마감한 사용자에게 보너스 exp를 지급한다.
User.last_budget_bonus_month로 월별 중복 지급을 막는다(멱등).
"""
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Budget, User
from app.services import level as level_service
from app.services.impulse import monthly_spent

logger = logging.getLogger(__name__)


def process_monthly_budget_bonus(db: Session, user_id: int | None = None, *, force: bool = False) -> int:
    """오늘이 매월 1일일 때만 동작. 보너스를 지급한 사용자 수를 반환한다.

    user_id: 지정하면 그 유저만 대상으로 함 (발표/데모 수동 트리거용).
    force: True면 "매월 1일만" 게이트와 월별 중복 지급 방지를 모두 건너뜀
    (데모 중 반복 트리거용). 지난달 실제 예산 준수 여부는 그대로 판정한다.
    스케줄러는 항상 기본값(False) 사용.
    """
    today = date.today()
    if not force and today.day != 1:
        return 0

    prev_month_last_day = today.replace(day=1) - timedelta(days=1)
    year, month = prev_month_last_day.year, prev_month_last_day.month
    year_month = f"{year:04d}-{month:02d}"

    query = db.query(User).filter(User.deleted_at.is_(None))
    if user_id is not None:
        query = query.filter(User.id == user_id)
    users = query.all()
    granted = 0
    for user in users:
        if not force and user.last_budget_bonus_month == year_month:
            continue

        budget = db.query(Budget).filter(Budget.user_id == user.id).first()
        if budget is None or budget.monthly_budget <= 0:
            continue

        spent = monthly_spent(db, user.id, year, month)
        if spent <= budget.monthly_budget:
            level_service.add_exp(db, user, level_service.EXP_BUDGET_COMPLIANCE_BONUS)
            granted += 1

        user.last_budget_bonus_month = year_month  # 초과했어도 그 달은 이미 판정 끝났으니 기록

    db.commit()
    logger.info("월간 예산 준수 보너스 배치 완료: %d명 지급 (%s)", granted, year_month)
    return granted
