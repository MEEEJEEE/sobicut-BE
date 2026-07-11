from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Time
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    user = relationship("User", back_populates="transactions")
    transaction_emotions = relationship(
        "TransactionEmotion", back_populates="transaction", cascade="all, delete-orphan"
    )
    satisfactions = relationship("Satisfaction", back_populates="transaction", cascade="all, delete-orphan")

    @property
    def emotion_tags(self):
        return [te.emotion_tag for te in self.transaction_emotions]
