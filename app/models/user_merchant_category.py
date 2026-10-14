from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserMerchantCategory(Base):
    """사용자별 가맹점 → 카테고리 학습 사전.

    사용자가 거래 카테고리를 제안값/기존값과 다르게 지정하면 (user_id, merchant_name)
    → category 를 저장하고, 같은 사용자의 같은 가맹점은 resolve_category 의 다른
    모든 단계(공용 룰·캐시·LLM)보다 먼저 이 값을 쓴다. 재수정 시 덮어쓴다.

    모든 사용자가 공유하는 LLM 결과 캐시(merchant_category_map)와는 별개다.
    merchant_name 은 category_matcher.normalize_merchant() 결과다.
    """

    __tablename__ = "user_merchant_category"
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_name", name="uq_user_merchant_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    merchant_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
