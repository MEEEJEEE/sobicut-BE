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


def process_monthly_budget_bonus(db: Session) -> int:
    """오늘이 매월 1일일 때만 동작. 보너스를 지급한 사용자 수를 반환한다."""
    today = date.today()
    if today.day != 1:
        return 0

    prev_month_last_day = today - timedelta(days=1)
    year, month = prev_month_last_day.year, prev_month_last_day.month
    year_month = f"{year:04d}-{month:02d}"

    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    granted = 0
    for user in users:
        if user.last_budget_bonus_month == year_month:
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
