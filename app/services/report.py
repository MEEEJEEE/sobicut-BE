import calendar
from datetime import date

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import Budget, Transaction
from app.services.common import DAY_NAMES, get_time_slot, get_week_of_month

CATEGORIES = ["식비", "고정지출", "교통", "생활", "쇼핑/패션", "자기계발", "문화/여가", "모임/기타"]

# 시간대컷 푸시 알림 이름 (소비컷 컨셉). 요일컷은 브랜드명 대신 요일명을 그대로 쓴다
# ("루틴 소비 컷"처럼 화/수/목이 뭉뚱그려지는 걸 없애기 위해 v2에서 요일컷/시간대컷을
# 완전히 독립된 두 지표로 분리함 — 더 이상 한쪽이 다른 쪽으로 대체되지 않는다).
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

    # 요일컷(요일별 합계 중 최대)과 시간대컷(시간대별 합계 중 최대)을 완전히 독립적으로 계산한다.
    # 예전엔 (요일,시간대) 조합 셀 하나만 골라서 요일이 화/수/목이면 "루틴 소비 컷"이라는
    # 시간대 라벨로 대체했는데, 이 폴백을 없애고 둘 다 항상 각자 기준으로 따로 뽑는다.
    day_totals: dict[str, int] = {}
    slot_totals: dict[str, int] = {}
    for (day, slot), v in cells.items():
        day_totals[day] = day_totals.get(day, 0) + v["amount"]
        slot_totals[slot] = slot_totals.get(slot, 0) + v["amount"]

    peak_day = None
    if day_totals:
        top_day = max(day_totals, key=day_totals.get)
        peak_day = {"day": top_day, "message": f"{top_day}요일에 소비가 가장 많아요"}

    peak_time_slot = None
    if slot_totals:
        top_slot = max(slot_totals, key=slot_totals.get)
        peak_time_slot = {"time_slot": top_slot, "label": TIME_LABELS[top_slot]}

    return {"heatmap": heatmap, "peak_day": peak_day, "peak_time_slot": peak_time_slot}


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


def monthly_spending_history(db: Session, user_id: int, year: int, month: int, months: int = 4) -> list[dict]:
    """이번 달을 제외한 과거 N개월 실제 지출액 (오래된 순). 막대 차트용."""
    history = []
    y, m = year, month
    for _ in range(months):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        spent = sum(t.amount for t in _month_expenses(db, user_id, y, m))
        history.append({"year": y, "month": m, "spent": spent})
    history.reverse()
    return history


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

    history = monthly_spending_history(db, user_id, year, month)
    monthly_average = round(sum(h["spent"] for h in history) / len(history)) if history else 0

    return {
        "current_spent": spent,
        "predicted_total": predicted,
        "budget": monthly_budget,
        "predicted_remaining": monthly_budget - predicted,
        "is_over_budget": predicted > monthly_budget if monthly_budget else False,
        "confidence": confidence,
        "history": history,
        "monthly_average": monthly_average,
    }


def daily_report(db: Session, user_id: int, year: int, month: int) -> list[dict]:
    """일자별 수입/지출 합계 (해당 월 기준)"""
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .all()
    )
    sums: dict = {}
    for t in txs:
        day = sums.setdefault(t.transaction_date, {"income": 0, "expense": 0})
        day[t.type] += t.amount

    return [
        {"date": d.isoformat(), "income": v["income"], "expense": v["expense"]}
        for d, v in sorted(sums.items())
    ]


def weekly_temperatures(db: Session, user_id: int, year: int, month: int) -> list[dict]:
    """주차별 온도 (주차 예산 대비 주차 지출)"""
    status = budget_status(db, user_id, year, month)
    return [
        {"week": row["week"], "temp": round(row["usage_rate"])}
        for row in status["weekly_breakdown"]
    ]
