from sqlalchemy.orm import Session

from app.models import User

# (레벨, 이름, 필요 누적 경험치)
LEVELS = [
    (1, "슬라임", 0),
    (2, "씨앗", 100),
    (3, "몬스터", 300),
    (4, "기사", 600),
    (5, "금융의 신", 1000),
]

LEVEL_DESCRIPTIONS = {
    1: "이제 막 소비 관리를 시작했어요!",
    2: "좋은 소비 습관의 씨앗이 자라고 있어요!",
    3: "소비 습관이 조금씩 성장하고 있어요!",
    4: "절제된 소비의 기사가 되었어요!",
    5: "당신은 금융의 신! 소비를 완전히 지배하고 있어요!",
}

# 경험치 지급 기준
EXP_TRANSACTION = 5      # 거래 기록
EXP_EMOTION_TAG = 3      # 감정 태그 입력
EXP_SATISFACTION = 10    # 만족도 입력


def calc_level(exp: int) -> int:
    level = 1
    for lv, _, required in LEVELS:
        if exp >= required:
            level = lv
    return level


def add_exp(db: Session, user: User, amount: int) -> None:
    """경험치 지급 후 레벨 재계산 (commit은 호출부에서)"""
    user.exp += amount
    user.level = calc_level(user.exp)


def get_level_info(user: User) -> dict:
    name = dict((lv, nm) for lv, nm, _ in LEVELS)[user.level]
    next_exp = None
    for lv, _, required in LEVELS:
        if lv == user.level + 1:
            next_exp = required
    return {
        "level": user.level,
        "level_name": name,
        "current_exp": user.exp,
        "next_level_exp": next_exp,  # 최고 레벨이면 null
        "description": LEVEL_DESCRIPTIONS[user.level],
    }
