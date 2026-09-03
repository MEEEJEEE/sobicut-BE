from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TransactionTag(Base):
    """자유 텍스트 소비 태그 (기록용) — 점수 계산에 쓰이는 EmotionTag(5개 고정 심리특성)와
    별개이며 충동 점수(app/services/impulse.py)에 전혀 영향을 주지 않는다."""

    __tablename__ = "transaction_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    transaction = relationship("Transaction", back_populates="transaction_tags")
