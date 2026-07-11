"""충동 소비 점수 계산 (로지스틱 회귀: 선형결합 + 시그모이드)

z = bias + Σ βi·xi (행동 변수) + Σ γj·yj (감정 변수)
P = 1 / (1 + e^-z),  점수 = P × 100

가중치는 weights.json에서 로드 — AI 파트(PCA/설문) 산출값으로 교체 가능.
"""
import json
import math
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Budget, Satisfaction, Transaction, User
from app.services.common import get_week_of_month

WEIGHTS_PATH = Path(__file__).parent / "weights.json"
WEIGHTS = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))

# 반복 소비 판정 대상 카테고리 (식비/고정지출/교통 제외)
REPEAT_CATEGORIES = {"생활", "쇼핑/패션", "문화/여가"}


def _time_abnormal(tx: Transaction) -> float:
    """야간 소비 여부: 01~05시=1, 23~01시=0.5, 그 외=0"""
    h = tx.transaction_time.hour
    if 1 <= h < 5:
        return 1.0
    if h >= 23 or h < 1:
        return 0.5
    return 0.0


def _amount_burden(db: Session, tx: Transaction) -> float:
    """금액 부담: 월 예산 대비 단건 지출 비율 (10% 이상이면 1.0)"""
    budget = db.query(Budget).filter(Budget.user_id == tx.user_id).first()
    if budget is None or budget.monthly_budget <= 0:
        return 0.0
    ratio = tx.amount / (budget.monthly_budget * 0.1)
    return min(max(ratio, 0.0), 1.0)


def _repeat_consumption(db: Session, tx: Transaction) -> float:
    """반복 소비: 최근 1주 같은 카테고리 지출 횟수 (1회=0, 2회=0.5, 3회~=1)"""
    if tx.category not in REPEAT_CATEGORIES:
        return 0.0
    week_ago = tx.transaction_date - timedelta(days=7)
    count = (
        db.query(func.count(Transaction.id))
        .filter(
            Transaction.user_id == tx.user_id,
            Transaction.type == "expense",
            Transaction.category == tx.category,
            Transaction.transaction_date > week_ago,
            Transaction.transaction_date <= tx.transaction_date,
        )
        .scalar()
    )
    if count <= 1:
        return 0.0
    if count == 2:
        return 0.5
    return 1.0


def _peer_comparison(db: Session, user: User, year: int, month: int) -> float:
    """또래 대비: 내 예산 소비율이 그룹 평균보다 얼마나 높은지 (0~1)"""
    my_rate = _budget_usage_rate(db, user.id, year, month)
    peer_rate = _peer_avg_usage_rate(db, user, year, month)
    if my_rate is None or peer_rate is None:
        return 0.0
    # 또래 평균 대비 초과분을 50%p 기준으로 정규화
    diff = my_rate - peer_rate
    return min(max(diff / 50.0, 0.0), 1.0)


def _regret_score(db: Session, tx: Transaction) -> float:
    """후회도: r = (5 - 만족도) / 4, 7일/30일 가중 평균"""
    records = db.query(Satisfaction).filter(Satisfaction.transaction_id == tx.id).all()
    if not records:
        return 0.0
    day_weights = WEIGHTS["regret_day_weights"]
    total_w, acc = 0.0, 0.0
    for s in records:
        w = day_weights.get(s.day_type, 0.0)
        acc += w * (5 - s.score) / 4
        total_w += w
    return acc / total_w if total_w > 0 else 0.0


def _budget_usage_rate(db: Session, user_id: int, year: int, month: int) -> float | None:
    budget = db.query(Budget).filter(Budget.user_id == user_id).first()
    if budget is None or budget.monthly_budget <= 0:
        return None
    spent = monthly_spent(db, user_id, year, month)
    return spent / budget.monthly_budget * 100


def _peer_avg_usage_rate(db: Session, user: User, year: int, month: int) -> float | None:
    """같은 그룹(거주형태+소득구간) 사용자들의 평균 예산 소비율"""
    peers = (
        db.query(User)
        .filter(
            User.residence_type == user.residence_type,
            User.income_level == user.income_level,
            User.id != user.id,
            User.deleted_at.is_(None),
        )
        .all()
    )
    rates = []
    for p in peers:
        rate = _budget_usage_rate(db, p.id, year, month)
        if rate is not None:
            rates.append(rate)
    return sum(rates) / len(rates) if rates else None


def monthly_spent(db: Session, user_id: int, year: int, month: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            func.extract("year", Transaction.transaction_date) == year,
            func.extract("month", Transaction.transaction_date) == month,
        )
        .scalar()
    )
    return int(total)


def behavior_breakdown(db: Session, tx: Transaction, user: User) -> dict[str, float]:
    return {
        "time_abnormal": _time_abnormal(tx),
        "amount_burden": _amount_burden(db, tx),
        "repeat_consumption": _repeat_consumption(db, tx),
        "peer_comparison": _peer_comparison(
            db, user, tx.transaction_date.year, tx.transaction_date.month
        ),
        "regret_score": _regret_score(db, tx),
    }


def transaction_impulse_probability(db: Session, tx: Transaction, user: User) -> float:
    """단건 거래의 충동 소비 확률 (0~1)"""
    x = behavior_breakdown(db, tx, user)
    z = WEIGHTS["bias"]
    for key, value in x.items():
        z += WEIGHTS["behavior"][key] * value

    tag_names = {t.name for t in tx.emotion_tags}
    for name, gamma in WEIGHTS["emotion"].items():
        z += gamma * (1 if name in tag_names else 0)

    return 1 / (1 + math.exp(-z))


def transaction_impulse_score(db: Session, tx: Transaction, user: User) -> int:
    """단건 거래의 충동 점수 (0~100)"""
    return round(transaction_impulse_probability(db, tx, user) * 100)
