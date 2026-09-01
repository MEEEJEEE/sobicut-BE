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
    monthly_avg_impulse_score,
    peer_avg_impulse_score,
    post_purchase_breakdown,
    risk_level,
    transaction_impulse_score,
    weekly_impulse_comparison,
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

    acc = {k: 0.0 for k in WEIGHTS["behavior"]}
    for tx in txs:
        for k, v in behavior_breakdown(db, tx, user).items():
            acc[k] += v

    n = len(txs)
    score = monthly_avg_impulse_score(db, user, year, month)
    return score, {k: round(v / n, 2) for k, v in acc.items()}


def _wallet_summary(db: Session, user: User, year: int, month: int) -> dict:
    my_temp, _, _ = wallet_service.my_temperature(db, user, year, month)
    peer_temp = wallet_service.peer_temperature(db, user, year, month)
    level = wallet_service.classify_temperature(my_temp)
    return {
        "my_temp": my_temp,
        "peer_avg_temp": peer_temp,
        "diff": my_temp - peer_temp,
        "level": level["label"],
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
                "impulse_score": (score := transaction_impulse_score(db, tx, user)),
                "risk_level": risk_level(score),
            }
            for tx in txs
        ),
        key=lambda x: x["impulse_score"],
        reverse=True,
    )

    return {
        "impulse_score": impulse_score,
        "risk_level": risk_level(impulse_score),
        "threshold": int(settings.IMPULSE_WARNING_THRESHOLD * 100),
        "caution_threshold": int(settings.IMPULSE_CAUTION_THRESHOLD * 100),
        "is_warning": impulse_score >= settings.IMPULSE_WARNING_THRESHOLD * 100,
        "breakdown": breakdown,
        "emotion_breakdown": emotion_breakdown,
        "top_impulse_transactions": scored[:5],
        "peer_avg_impulse_score": peer_avg_impulse_score(db, user, year, month),
        "week_over_week": weekly_impulse_comparison(db, user),
        "post_purchase": _month_post_purchase_avg(db, txs),
    }


def _month_post_purchase_avg(db: Session, txs: list[Transaction]) -> dict:
    """결제 후 평가(구매후후회/지속적만족) 월 평균 — 참고용, 충동 점수엔 미반영."""
    if not txs:
        return {"regret_score": 0.0, "sustained_satisfaction": 0.0}
    acc = {"regret_score": 0.0, "sustained_satisfaction": 0.0}
    for tx in txs:
        for k, v in post_purchase_breakdown(db, tx).items():
            acc[k] += v
    return {k: round(v / len(txs), 2) for k, v in acc.items()}


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
                "message": "아직 소비 태그 데이터가 없어요. 나의 소비를 기록해보세요!",
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


@router.get("/daily")
def get_daily_report(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    return report_service.daily_report(db, user.id, year, month)


@router.get("/monthly-forecast")
def get_monthly_forecast(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    year, month = _now_ym(year, month)
    return report_service.monthly_forecast(db, user.id, year, month)
