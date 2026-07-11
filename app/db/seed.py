from sqlalchemy.orm import Session

from app.models import EmotionTag

EMOTION_TAGS = [
    # 결핍형 소비 (부정)
    {"name": "스트레스", "type": "negative"},
    {"name": "무의식", "type": "negative"},
    {"name": "귀찮음", "type": "negative"},
    # 충만형 소비 (긍정)
    {"name": "성취", "type": "positive"},
    {"name": "행복", "type": "positive"},
    {"name": "고마움", "type": "positive"},
]


def seed_emotion_tags(db: Session) -> None:
    """감정 태그 6종 초기 데이터. 이미 있으면 건너뜀."""
    if db.query(EmotionTag).count() > 0:
        return
    for tag in EMOTION_TAGS:
        db.add(EmotionTag(**tag))
    db.commit()
