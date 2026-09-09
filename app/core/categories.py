"""소비 카테고리 단일 정의.

이전에는 라우터(app/routers/transactions.py)의 검증용 집합과
룰 매칭(app/services/category_matcher.py)의 `_RULES` 키가 따로 관리돼
서로 어긋났다("모임/기타" 유무 등). 카테고리를 쓰는 모든 곳
(거래 생성 검증, LLM 분류 enum, 룰 키 검증 테스트)이 이 상수를 참조한다.

순서가 있는 튜플이다 — LLM responseSchema의 enum 목록으로 그대로 쓰이므로
정렬 대신 의미 순서를 고정한다.
"""

CATEGORIES: tuple[str, ...] = (
    "식비",
    "교통",
    "생활",
    "쇼핑/패션",
    "자기계발",
    "문화/여가",
    "고정지출",
    "모임/기타",
)
