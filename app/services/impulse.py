"""충동 소비 점수 계산 (로지스틱 회귀: 선형결합 + 시그모이드)

"설문조사 기반 충동 점수 로직 재설정" 문서(대학생 45명 설문) 기준.

z = bias + Σ βi·xi (결제 전 행동 변수) + Σ γj·yj (심리 변수)
충동 위험 지수 = 100 × 1 / (1 + e^-z)

구매후후회(β4)·지속적만족(γ6)은 "결제 후 평가"로 별도 관리한다 — 이미 끝난 구매의
실시간 위험 점수(z)를 만족도 데이터가 나중에 들어올 때마다 다시 계산하지 않기 위해,
post_purchase_breakdown()으로 분리하고 z 계산에는 포함하지 않는다.

가중치는 weights.json에서 로드 — 실사용 데이터 축적 후 정규화 로지스틱 회귀로 재추정 예정.
"""
import json
import math
import statistics
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Budget, Satisfaction, Transaction, User

WEIGHTS_PATH = Path(__file__).parent / "weights.json"
WEIGHTS = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))


def _time_abnormal(tx: Transaction) -> float:
    """이상 시간대(x1): 01~05시=1, 23~01시=0.5, 그 외=0"""
    h = tx.transaction_time.hour
    if 1 <= h < 5:
        return 1.0
    if h >= 23 or h < 1:
        return 0.5
    return 0.0


def _amount_burden(db: Session, tx: Transaction) -> float:
    """금액 부담(x2) = 0.6*R + 0.4*B

    R: 가용자금(월 예산) 대비 구매금액 비율을 구간별로 변환 (5%이하=0.10 ~ 30%이상=1.00)
    B: 구매 시점에 입력한 주관적 경제 부담(1~5점) -> 0~1 변환. 미입력 시 R로 근사한다.
    """
    budget = db.query(Budget).filter(Budget.user_id == tx.user_id).first()
    if budget is None or budget.monthly_budget <= 0:
        return 0.0

    ratio = tx.amount / budget.monthly_budget
    if ratio <= 0.05:
        R = 0.10
    elif ratio <= 0.10:
        R = 0.25
    elif ratio <= 0.20:
        R = 0.50
    elif ratio <= 0.30:
        R = 0.75
    else:
        R = 1.00

    B = (tx.subjective_burden - 1) / 4 if tx.subjective_burden is not None else R
    return 0.6 * R + 0.4 * B


def _peer_comparison(db: Session, user: User, year: int, month: int) -> float:
    """또래 대비 소비(x3): z-score 기반. 또래 평균 이하=0, +1표준편차=0.5, +2표준편차 이상=1"""
    my_spent = monthly_spent(db, user.id, year, month)
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
    peer_spendings = [monthly_spent(db, p.id, year, month) for p in peers]
    if len(peer_spendings) < 2:
        return 0.0  # 표준편차를 낼 만큼 또래 데이터가 없음

    mean = statistics.mean(peer_spendings)
    stdev = statistics.pstdev(peer_spendings)
    if stdev == 0:
        return 1.0 if my_spent > mean else 0.0
    z = (my_spent - mean) / stdev
    return min(max(z / 2, 0.0), 1.0)


def _weighted_satisfaction(db: Session, tx: Transaction) -> float | None:
    """q = 0.2*q_1일 + 0.3*q_7일 + 0.5*q_30일, qt=(만족도-1)/4. 제출된 데이터 없으면 None."""
    records = db.query(Satisfaction).filter(Satisfaction.transaction_id == tx.id).all()
    if not records:
        return None
    day_weights = WEIGHTS["regret_day_weights"]
    total_w, acc = 0.0, 0.0
    for s in records:
        w = day_weights.get(s.day_type, 0.0)
        acc += w * (s.score - 1) / 4
        total_w += w
    return acc / total_w if total_w > 0 else None


def _regret_score(db: Session, tx: Transaction) -> float:
    """구매 후 후회(x4) = max(0, 1-2q). 결제 후 평가 — 실시간 z에는 미반영."""
    q = _weighted_satisfaction(db, tx)
    return max(0.0, 1 - 2 * q) if q is not None else 0.0


def _sustained_satisfaction(db: Session, tx: Transaction) -> float:
    """지속적 만족(y6) = max(0, 2q-1). 결제 후 평가 — 실시간 z에는 미반영."""
    q = _weighted_satisfaction(db, tx)
    return max(0.0, 2 * q - 1) if q is not None else 0.0


def _budget_usage_rate(db: Session, user_id: int, year: int, month: int) -> float | None:
    budget = db.query(Budget).filter(Budget.user_id == user_id).first()
    if budget is None or budget.monthly_budget <= 0:
        return None
    spent = monthly_spent(db, user_id, year, month)
    return spent / budget.monthly_budget * 100


def _peer_avg_usage_rate(db: Session, user: User, year: int, month: int) -> float | None:
    """같은 그룹(거주형태+소득구간) 사용자들의 평균 예산 소비율 (지갑 온도 비교용, 충동 점수 아님)"""
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


def peer_avg_impulse_score(db: Session, user: User, year: int, month: int) -> int | None:
    """같은 그룹(거주형태+소득구간) 사용자들의 이번 달 평균 충동 점수"""
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
    scores = []
    for p in peers:
        txs = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == p.id,
                Transaction.type == "expense",
                func.extract("year", Transaction.transaction_date) == year,
                func.extract("month", Transaction.transaction_date) == month,
            )
            .all()
        )
        if txs:
            scores.append(sum(transaction_impulse_score(db, tx, p) for tx in txs) / len(txs))
    return round(sum(scores) / len(scores)) if scores else None


def weekly_impulse_comparison(db: Session, user: User) -> dict:
    """이번 주 vs 지난주 평균 충동 점수 (오늘 기준 최근 7일 롤링 윈도우)"""

    def _avg_for_range(start: date, end: date) -> int | None:
        txs = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user.id,
                Transaction.type == "expense",
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
            .all()
        )
        if not txs:
            return None
        return round(sum(transaction_impulse_score(db, tx, user) for tx in txs) / len(txs))

    today = date.today()
    this_week_start = today - timedelta(days=6)
    last_week_end = this_week_start - timedelta(days=1)
    last_week_start = last_week_end - timedelta(days=6)

    this_week = _avg_for_range(this_week_start, today)
    last_week = _avg_for_range(last_week_start, last_week_end)
    diff = (this_week - last_week) if (this_week is not None and last_week is not None) else None

    return {"this_week": this_week, "last_week": last_week, "diff": diff}


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
    """결제 전 위험 점수(z)에 실제로 반영되는 행동 변수만 포함."""
    return {
        "time_abnormal": _time_abnormal(tx),
        "amount_burden": _amount_burden(db, tx),
        "peer_comparison": _peer_comparison(db, user, tx.transaction_date.year, tx.transaction_date.month),
    }


def post_purchase_breakdown(db: Session, tx: Transaction) -> dict[str, float]:
    """결제 후 평가 — 개인화/분석 참고용. 실시간 충동 점수(z)에는 포함하지 않는다."""
    return {
        "regret_score": _regret_score(db, tx),
        "sustained_satisfaction": _sustained_satisfaction(db, tx),
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
    """단건 거래의 충동 위험 지수 (0~100)"""
    return round(transaction_impulse_probability(db, tx, user) * 100)


def risk_level(score: int) -> str:
    """충동 위험 지수 3단계: 0~59 낮음 / 60~66 주의 / 67 이상 경고"""
    if score >= settings.IMPULSE_WARNING_THRESHOLD * 100:
        return "경고"
    if score >= settings.IMPULSE_CAUTION_THRESHOLD * 100:
        return "주의"
    return "낮음"
