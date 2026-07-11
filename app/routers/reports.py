from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Transaction, User
from app.services import bpti as bpti_service
from app.services import report as report_service
from app.services import wallet as wallet_service
from app.services.impulse import (
    WEIGHTS,
    behavior_breakdown,
    transaction_impulse_score,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def _now_ym(year: int | None, month: int | None) -> tuple[int, int]:
    today = date.today()
    return year or today.year, month or today.month


def _month_expense_txs(db: Session, user_id: int, year: int, month: int) -> list[Transaction]:
    from sqlalchemy import extract

    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .all()
    )


def _monthly_impulse(db: Session, user: User, year: int, month: int) -> tuple[int, dict]:
    """월 단위 충동 지수: 지출 거래별 점수 평균 + 행동 변수 평균"""
    txs = _month_expense_txs(db, user.id, year, month)
    if not txs:
        empty = {k: 0.0 for k in WEIGHTS["behavior"]}
        return 0, empty

    scores, acc = [], {k: 0.0 for k in WEIGHTS["behavior"]}
    for tx in txs:
        scores.append(transaction_impulse_score(db, tx, user))
        for k, v in behavior_breakdown(db, tx, user).items():
            acc[k] += v

    n = len(txs)
    return round(sum(scores) / n), {k: round(v / n, 2) for k, v in acc.items()}


def _wallet_summary(db: Session, user: User, year: int, month: int) -> dict:
    my_temp, _, _ = wallet_service.my_temperature(db, user, year, month)
    peer_temp = wallet_service.peer_temperature(db, user, year, month)
    level = wallet_service.classify_temperature(my_temp)
    return {
        "my_temp": my_temp,
        "peer_avg_temp": peer_temp,
        "diff": my_temp - peer_temp,
        "level": level["status"],
        "emoji": level["emoji"],
        "message": level["message"],
    }


@router.get("/scores")
def get_scores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """메인 요약 지표: 충동 지수 + 지갑 온도 + BPTI"""
    year, month = _now_ym(None, None)
    impulse_score, _ = _monthly_impulse(db, user, year, month)
    return {
        "impulse_score": impulse_score,
        "wallet_temperature": _wallet_summary(db, user, year, month),
        "bpti": bpti_service.get_bpti(db, user.id, year, month),
    }


@router.get("/impulse")
def get_impulse(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    impulse_score, breakdown = _monthly_impulse(db, user, year, month)

    radar = bpti_service.emotion_radar(db, user.id, year, month)
    emotion_breakdown = {name: round(v / 100, 2) for name, v in radar.items()}

    txs = _month_expense_txs(db, user.id, year, month)
    scored = sorted(
        (
            {
                "id": tx.id,
                "merchant": tx.merchant,
                "amount": tx.amount,
                "transaction_date": tx.transaction_date.isoformat(),
                "impulse_score": transaction_impulse_score(db, tx, user),
            }
            for tx in txs
        ),
        key=lambda x: x["impulse_score"],
        reverse=True,
    )

    return {
        "impulse_score": impulse_score,
        "threshold": int(settings.IMPULSE_THRESHOLD * 100),
        "is_warning": impulse_score >= settings.IMPULSE_THRESHOLD * 100,
        "breakdown": breakdown,
        "emotion_breakdown": emotion_breakdown,
        "top_impulse_transactions": scored[:5],
    }


@router.get("/wallet-temperature")
def get_wallet_temperature(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    summary = _wallet_summary(db, user, year, month)
    _, spent, budget = wallet_service.my_temperature(db, user, year, month)

    from app.services.impulse import _peer_avg_usage_rate  # 그룹 평균 재사용

    peer_rate = _peer_avg_usage_rate(db, user, year, month)
    return {
        **summary,
        "my_spent": spent,
        "my_budget": budget,
        "peer_group": {
            "residence_type": user.residence_type,
            "income_level": user.income_level,
            "avg_usage_rate": round(peer_rate, 1) if peer_rate is not None else None,
        },
        "temperature_levels": wallet_service.TEMPERATURE_LEVELS,
    }


@router.get("/wallet-temperature/monthly")
def get_wallet_temperature_monthly(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    summary = _wallet_summary(db, user, year, month)
    return {
        "my_temp": summary["my_temp"],
        "peer_avg_temp": summary["peer_avg_temp"],
        "level": summary["level"],
        "emoji": summary["emoji"],
        "message": summary["message"],
        "weekly_temps": report_service.weekly_temperatures(db, user.id, year, month),
    }


@router.get("/bpti")
def get_bpti(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    result = bpti_service.get_bpti(db, user.id, year, month)
    radar = bpti_service.emotion_radar(db, user.id, year, month)
    if result is None:
        return {"type": None, "label": None, "definition": None,
                "message": "아직 감정 태그 데이터가 없어요. 소비에 감정을 기록해보세요!",
                "emotion_radar": radar}
    return {**result, "emotion_radar": radar}


@router.get("/budget-status")
def get_budget_status(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    return report_service.budget_status(db, user.id, year, month)


@router.get("/category")
def get_category_report(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    return report_service.category_report(db, user.id, year, month)


@router.get("/heatmap")
def get_heatmap(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    return report_service.heatmap_report(db, user.id, year, month)


@router.get("/monthly-forecast")
def get_monthly_forecast(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    return report_service.monthly_forecast(db, user.id, year, month)
