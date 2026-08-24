from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SatisfactionNotificationLog(Base):
    """만족도 조사 알림(7일/30일) 발송 여부 기록 — 배치 중복 발송 방지용."""

    __tablename__ = "satisfaction_notification_logs"
    __table_args__ = (
        UniqueConstraint("transaction_id", "day_type", name="uq_satisfaction_notification_log"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True, nullable=False)
    day_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 7일 | 30일
    notified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
