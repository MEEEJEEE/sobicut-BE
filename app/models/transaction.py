from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    """지출/수입 거래 내역"""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # income | expense
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transaction_time: Mapped[time] = mapped_column(Time, nullable=False)
    # 충동 점수 β2(금액 부담) 계산용 — 구매 시점에 느낀 경제적 부담 1(전혀 없음)~5(매우 큼)
    subjective_burden: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 신중한 소비 보너스 exp 중복 지급 방지 (거래 생성 시 또는 태그 등록 후 최대 1회)
    low_impulse_bonus_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    user = relationship("User", back_populates="transactions")
    transaction_emotions = relationship(
        "TransactionEmotion", back_populates="transaction", cascade="all, delete-orphan"
    )
    transaction_tags = relationship(
        "TransactionTag", back_populates="transaction", cascade="all, delete-orphan"
    )
    satisfactions = relationship("Satisfaction", back_populates="transaction", cascade="all, delete-orphan")

    @property
    def emotion_tags(self):
        return [te.emotion_tag for te in self.transaction_emotions]

    @property
    def tags(self):
        """자유 텍스트 소비 태그 (기록용, 충동 점수 미반영)"""
        return [t.content for t in self.transaction_tags]
