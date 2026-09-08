from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantCategoryMap(Base):
    """가맹점명 → 카테고리 매핑 캐시.

    룰 매칭(category_matcher.guess_category)으로 분류하지 못한 가맹점을
    LLM으로 1회 분류한 뒤 그 결과를 저장해 두고, 이후 같은 가맹점은
    LLM 재호출 없이 재사용한다.

    normalized_name 은 category_matcher.normalize_merchant() 결과
    (공백 전부 제거 + 소문자화)다. 카테고리 테이블이 따로 없으므로
    category 는 FK 가 아닌 문자열이다.
    """

    __tablename__ = "merchant_category_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False)  # 'llm' | 'manual'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
