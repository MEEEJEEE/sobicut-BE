"""BPTI (Buying Pattern Type Indicator): 주력 감정 태그 기반 소비 성격 유형"""
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models import EmotionTag, Transaction, TransactionEmotion

BPTI_TYPES = {
    "스트레스": {"type": "FIRE", "label": "불지옥", "definition": "홧김 비용의 지배자",
             "message": "화가 날 때 지갑을 여는 타입! 스트레스 해소법을 돈 쓰기 말고 다른 걸로 찾아봐요."},
    "무의식": {"type": "FOG", "label": "안개 속", "definition": "새어 나가는 돈의 달인",
            "message": "정신 차려보니 결제 완료? 멍하니 쓴 작은 돈들이 모여 큰 산이 되고 있어요."},
    "귀찮음": {"type": "LAZY", "label": "귀찮니즘", "definition": "편리함과 돈을 바꾼 자",
            "message": "귀찮음으로 시작된 배달과 택시가 삶의 동반자군요. 몸은 편하지만 지갑은 비명을 지르고 있어요!"},
    "성취": {"type": "REWARD", "label": "보상왕", "definition": "성취를 결제로 증명하는 자",
           "message": "고생한 나를 아낄 줄 아는 타입! 계획적인 보상이라면 온도는 안전해요."},
    "행복": {"type": "JOY", "label": "행복 요정", "definition": "인생의 즐거움을 아는 자",
           "message": "좋아하는 것에 돈을 쓸 때 가장 빛나요. 행복 지수가 지갑 온도보다 높네요!"},
    "고마움": {"type": "GIVER", "label": "기부 천사", "definition": "관계에 진심인 큰 손",
            "message": "주변 사람들의 행복이 곧 나의 행복! 온기가 가득한 지갑입니다. 당신, 혹시 천사인가요?"},
}

EMOTION_NAMES = list(BPTI_TYPES.keys())


def emotion_tag_counts(db: Session, user_id: int, year: int, month: int) -> dict[str, int]:
    """기간 내 지출 거래의 감정 태그별 횟수"""
    rows = (
        db.query(EmotionTag.name, func.count(TransactionEmotion.id))
        .join(TransactionEmotion, TransactionEmotion.emotion_tag_id == EmotionTag.id)
        .join(Transaction, Transaction.id == TransactionEmotion.transaction_id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .group_by(EmotionTag.name)
        .all()
    )
    counts = {name: 0 for name in EMOTION_NAMES}
    counts.update(dict(rows))
    return counts


def emotion_radar(db: Session, user_id: int, year: int, month: int) -> dict[str, int]:
    """감정 태그별 비율(%) — 6각형 레이더 그래프용"""
    counts = emotion_tag_counts(db, user_id, year, month)
    total = sum(counts.values())
    if total == 0:
        return {name: 0 for name in EMOTION_NAMES}
    return {name: round(cnt / total * 100) for name, cnt in counts.items()}


def get_bpti(db: Session, user_id: int, year: int, month: int) -> dict | None:
    """주력 태그 기반 BPTI 유형. 태그 데이터 없으면 None."""
    counts = emotion_tag_counts(db, user_id, year, month)
    if sum(counts.values()) == 0:
        return None
    top = max(counts, key=counts.get)
    return BPTI_TYPES[top]
