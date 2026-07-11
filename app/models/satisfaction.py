from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Satisfaction(Base):
    """고가 소비(5만원 이상) 만족도 조사 — 7일/30일 후 2회 입력"""

    __tablename__ = "satisfactions"
    __table_args__ = (UniqueConstraint("transaction_id", "day_type", name="uq_satisfaction_day_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True, nullable=False)
    day_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 7일 | 30일
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1(매우 후회) ~ 5(매우 만족)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    transaction = relationship("Transaction", back_populates="satisfactions")
