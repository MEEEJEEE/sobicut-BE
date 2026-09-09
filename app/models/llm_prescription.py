from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LlmPrescription(Base):
    """주기별 LLM 소비 처방(개선 제안 3개) 캐시.

    동일한 (user_id, period_type, period_start) 조합당 1건만 저장하고,
    재요청 시 LLM을 다시 호출하지 않고 캐시된 결과를 재사용한다.
    """

    __tablename__ = "llm_prescriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_start", name="uq_llm_prescription_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 예: "weekly"
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[list] = mapped_column(JSON, nullable=False)  # 처방 3개 배열
    model_name: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 예: "gemini-2.5-flash"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    user = relationship("User")
