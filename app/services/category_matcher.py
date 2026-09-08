"""가맹점명 기반 소비 카테고리 자동 매칭.

1차는 규칙/키워드 기반(`guess_category`) — 비용·지연 없이 즉시 응답한다.
룰로 분류하지 못한 가맹점은 `resolve_category()`가 캐시(merchant_category_map)
→ LLM(`category_llm.classify_category`) 순으로 fallback 하고, LLM 결과는
캐시에 저장해 재사용한다. 모든 단계 실패 시 None 을 반환하며, 프론트는
사용자가 직접 카테고리를 고르도록 안내하면 된다.

우선순위(룰 > 캐시 > LLM)는 고정이다. `_RULES` 가 갱신되면 그 결과가
과거 LLM 캐시보다 우선해야 하므로 룰 매칭이 반드시 캐시보다 먼저다.
"""
import logging
import re

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.categories import CATEGORIES
from app.models import MerchantCategoryMap
from app.services.category_llm import classify_category

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")

_RULES: dict[str, list[str]] = {
    "식비": [
        "스타벅스", "이디야", "투썸", "커피", "카페", "식당", "분식", "치킨", "피자", "버거",
        "맥도날드", "버거킹", "롯데리아", "배달의민족", "요기요", "쿠팡이츠", "GS25", "CU",
        "세븐일레븐", "이마트24", "미니스톱", "김밥", "국밥", "고깃집", "족발", "보쌈", "떡볶이",
    ],
    "교통": [
        "택시", "카카오T", "카카오택시", "버스", "지하철", "티맵", "주유소", "SK에너지",
        "GS칼텍스", "S-OIL", "현대오일뱅크", "코레일", "ITX", "SRT", "KTX",
    ],
    "생활": [
        "다이소", "올리브영", "약국", "세탁", "이마트", "홈플러스", "롯데마트", "드럭스토어",
    ],
    "쇼핑/패션": [
        "무신사", "쿠팡", "지마켓", "11번가", "옥션", "티몬", "위메프", "올웨이즈", "백화점",
        "ZARA", "유니클로", "나이키", "아디다스", "29CM", "W컨셉",
    ],
    "자기계발": [
        "교보문고", "YES24", "알라딘", "인강", "학원", "클래스101", "멀티캠퍼스", "패스트캠퍼스",
        "헬스장", "필라테스", "요가",
    ],
    "문화/여가": [
        "CGV", "메가박스", "롯데시네마", "넷플릭스", "왓챠", "디즈니플러스", "멜론", "지니뮤직",
        "PC방", "노래방", "볼링",
    ],
    "고정지출": [
        "SKT", "KT", "LG유플러스", "통신", "보험", "월세", "관리비", "가스", "전기",
    ],
}


def guess_category(merchant: str | None) -> str | None:
    """가맹점명으로 카테고리를 추정한다. 매칭되는 키워드가 없으면 None (수동 태그 유도).

    룰 전용 매칭. 캐시/LLM fallback 이 필요하면 `resolve_category()` 를 쓴다.
    시그니처·동작은 다른 호출자(테스트 등) 영향 방지를 위해 바꾸지 않는다.
    """
    if not merchant:
        return None
    text = merchant.upper()
    for category, keywords in _RULES.items():
        for kw in keywords:
            if kw.upper() in text:
                return category
    return None


def normalize_merchant(merchant: str | None) -> str | None:
    """캐시 키·LLM 입력용 정규화: 공백을 전부 제거하고 소문자로 통일한다.

    "스타벅스 강남점" 과 "스타벅스강남점" 을 같은 키로 모으기 위한 것이며,
    지점명까지 떼지는 않는다("스타벅스강남점" != "스타벅스역삼점").
    guess_category(룰 매칭)에는 이 정규화를 적용하지 않는다 — 원본을 넘긴다.
    """
    if not merchant:
        return None
    normalized = _WHITESPACE_RE.sub("", merchant).lower()
    return normalized or None


def _cache_category(db: Session, normalized_name: str, category: str) -> None:
    """LLM 분류 결과를 저장한다.

    동시 요청으로 같은 normalized_name 이 들어와도 ON CONFLICT DO NOTHING 으로
    무시한다. 저장 실패(연결 오류·경합 등)는 로그만 남기고 삼킨다 — 이미 확보한
    매칭 결과에는 영향을 주지 않는다.
    """
    stmt = (
        pg_insert(MerchantCategoryMap)
        .values(normalized_name=normalized_name, category=category, source="llm")
        .on_conflict_do_nothing(index_elements=["normalized_name"])
    )
    try:
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning(
            "카테고리 캐시 저장 실패 (무시): %s -> %s", normalized_name, category, exc_info=True
        )


def resolve_category(db: Session, merchant: str | None) -> str | None:
    """가맹점명으로 카테고리를 결정한다. 우선순위: 룰 > 캐시 > LLM.

    어떤 단계에서도 예외를 밖으로 내지 않는다 (parse 응답은 실패하면 안 되고
    category=null 로 정상 응답해야 한다). 최종 실패 시 None.
    """
    rule_hit = guess_category(merchant)
    if rule_hit is not None:
        return rule_hit

    normalized = normalize_merchant(merchant)
    if normalized is None:
        return None

    cached = (
        db.query(MerchantCategoryMap)
        .filter(MerchantCategoryMap.normalized_name == normalized)
        .first()
    )
    if cached is not None:
        return cached.category

    try:
        category = classify_category(normalized)
    except Exception:
        logger.warning("카테고리 LLM 호출 중 예외 (무시)", exc_info=True)
        return None

    if category is None:
        return None
    if category not in CATEGORIES:
        logger.warning("카테고리 LLM 이 허용되지 않은 값 반환 (저장 안 함): %r", category)
        return None

    _cache_category(db, normalized, category)
    return category
