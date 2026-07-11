"""지갑 온도: 예산 소비율(%)을 온도(°C)로 치환해 또래와 비교"""
from sqlalchemy.orm import Session

from app.models import Budget, User
from app.services.impulse import _peer_avg_usage_rate, monthly_spent

TEMPERATURE_LEVELS = [
    {"min": 0, "max": 19, "emoji": "❄️", "label": "매우 안정", "status": "매우 안정",
     "message": "지갑이 시원하게 유지되고 있어요. 아직 충분히 여유 있어요"},
    {"min": 20, "max": 49, "emoji": "🙂", "label": "안정", "status": "안정",
     "message": "아직은 미지근한 상태! 여유 있게 잘 관리 중이에요"},
    {"min": 50, "max": 79, "emoji": "😐", "label": "보통", "status": "보통",
     "message": "지갑이 적당히 데워지고 있어요. 이 흐름을 유지해보세요"},
    {"min": 80, "max": 99, "emoji": "⚠️", "label": "임계", "status": "주의",
     "message": "열기가 꽤 올라왔어요. 거의 다 썼어요, 조심!"},
    {"min": 100, "max": 119, "emoji": "🔥", "label": "초과", "status": "위험",
     "message": "이미 끓어넘쳤어요. 불필요한 소비를 잠시 멈춰보세요"},
    {"min": 120, "max": None, "emoji": "🚨", "label": "과열", "status": "매우 위험",
     "message": "지갑이 타기 직전이에요. 지금 당장 지출을 멈추고 식혀야 해요"},
]


def classify_temperature(temp: int) -> dict:
    for lv in TEMPERATURE_LEVELS:
        if lv["max"] is None or temp <= lv["max"]:
            if temp >= lv["min"]:
                return lv
    return TEMPERATURE_LEVELS[0]


def my_temperature(db: Session, user: User, year: int, month: int) -> tuple[int, int, int]:
    """(내 온도, 지출액, 월 예산) 반환. 예산 미설정 시 온도 0."""
    budget = db.query(Budget).filter(Budget.user_id == user.id).first()
    spent = monthly_spent(db, user.id, year, month)
    if budget is None or budget.monthly_budget <= 0:
        return 0, spent, 0
    return round(spent / budget.monthly_budget * 100), spent, budget.monthly_budget


def peer_temperature(db: Session, user: User, year: int, month: int) -> int:
    rate = _peer_avg_usage_rate(db, user, year, month)
    return round(rate) if rate is not None else 0
