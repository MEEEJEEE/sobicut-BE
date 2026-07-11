from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """사용자 (거주형태/소득구간은 또래 그룹핑에 사용)"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt 해시
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    residence_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 자취 | 기숙사 | 통학
    income_level: Mapped[str] = mapped_column(String(20), nullable=False)  # under-30 | 30-60 | 60-100 | over-100
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    exp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # soft delete

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    budget = relationship("Budget", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
