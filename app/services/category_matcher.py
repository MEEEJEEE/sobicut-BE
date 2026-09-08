"""가맹점명 기반 소비 카테고리 자동 매칭.

1차는 규칙/키워드 기반(`guess_category`) — 비용·지연 없이 즉시 응답한다.
룰로 분류하지 못한 가맹점은 `resolve_category()`가 캐시(merchant_category_map)
→ LLM(`category_llm.classify_category`) 순으로 fallback 하고, LLM 결과는
캐시에 저장해 재사용한다. 모든 단계 실패 시 None 을 반환하며, 프론트는
사용자가 직접 카테고리를 고르도록 안내하면 된다.

우선순위(룰 > 캐시 > LLM)는 고정이다. `_RULES` 가 갱신되면 그 결과가
과거 LLM 캐시보다 우선해야 하므로 룰 매칭이 반드시 캐시보다 먼저다.

룰 매칭(`_match_rules`)은 2티어다:
  (1) `_PREFIX_RULES` — startswith. contains 로 넣으면 라틴 문자 상호에
      오분류되는 짧은 키워드("DOCUMENT" 안의 "CU" 등)를 여기 둔다.
  (2) `_RULES` — contains.
두 티어 모두 키워드 길이 내림차순으로 검사한다(_..._BY_LEN). 짧은 키워드가
긴 키워드를 가로채지 못하게 하기 위함이며, 카테고리 dict 순서에는 의존하지
않는다. 정렬은 모듈 로드 시 1회만 계산한다.

`guess_category` 는 PG사 접두사(" - ") 대응으로 이 매칭을 뒤쪽 → 원본 순으로
최대 2회 호출한다.
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
        "맥도날드", "버거킹", "롯데리아", "배달의민족", "요기요", "쿠팡이츠",
        "김밥", "국밥", "고깃집", "족발", "보쌈", "떡볶이",
    ],
    "교통": [
        "택시", "카카오T", "카카오택시", "버스", "지하철", "티맵", "주유소", "SK에너지",
        "GS칼텍스", "S-OIL", "현대오일뱅크", "코레일", "ITX", "SRT", "KTX",
    ],
    "생활": [
        "다이소", "올리브영", "약국", "세탁", "이마트", "홈플러스", "롯데마트", "드럭스토어",
        "GS25", "세븐일레븐", "이마트24", "미니스톱",
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

# startswith 로 매칭할 규칙. contains 로 넣으면 라틴 문자 상호에 오분류되는
# 짧은 키워드를 여기 둔다("CU" 가 "DOCUMENT"/"SECURITY" 안에 잡히는 문제).
# 본격적인 사전(수백 건)은 별도 작업에서 투입 예정 — 지금은 CU 이동분만 둔다.
_PREFIX_RULES: dict[str, list[str]] = {
    "생활": ["씨유", "CU"],
}

# PG사 접두사 구분자. "카카오페이_중소3 - 레벨업PC카페 수유역점" 처럼 앞에 PG사
# 이름이 붙은 실거래가 많다. guess_category 가 이 구분자 뒤쪽 → 원본 순으로
# 최대 2회 매칭을 시도한다.
_PG_SEPARATOR = " - "


def _sort_by_len_desc(rules: dict[str, list[str]]) -> list[tuple[str, str]]:
    """dict 를 (키워드대문자, 카테고리) 플랫 리스트로 펼쳐 키워드 길이 내림차순 정렬.

    카테고리 dict 순서가 아니라 "가장 구체적인(긴) 키워드" 가 이기게 한다.
    같은 길이는 stable sort 라 dict/리스트 삽입 순서를 유지한다.
    모듈 로드 시 1회만 호출한다(매 매칭마다 정렬하지 않는다).
    """
    pairs = [(kw, category) for category, keywords in rules.items() for kw in keywords]
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return [(kw.upper(), category) for kw, category in pairs]


_PREFIX_RULES_BY_LEN: list[tuple[str, str]] = _sort_by_len_desc(_PREFIX_RULES)
_RULES_BY_LEN: list[tuple[str, str]] = _sort_by_len_desc(_RULES)


def _match_rules(text: str) -> str | None:
    """대문자로 변환된 상호명에 2티어 매칭: (1) `_PREFIX_RULES` startswith →
    (2) `_RULES` contains. 두 티어 모두 키워드 길이 내림차순으로 검사한다."""
    for kw, category in _PREFIX_RULES_BY_LEN:
        if text.startswith(kw):
            return category
    for kw, category in _RULES_BY_LEN:
        if kw in text:
            return category
    return None


def guess_category(merchant: str | None) -> str | None:
    """가맹점명으로 카테고리를 추정한다. 매칭되는 키워드가 없으면 None (수동 태그 유도).

    PG사 접두사("카카오T_바이크 - (주)카카오모빌리티") 대응: `_PG_SEPARATOR` 가
    있으면 마지막 구분자 뒤쪽으로 먼저 매칭을 시도하고, 실패하면 원본으로 다시
    시도한다. 뒤쪽에만 유효 정보가 있는 경우와 앞쪽에만 있는 경우를 모두
    잡는다. 이 전처리는 이 함수 안에서만 적용하고 `normalize_merchant()` 는
    건드리지 않는다.

    룰 전용 매칭. 캐시/LLM fallback 이 필요하면 `resolve_category()` 를 쓴다.
    시그니처·반환 타입은 다른 호출자(테스트 등) 영향 방지를 위해 바꾸지 않는다.
    """
    if not merchant:
        return None

    if _PG_SEPARATOR in merchant:
        tail = merchant.rsplit(_PG_SEPARATOR, 1)[1]
        if tail:
            hit = _match_rules(tail.upper())
            if hit is not None:
                return hit

    return _match_rules(merchant.upper())


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
