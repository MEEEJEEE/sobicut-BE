from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmotionTag(Base):
    """구매 결정 심리특성 마스터 (5종, BPTI 유형과 1:1) — 스트레스/즉흥성/비교회피/충분한숙고/장기적가치"""

    __tablename__ = "emotion_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # negative | positive

    transaction_emotions = relationship("TransactionEmotion", back_populates="emotion_tag")


class TransactionEmotion(Base):
    """거래-심리특성 태그 매핑 (N:M, 거래당 최대 4개: 계획여부 1개 + 소비특성 최대 3개)"""

    __tablename__ = "transaction_emotions"
    __table_args__ = (UniqueConstraint("transaction_id", "emotion_tag_id", name="uq_transaction_emotion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True, nullable=False)
    emotion_tag_id: Mapped[int] = mapped_column(ForeignKey("emotion_tags.id"), nullable=False)

    transaction = relationship("Transaction", back_populates="transaction_emotions")
    emotion_tag = relationship("EmotionTag", back_populates="transaction_emotions")
