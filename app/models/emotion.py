from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmotionTag(Base):
    """감정 태그 마스터 (6종: 결핍형 3 + 충만형 3)"""

    __tablename__ = "emotion_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # negative | positive

    transaction_emotions = relationship("TransactionEmotion", back_populates="emotion_tag")


class TransactionEmotion(Base):
    """거래-감정 태그 매핑 (N:M)"""

    __tablename__ = "transaction_emotions"
    __table_args__ = (UniqueConstraint("transaction_id", "emotion_tag_id", name="uq_transaction_emotion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True, nullable=False)
    emotion_tag_id: Mapped[int] = mapped_column(ForeignKey("emotion_tags.id"), nullable=False)

    transaction = relationship("Transaction", back_populates="transaction_emotions")
    emotion_tag = relationship("EmotionTag", back_populates="transaction_emotions")
