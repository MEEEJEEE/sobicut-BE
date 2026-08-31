from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Budget, Notification, Transaction, User
from app.services import level as level_service
from app.services.common import get_week_of_month
from app.services.impulse import monthly_avg_impulse_score, monthly_spent, transaction_impulse_score
from app.services.web_push import notify_active_subscribers

PUSH_NOTIFICATION_TYPE = "충동지수예산초과알림"

# 이번 달 평균 충동 지수 단계별 알림 임계값 (높은 순으로 검사)
IMPULSE_TREND_TIERS = [99, 90, 75]

_IMPULSE_TREND_COPY = {
    75: ("이번 달 충동 지수 75점 돌파 ⚠️", "이번 달 평균 충동 지수가 {score}점이에요. 소비 패턴이 조금씩 충동적으로 흐르고 있어요."),
    90: ("이번 달 충동 지수 90점 돌파 🚨", "이번 달 평균 충동 지수가 {score}점까지 올라갔어요. 소비 습관을 다시 점검해볼 때예요."),
    99: ("이번 달 충동 지수 99점 돌파 🔥", "이번 달 평균 충동 지수가 {score}점, 최고 수준이에요! 지금 바로 소비 습관을 되돌아보세요."),
}


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
                title, message = "월간 예산 초과", "이번 달 예산을 초과했습니다."
                db.add(Notification(user_id=user.id, type="budget_monthly", title=title, message=message))
                notify_active_subscribers(
                    db, user.id, PUSH_NOTIFICATION_TYPE, title, message, notification_type="budget_monthly"
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
                title, message = "주간 예산 초과", "이번 주 예산을 초과했습니다."
                db.add(Notification(user_id=user.id, type="budget_weekly", title=title, message=message))
                notify_active_subscribers(
                    db, user.id, PUSH_NOTIFICATION_TYPE, title, message, notification_type="budget_weekly"
                )

    # 이번 달 평균 충동 지수 단계별 알림 (건별 알림은 폐지 — 태그는 사용자가 직접 고른
    # 값이라 건별로 되돌려주는 게 정보값이 낮고, 태그 1~2개만 있어도 거의 매 거래마다
    # 떠서 알림이 남발되는 문제가 있었음. 메인/리포트에 보이는 "이번 달 평균 충동 지수"가
    # 새 임계값(75/90/99)을 넘을 때만, 그것도 이번 달에 아직 그 단계를 안 알렸을 때만 발송)
    _check_monthly_impulse_trend(db, user, tx)

    score = transaction_impulse_score(db, tx, user)
    if score < level_service.LOW_IMPULSE_THRESHOLD and not tx.low_impulse_bonus_granted:
        # 신중한 소비 보너스 — 좋은 소비 습관이 exp/레벨업에 직접 반영되도록.
        # 감정 태그는 거래 등록 이후 별도 호출로 붙기 때문에(생성 시점엔 항상 비어있음),
        # 실제로는 태깅 이후 재판정(tag_emotions)에서 주로 지급되고 여기선 태그 없이도
        # 낮은 점수가 나오는 경우(예산 미설정 등)만 잡는다.
        level_service.add_exp(db, user, level_service.EXP_LOW_IMPULSE_BONUS)
        tx.low_impulse_bonus_granted = True


def _check_monthly_impulse_trend(db: Session, user: User, tx: Transaction) -> None:
    """이번 달 평균 충동 지수가 새 단계(75/90/99)를 넘었으면 1회만 알린다.

    거래의 transaction_date 기준 연/월로 판단 — 예산 초과 체크와 동일한 기준.
    User.last_impulse_alert_month/tier로 같은 달 재발송을 막되, 더 높은 단계를
    새로 넘으면 다시 알린다 (예: 이번 달에 75 알림을 이미 받았어도 이후 90을
    넘으면 90 알림은 새로 감).
    """
    year, month = tx.transaction_date.year, tx.transaction_date.month
    year_month = f"{year:04d}-{month:02d}"
    score = monthly_avg_impulse_score(db, user, year, month)

    tier = next((t for t in IMPULSE_TREND_TIERS if score >= t), None)
    if tier is None:
        return

    already_notified_tier = user.last_impulse_alert_tier if user.last_impulse_alert_month == year_month else None
    if already_notified_tier is not None and tier <= already_notified_tier:
        return

    title, message_template = _IMPULSE_TREND_COPY[tier]
    message = message_template.format(score=score)
    db.add(Notification(user_id=user.id, type="impulse_monthly_trend", title=title, message=message))
    notify_active_subscribers(
        db, user.id, PUSH_NOTIFICATION_TYPE, title, message, notification_type="impulse_monthly_trend"
    )
    user.last_impulse_alert_month = year_month
    user.last_impulse_alert_tier = tier
