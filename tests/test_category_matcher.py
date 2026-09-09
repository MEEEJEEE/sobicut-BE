from unittest.mock import MagicMock

from app.core.categories import CATEGORIES
from app.models import MerchantCategoryMap
from app.services import category_matcher as cm
from app.services.category_matcher import (
    _PREFIX_RULES,
    _RULES,
    _sort_by_len_desc,
    guess_category,
    normalize_merchant,
    resolve_category,
)
from tests.conftest import TestingSessionLocal


def test_rule_keys_are_subset_of_categories():
    """룰 매칭이 반환하는 카테고리(_RULES / _PREFIX_RULES 키)는 반드시 CATEGORIES
    안에 있어야 한다. 오타로 CATEGORIES에 없는 키가 들어가면 그 카테고리는
    영원히 매칭되지 않는다."""
    assert set(_RULES) <= set(CATEGORIES), set(_RULES) - set(CATEGORIES)
    assert set(_PREFIX_RULES) <= set(CATEGORIES), set(_PREFIX_RULES) - set(CATEGORIES)


def test_no_duplicate_keywords_across_rule_dicts():
    """같은 키워드가 _RULES / _PREFIX_RULES 여러 곳에 등록되면 어느 카테고리로
    가는지 길이·정렬에 좌우되므로 금지한다."""
    all_keywords = [kw for keywords in _RULES.values() for kw in keywords]
    all_keywords += [kw for keywords in _PREFIX_RULES.values() for kw in keywords]
    dupes = sorted({kw for kw in all_keywords if all_keywords.count(kw) > 1})
    assert not dupes, dupes


def test_sort_by_len_desc_orders_by_keyword_length_and_is_stable():
    result = _sort_by_len_desc(
        {"식비": ["짧", "매우김키워드", "중간키워드"], "생활": ["또중간키워"]}
    )
    lengths = [len(kw) for kw, _ in result]
    assert lengths == sorted(lengths, reverse=True)
    # 같은 길이(5)는 dict/리스트 삽입 순서 유지: "중간키워드"(식비) → "또중간키워"(생활)
    five = [(kw, cat) for kw, cat in result if len(kw) == 5]
    assert five == [("중간키워드", "식비"), ("또중간키워", "생활")]


def test_guess_category_prefix_tier_and_convenience_store_move():
    assert guess_category("씨유역삼점") == "생활"
    assert guess_category("GS25강남") == "생활"  # 편의점 5종 식비 → 생활 이동 반영
    assert guess_category("PC방") == "문화/여가"  # 기존 동작 유지


def test_guess_category_cu_contains_no_longer_misclassifies():
    """"CU" 를 _RULES(contains) → _PREFIX_RULES(startswith) 로 옮겨, 라틴 문자
    상호에 우연히 CU 가 들어가도 편의점(식비)으로 오분류하지 않는다."""
    assert guess_category("DOCUMENT SECURITY") != "식비"


def test_guess_category_strips_pg_prefix():
    # PG사 접두사가 붙어도 " - " 뒤쪽으로 매칭한다.
    # (사전 신규 항목에 비의존: 기존 "카페"(식비) 규칙으로 검증)
    assert guess_category("카카오페이_중소3 - 레벨업PC카페 수유역점") == "식비"
    # 구분자가 여러 번이면 마지막 것 기준으로 뒤쪽 사용
    assert guess_category("PG_A - PG_B - 스타벅스 강남") == "식비"


def test_guess_category_falls_back_to_original_when_tail_unmatched():
    # 뒤쪽("(주)카카오모빌리티")에는 매칭 키워드가 없고 앞쪽("카카오T_바이크")에
    # 유효 정보가 있는 경우 → 원본으로 재시도해서 잡는다.
    assert guess_category("카카오T_바이크 - (주)카카오모빌리티") == "교통"


def test_guess_category_tail_match_skips_original_fallback(monkeypatch):
    # 뒤쪽으로 매칭되면 원본 재시도를 하지 않는다 (_match_rules 1회 호출).
    calls = []
    real = cm._match_rules

    def spy(text):
        calls.append(text)
        return real(text)

    monkeypatch.setattr(cm, "_match_rules", spy)
    assert guess_category("카카오페이_중소3 - 스타벅스 강남") == "식비"
    assert calls == ["스타벅스 강남".upper()]


def test_guess_category_without_pg_separator_unchanged():
    assert guess_category("스타벅스 강남점") == "식비"
    assert guess_category("듣도보도못한상호명123") is None


def test_guess_category_empty_tail_falls_back_to_original():
    # " - " 로 끝나 뒤쪽이 비면 원본을 사용
    assert guess_category("스타벅스 - ") == "식비"


def test_no_llm_calls_fixture_patches_the_symbol_resolve_category_uses():
    """conftest 의 _no_llm_calls autouse fixture 가 올바른 경로를 패치했는지 확인.
    (잘못된 경로를 패치하면 조용히 무력화되고 실제 Gemini 호출이 나간다.)"""
    assert cm.classify_category("아무거나") is None
    assert getattr(cm.classify_category, "__name__", "") == "<lambda>"


def test_no_llm_calls_fixture_allows_per_test_override(monkeypatch):
    """LLM 반환값이 필요한 테스트는 각자 monkeypatch 로 fixture 를 덮어쓸 수 있어야 한다."""
    monkeypatch.setattr(cm, "classify_category", lambda name: "식비")
    assert cm.classify_category("x") == "식비"


def test_normalize_merchant():
    assert normalize_merchant("스타벅스 강남 2호점") == "스타벅스강남2호점"
    assert normalize_merchant("  GS25  ") == "gs25"
    assert normalize_merchant("Coffee Bean") == "coffeebean"
    assert normalize_merchant("") is None
    assert normalize_merchant("   ") is None
    assert normalize_merchant(None) is None


def test_resolve_category_rule_hit_skips_cache_and_llm(monkeypatch):
    """룰이 맞으면 캐시 조회도 LLM 호출도 하지 않는다 (룰 우선순위)."""
    llm = MagicMock()
    monkeypatch.setattr(cm, "classify_category", llm)
    db = MagicMock()

    assert resolve_category(db, "스타벅스 역삼점") == "식비"

    db.query.assert_not_called()
    llm.assert_not_called()


def test_resolve_category_cache_hit_skips_llm(monkeypatch):
    """룰 실패 + 캐시 히트면 LLM을 호출하지 않는다."""
    llm = MagicMock()
    monkeypatch.setattr(cm, "classify_category", llm)

    db = TestingSessionLocal()
    try:
        db.add(MerchantCategoryMap(normalized_name="테스트상점", category="교통", source="llm"))
        db.commit()

        assert resolve_category(db, "테스트 상점") == "교통"
        llm.assert_not_called()
    finally:
        db.close()


def test_resolve_category_llm_invalid_value_returns_none_and_not_cached(monkeypatch):
    """LLM이 CATEGORIES에 없는 값을 반환하면 None이고 캐시에 저장되지 않는다."""
    monkeypatch.setattr(cm, "classify_category", lambda name: "없는카테고리")

    db = TestingSessionLocal()
    try:
        assert resolve_category(db, "정체불명상호 12345") is None
        assert db.query(MerchantCategoryMap).count() == 0
    finally:
        db.close()


def test_resolve_category_llm_raises_returns_none(monkeypatch):
    """LLM이 예외를 던져도 None을 반환하고 예외가 밖으로 새지 않는다."""
    def _boom(name):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(cm, "classify_category", _boom)

    db = TestingSessionLocal()
    try:
        assert resolve_category(db, "정체불명상호 67890") is None
        assert db.query(MerchantCategoryMap).count() == 0
    finally:
        db.close()


def test_guess_category_known_merchants():
    assert guess_category("스타벅스") == "식비"
    assert guess_category("무신사") == "쇼핑/패션"
    assert guess_category("카카오T") == "교통"
    assert guess_category("CGV 강남") == "문화/여가"
    assert guess_category("다이소") == "생활"


def test_guess_category_unknown_returns_none():
    assert guess_category("듣도보도못한상호명123") is None
    assert guess_category(None) is None
    assert guess_category("") is None


def test_transactions_parse_includes_category(client, auth_headers):
    res = client.post(
        "/transactions/parse",
        json={"message_text": "신한카드 승인되었습니다. [스타벅스] 5,500원 2026-08-22 14:32"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["category"] == "식비"


def test_transactions_parse_category_null_when_unmatched(client, auth_headers):
    # 룰·캐시 미스 + LLM 도 분류 실패 → category=null 로 200 정상 응답.
    # (conftest 의 _no_llm_calls autouse fixture 가 LLM 호출을 차단한다.)
    res = client.post(
        "/transactions/parse",
        json={"message_text": "신한카드 승인되었습니다. [듣도보도못한가게] 5,500원 2026-08-22 14:32"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["category"] is None
