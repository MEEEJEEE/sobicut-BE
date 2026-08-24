from sqlalchemy.orm import Session

from app.models import EmotionTag

EMOTION_TAGS = [
    # 즉흥/회피형 의사결정
    {"name": "스트레스", "type": "negative"},
    {"name": "즉흥성", "type": "negative"},
    {"name": "비교회피", "type": "negative"},
    # 숙고/가치형 의사결정
    {"name": "충분한숙고", "type": "positive"},
    {"name": "장기적가치", "type": "positive"},
]


def seed_emotion_tags(db: Session) -> None:
    """구매 결정 심리특성 5종 초기 데이터. 이미 있으면 건너뜀."""
    if db.query(EmotionTag).count() > 0:
        return
    for tag in EMOTION_TAGS:
        db.add(EmotionTag(**tag))
    db.commit()
