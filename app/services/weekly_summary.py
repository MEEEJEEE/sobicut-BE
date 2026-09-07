"""LLM 소비 처방 생성에 넣을 주간 소비 요약 데이터 구성 모듈.

주(week) 정의: ISO 주 — 월요일 시작 ~ 일요일 종료.
레포 기존의 `app.services.common.get_week_of_month`(매월 1·8·15·22일 기준의
월 내 1~4주차)와는 정의가 다르므로 이 모듈에서는 그 함수를 쓰지 않는다.

거래 조회 방식은 `app.services.report._month_expenses` / `category_report`,
`app.services.bpti.emotion_tag_counts`의 패턴을 그대로 따르되, 연/월 필터를
날짜 범위(월요일~일요일) 필터로 바꾼 버전을 사용한다.
"""
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import EmotionTag, Transaction, TransactionEmotion, User
from app.services.bpti import EMOTION_NAMES
from app.services.impulse import transaction_impulse_score
from app.services.report import CATEGORIES


def get_iso_week_range(d: date) -> tuple[date, date]:
    """`d`가 속한 ISO 주의 (월요일, 일요일)을 반환한다. `d.weekday()`는 월=0."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _week_expenses(db: Session, user_id: int, week_start: date, week_end: date) -> list[Transaction]:
    """해당 주(week_start~week_end, 양끝 포함)의 지출 거래. 수입은 제외한다.

    (transactions에는 soft-delete 컬럼이 없어 report._month_expenses와 동일하게
    user_id + type == "expense" + 기간만 필터한다.)
    """
    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.transaction_date >= week_start,
            Transaction.transaction_date <= week_end,
        )
        .all()
    )


def _week_emotion_tag_counts(
    db: Session, user_id: int, week_start: date, week_end: date
) -> dict[str, int]:
    """해당 주 지출 거래의 감정(심리특성) 태그별 건수.

    bpti.emotion_tag_counts와 같은 join 방식이지만 연/월 대신 날짜 범위로 필터한다.
    태그명은 코드상 공백 없이 사용된다(예: 비교회피, 충분한숙고).
    """
    rows = (
        db.query(EmotionTag.name, func.count(TransactionEmotion.id))
        .join(TransactionEmotion, TransactionEmotion.emotion_tag_id == EmotionTag.id)
        .join(Transaction, Transaction.id == TransactionEmotion.transaction_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.transaction_date >= week_start,
            Transaction.transaction_date <= week_end,
        )
        .group_by(EmotionTag.name)
        .all()
    )
    counts = {name: 0 for name in EMOTION_NAMES}
    counts.update(dict(rows))
    return counts


def build_weekly_summary(db: Session, user: User, week_start: date) -> dict:
    """`week_start`(반드시 월요일)이 속한 ISO 주의 소비 요약을 만든다.

    해당 주에 지출 거래가 0건이어도 예외 없이 빈 값으로 정상 반환한다.
    """
    if week_start.weekday() != 0:
        raise ValueError("week_start는 월요일(weekday() == 0)이어야 합니다.")

    _, week_end = get_iso_week_range(week_start)

    txs = _week_expenses(db, user.id, week_start, week_end)
    total_spent = sum(t.amount for t in txs)

    # 카테고리 집계: report.category_report와 동일 패턴 (CATEGORIES 상수 재사용).
    sums = {c: 0 for c in CATEGORIES}
    for t in txs:
        sums[t.category] = sums.get(t.category, 0) + t.amount
    categories = [
        {
            "category": c,
            "amount": amt,
            "ratio": round(amt / total_spent * 100, 1) if total_spent else 0.0,
        }
        for c, amt in sums.items()
    ]

    scored = [(t, transaction_impulse_score(db, t, user)) for t in txs]
    avg_impulse_score = round(sum(s for _, s in scored) / len(scored)) if scored else None

    top_transactions = [
        {
            "merchant": t.merchant,
            "amount": t.amount,
            "category": t.category,
            "impulse_score": score,
        }
        for t, score in sorted(scored, key=lambda x: x[1], reverse=True)[:3]
    ]

    return {
        "period_start": week_start,
        "period_end": week_end,
        "total_spent": total_spent,
        "transaction_count": len(txs),
        "categories": categories,
        "avg_impulse_score": avg_impulse_score,
        "top_transactions": top_transactions,
        "emotion_counts": _week_emotion_tag_counts(db, user.id, week_start, week_end),
    }
