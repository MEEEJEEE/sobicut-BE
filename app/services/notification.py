from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Budget, Notification, Transaction, User
from app.services.common import get_week_of_month
from app.services.impulse import monthly_spent, transaction_impulse_score


def _exists_this_period(db: Session, user_id: int, ntype: str, since: date) -> bool:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.type == ntype,
            func.date(Notification.created_at) >= since,
        )
        .first()
        is not None
    )


def check_after_transaction(db: Session, user: User, tx: Transaction) -> None:
    """거래 등록 직후 예산 초과·충동 경고 알림 생성 (commit은 호출부에서)"""
    if tx.type != "expense":
        return

    budget = db.query(Budget).filter(Budget.user_id == user.id).first()
    d = tx.transaction_date

    if budget:
        # 월간 예산 초과
        if budget.monthly_budget > 0:
            spent = monthly_spent(db, user.id, d.year, d.month)
            if spent > budget.monthly_budget and not _exists_this_period(
                db, user.id, "budget_monthly", d.replace(day=1)
            ):
                db.add(
                    Notification(
                        user_id=user.id,
                        type="budget_monthly",
                        title="월간 예산 초과",
                        message="이번 달 예산을 초과했습니다.",
                    )
                )

        # 주간 예산 초과 (해당 주차 예산 기준)
        week = get_week_of_month(d)
        week_budget = getattr(budget, f"week_{week}_budget", 0) or budget.weekly_budget
        if week_budget > 0:
            week_start_day = (week - 1) * 7 + 1
            week_start = d.replace(day=week_start_day)
            week_spent = (
                db.query(func.coalesce(func.sum(Transaction.amount), 0))
                .filter(
                    Transaction.user_id == user.id,
                    Transaction.type == "expense",
                    Transaction.transaction_date >= week_start,
                    Transaction.transaction_date <= d,
                )
                .scalar()
            )
            if int(week_spent) > week_budget and not _exists_this_period(
                db, user.id, "budget_weekly", week_start
            ):
                db.add(
                    Notification(
                        user_id=user.id,
                        type="budget_weekly",
                        title="주간 예산 초과",
                        message="이번 주 예산을 초과했습니다.",
                    )
                )

    # 충동 소비 경고
    score = transaction_impulse_score(db, tx, user)
    if score >= settings.IMPULSE_THRESHOLD * 100:
        db.add(
            Notification(
                user_id=user.id,
                type="impulse_warning",
                title="충동 소비 경고 ✂️",
                message=f"방금 소비의 충동 점수가 {score}점이에요. 잠시 멈추고 다시 생각해봐요!",
            )
        )
