import calendar
from datetime import date

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Budget, Transaction
from app.services.common import DAY_NAMES, get_time_slot, get_week_of_month

CATEGORIES = ["식비", "고정지출", "교통", "생활", "쇼핑/패션", "자기계발", "문화/여가", "모임/기타"]

# 히트맵 피크 푸시 알림 이름 (소비컷 컨셉)
DAY_LABELS = {"월": "월요병 텅진 컷", "화": "루틴 소비 컷", "수": "루틴 소비 컷",
              "목": "루틴 소비 컷", "금": "불금 입구 컷", "토": "주말 플렉스 컷", "일": "주말 플렉스 컷"}
TIME_LABELS = {"아침": "갓생 시동 컷", "점심": "공강 텐션 컷", "저녁": "저녁 보상 컷",
               "밤": "야간 야망 컷", "새벽": "새벽 감성 컷"}


def _month_expenses(db: Session, user_id: int, year: int, month: int) -> list[Transaction]:
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


def category_report(db: Session, user_id: int, year: int, month: int) -> dict:
    txs = _month_expenses(db, user_id, year, month)
    total = sum(t.amount for t in txs)
    sums = {c: 0 for c in CATEGORIES}
    for t in txs:
        sums[t.category] = sums.get(t.category, 0) + t.amount
    categories = [
        {"category": c, "amount": amt, "ratio": round(amt / total * 100, 1) if total else 0.0}
        for c, amt in sums.items()
    ]
    return {"total_spent": total, "categories": categories}


def heatmap_report(db: Session, user_id: int, year: int, month: int) -> dict:
    txs = _month_expenses(db, user_id, year, month)
    cells: dict[tuple[str, str], dict] = {}
    for t in txs:
        day = DAY_NAMES[t.transaction_date.weekday()]
        slot = get_time_slot(t.transaction_time)
        cell = cells.setdefault((day, slot), {"amount": 0, "count": 0})
        cell["amount"] += t.amount
        cell["count"] += 1

    heatmap = [
        {"day": day, "time_slot": slot, "amount": v["amount"], "count": v["count"]}
        for (day, slot), v in cells.items()
    ]
    heatmap.sort(key=lambda x: (DAY_NAMES.index(x["day"]), ["아침", "점심", "저녁", "밤", "새벽"].index(x["time_slot"])))

    peak = None
    if cells:
        (day, slot), _ = max(cells.items(), key=lambda kv: kv[1]["amount"])
        # 요일 특화 라벨 우선(월/금/토/일), 그 외 요일은 시간대 라벨
        label = DAY_LABELS[day] if day in {"월", "금", "토", "일"} else TIME_LABELS[slot]
        peak = {"day": day, "time_slot": slot, "notification_label": label}

    return {"heatmap": heatmap, "peak": peak}


def budget_status(db: Session, user_id: int, year: int, month: int) -> dict:
    budget = db.query(Budget).filter(Budget.user_id == user_id).first()
    monthly_budget = budget.monthly_budget if budget else 0
    txs = _month_expenses(db, user_id, year, month)
    spent = sum(t.amount for t in txs)

    weekly_spent = {w: 0 for w in (1, 2, 3, 4)}
    for t in txs:
        weekly_spent[get_week_of_month(t.transaction_date)] += t.amount

    def week_budget(w: int) -> int:
        if budget is None:
            return 0
        return getattr(budget, f"week_{w}_budget", 0) or budget.weekly_budget

    today = date.today()
    current_week = get_week_of_month(today) if (today.year, today.month) == (year, month) else 4

    weekly_breakdown = []
    for w in (1, 2, 3, 4):
        wb = week_budget(w)
        ws = weekly_spent[w]
        weekly_breakdown.append({
            "week": w,
            "budget": wb,
            "spent": ws,
            "usage_rate": round(ws / wb * 100, 1) if wb else 0.0,
        })

    cw_budget = week_budget(current_week)
    cw_spent = weekly_spent[current_week]
    return {
        "monthly": {
            "budget": monthly_budget,
            "spent": spent,
            "remaining": monthly_budget - spent,
            "usage_rate": round(spent / monthly_budget * 100, 1) if monthly_budget else 0.0,
        },
        "weekly": {
            "current_week": current_week,
            "budget": cw_budget,
            "spent": cw_spent,
            "remaining": cw_budget - cw_spent,
            "usage_rate": round(cw_spent / cw_budget * 100, 1) if cw_budget else 0.0,
        },
        "weekly_breakdown": weekly_breakdown,
    }


def monthly_forecast(db: Session, user_id: int, year: int, month: int) -> dict:
    """일평균 기반 월말 지출 예측 (AI 파트 회귀 모델로 고도화 예정)"""
    budget = db.query(Budget).filter(Budget.user_id == user_id).first()
    monthly_budget = budget.monthly_budget if budget else 0
    spent = sum(t.amount for t in _month_expenses(db, user_id, year, month))

    days_in_month = calendar.monthrange(year, month)[1]
    today = date.today()
    if (today.year, today.month) == (year, month):
        elapsed = today.day
    else:
        elapsed = days_in_month  # 과거 달은 확정치

    predicted = round(spent / elapsed * days_in_month) if elapsed else spent
    if elapsed >= days_in_month:
        confidence = "high"
    elif elapsed >= 15:
        confidence = "high"
    elif elapsed >= 7:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "current_spent": spent,
        "predicted_total": predicted,
        "budget": monthly_budget,
        "predicted_remaining": monthly_budget - predicted,
        "is_over_budget": predicted > monthly_budget if monthly_budget else False,
        "confidence": confidence,
    }


def weekly_temperatures(db: Session, user_id: int, year: int, month: int) -> list[dict]:
    """주차별 온도 (주차 예산 대비 주차 지출)"""
    status = budget_status(db, user_id, year, month)
    return [
        {"week": row["week"], "temp": round(row["usage_rate"])}
        for row in status["weekly_breakdown"]
    ]
