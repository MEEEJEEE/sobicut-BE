from unittest.mock import MagicMock

from app.core.categories import CATEGORIES
from app.models import MerchantCategoryMap
from app.services import category_matcher as cm
from app.services.category_matcher import _RULES, guess_category, normalize_merchant, resolve_category
from tests.conftest import TestingSessionLocal


def test_rules_keys_are_subset_of_categories():
    """룰 매칭이 반환하는 카테고리(_RULES 키)는 반드시 CATEGORIES 안에 있어야 한다.
    오타로 CATEGORIES에 없는 키가 들어가면 그 카테고리는 영원히 매칭되지 않는다."""
    assert set(_RULES) <= set(CATEGORIES), set(_RULES) - set(CATEGORIES)


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
    res = client.post(
        "/transactions/parse",
        json={"message_text": "신한카드 승인되었습니다. [듣도보도못한가게] 5,500원 2026-08-22 14:32"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["category"] is None
