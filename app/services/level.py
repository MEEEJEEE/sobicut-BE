from sqlalchemy.orm import Session

from app.models import User

# (레벨, 이름, 필요 누적 경험치)
# 임계값은 exp 지급 기준 개편(거래 기록 2, 저충동 보너스 5, 월간 예산 준수 15 등)에
# 맞춰 재산정한 값 — 데모에서 몇 번의 조작만으로도 진행 상황이 보이도록 낮게 잡았다.
LEVELS = [
    (0, "슬라임 커티", 0),
    (1, "씨앗 커티", 10),
    (2, "박스 몬스터", 40),
    (3, "쉴드 가디언", 90),
    (4, "위저드 커티", 160),
    (5, "나이트 커티", 250),
    (6, "금융의 신 커티", 400),
]

LEVEL_DESCRIPTIONS = {
    0: "소비 정령이 형태를 잃고 흘러내리고 있어요. 올바른 소비 습관으로 형태를 되찾아주세요!",
    1: "작은 형태를 되찾았어요! 좋은 소비 습관의 씨앗이 자라고 있어요.",
    2: "지갑의 뼈대가 잡히고 있어요! 소비 습관이 조금씩 성장하고 있어요.",
    3: "오! 정령이 소비 유혹을 막아내기 시작했어요. 불필요한 지출을 잘 견디고 있군요!",
    4: "자산을 지키는 강력한 힘이 생겼어요! 이제 웬만한 바람에도 흔들리지 않는군요?",
    5: "완전한 수호자의 탄생! 소비 유혹을 완전히 통제하는 당신은 진정한 지갑의 주인입니다.",
    6: "정령이 완전히 각성해 금융의 신으로 성장했어요! 이제 소비를 넘어 자산을 다루는 단계예요.",
}

# 경험치 지급 기준 — 단순 기록 행위는 낮게, 좋은 소비 습관에는 보너스로 방향을 맞춘다.
EXP_TRANSACTION = 2          # 거래 기록
EXP_EMOTION_TAG = 2          # 감정 태그 입력
EXP_SATISFACTION = 10        # 만족도 입력 (자주 없는 행동이라 그대로 유지)
EXP_LOW_IMPULSE_BONUS = 5    # 신중한 소비(충동 점수 낮음) 보너스
EXP_BUDGET_COMPLIANCE_BONUS = 15  # 월간 예산 준수 마감 보너스

LOW_IMPULSE_THRESHOLD = 30   # 이 점수 미만이면 "신중한 소비"로 보너스 지급


def calc_level(exp: int) -> int:
    level = 0
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
