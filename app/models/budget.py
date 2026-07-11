from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Budget(Base):
    """사용자 예산 (User 1:1)"""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    monthly_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weekly_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_1_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_2_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_3_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_4_budget: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user = relationship("User", back_populates="budget")
