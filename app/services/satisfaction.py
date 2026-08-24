"""고가 소비 만족도 조사 대상 계산 로직.

Satisfaction row는 사용자가 실제로 제출했을 때만 생성되므로(스키마상 score 필수),
"아직 미제출인 대상"은 거래 내역과 (transaction_id, day_type) 조합으로 그때그때
계산한다. `GET /satisfactions/pending`(팝업 트리거용, 마감일이 지난 것 전부)과
배치 발송(정확히 마감일 당일인 것만)이 이 로직을 공유한다.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Transaction

DAY_TYPES = {"7일": 7, "30일": 30}


def due_satisfaction_targets(
    db: Session, user_id: int | None = None, *, due_today_only: bool = False
) -> list[tuple[Transaction, str, date]]:
    """(거래, day_type, 마감일) 목록 반환. 만족도 미제출 대상만 포함한다.

    - due_today_only=False (기본): 마감일이 지났고 아직 미제출인 전체 대상 (pending 조회용)
    - due_today_only=True: 마감일이 정확히 오늘인 대상만 (배치 발송용, 하루에 한 번만 걸리게)
    """
    q = db.query(Transaction).filter(
        Transaction.type == "expense",
        Transaction.amount >= settings.HIGH_PRICE_THRESHOLD,
    )
    if user_id is not None:
        q = q.filter(Transaction.user_id == user_id)

    today = date.today()
    result: list[tuple[Transaction, str, date]] = []
    for tx in q.all():
        submitted = {s.day_type for s in tx.satisfactions}
        for day_type, days in DAY_TYPES.items():
            if day_type in submitted:
                continue
            due = tx.transaction_date + timedelta(days=days)
            if due_today_only:
                if due == today:
                    result.append((tx, day_type, due))
            elif today >= due:
                result.append((tx, day_type, due))
    return result
