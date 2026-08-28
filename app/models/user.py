from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """사용자 (거주형태/소득구간은 또래 그룹핑에 사용)"""

    __tablename__ = "users"
    __table_args__ = (
        # 탈퇴(soft delete) 계정은 이메일 유니크 제약에서 제외 → 탈퇴 이메일로 재가입 가능
        Index(
            "ix_users_email_active",
            "email",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  # bcrypt 해시
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    residence_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 자취 | 기숙사 | 통학
    income_level: Mapped[str] = mapped_column(String(20), nullable=False)  # under-30 | 30-60 | 60-100 | over-100
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_budget_bonus_month: Mapped[str | None] = mapped_column(String(7), nullable=True)  # "YYYY-MM", 중복 지급 방지
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # soft delete

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    budget = relationship("Budget", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
