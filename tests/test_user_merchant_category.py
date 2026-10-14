"""사용자 학습 사전(user_merchant_category) — POST/PUT 학습 저장과 resolve_category 우선순위."""
from unittest.mock import MagicMock

from app.models import MerchantCategoryMap, UserMerchantCategory
from app.services import category_matcher as cm
from app.services.category_matcher import learn_user_category, resolve_category
from tests.conftest import SIGNUP_BODY, TestingSessionLocal

# "다이소" 는 공용 룰(CSV 사전)상 생활이다. 학습값은 이와 다른 식비로 검증한다.
RULE_MERCHANT = "다이소"
RULE_CATEGORY = "생활"
UNKNOWN_MERCHANT = "듣도보도못한가게"

TX_BODY = {
    "amount": 10000,
    "type": "expense",
    "category": RULE_CATEGORY,
    "merchant": RULE_MERCHANT,
    "description": None,
    "transaction_date": "2026-07-10",
    "transaction_time": "14:30",
}


def _parse_message(merchant: str) -> str:
    return f"신한카드 승인되었습니다. [{merchant}] 5,500원 2026-08-22 14:32"


def _parse_category(client, headers, merchant: str):
    res = client.post("/transactions/parse", json={"message_text": _parse_message(merchant)}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["category"]


def _learned_rows() -> list[tuple[int, str, str]]:
    db = TestingSessionLocal()
    try:
        return [
            (r.user_id, r.merchant_name, r.category)
            for r in db.query(UserMerchantCategory).order_by(UserMerchantCategory.id).all()
        ]
    finally:
        db.close()


def _user_id(client, headers) -> int:
    return client.get("/users/me", headers=headers).json()["id"]


def _other_user_headers(client) -> dict:
    body = {**SIGNUP_BODY, "email": "other@sookmyung.ac.kr", "nickname": "다른사람"}
    client.post("/auth/signup", json=body)
    res = client.post("/auth/login", json={"email": body["email"], "password": body["password"]})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# --- POST /transactions ---------------------------------------------------


def test_post_with_suggested_category_is_not_learned(client, auth_headers):
    # 제안값(공용 룰: 생활) 그대로 저장 = 팝업 "맞아요" → 학습 안 함
    assert _parse_category(client, auth_headers, RULE_MERCHANT) == RULE_CATEGORY
    res = client.post("/transactions", json=TX_BODY, headers=auth_headers)
    assert res.status_code == 201
    assert _learned_rows() == []


def test_post_with_different_category_is_learned_and_used_by_next_parse(client, auth_headers):
    res = client.post("/transactions", json={**TX_BODY, "category": "식비"}, headers=auth_headers)
    assert res.status_code == 201

    user_id = _user_id(client, auth_headers)
    assert _learned_rows() == [(user_id, "다이소", "식비")]
    # 공용 룰(생활)보다 학습값이 먼저 적용된다.
    assert _parse_category(client, auth_headers, RULE_MERCHANT) == "식비"


def test_post_learns_when_suggestion_is_none(client, auth_headers):
    # 룰·캐시 미스(LLM 은 conftest 에서 차단) → 제안값 None
    assert _parse_category(client, auth_headers, UNKNOWN_MERCHANT) is None
    res = client.post(
        "/transactions",
        json={**TX_BODY, "merchant": UNKNOWN_MERCHANT, "category": "모임/기타"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert [row[1:] for row in _learned_rows()] == [("듣도보도못한가게", "모임/기타")]
    assert _parse_category(client, auth_headers, UNKNOWN_MERCHANT) == "모임/기타"


def test_post_without_merchant_is_not_learned(client, auth_headers):
    res = client.post(
        "/transactions", json={**TX_BODY, "merchant": "   ", "category": "식비"}, headers=auth_headers
    )
    assert res.status_code == 201
    assert _learned_rows() == []


def test_post_does_not_call_llm(client, auth_headers, monkeypatch):
    # 제안값 복원은 allow_llm=False 로만 한다.
    llm = MagicMock(return_value="교통")
    monkeypatch.setattr(cm, "classify_category", llm)
    res = client.post(
        "/transactions",
        json={**TX_BODY, "merchant": UNKNOWN_MERCHANT, "category": "식비"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    llm.assert_not_called()


def test_learning_does_not_affect_other_user(client, auth_headers):
    client.post("/transactions", json={**TX_BODY, "category": "식비"}, headers=auth_headers)
    other = _other_user_headers(client)

    assert _parse_category(client, auth_headers, RULE_MERCHANT) == "식비"
    assert _parse_category(client, other, RULE_MERCHANT) == RULE_CATEGORY


# --- PUT /transactions/{id} -----------------------------------------------


def test_put_with_changed_category_is_learned(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    assert _learned_rows() == []

    res = client.put(f"/transactions/{tx_id}", json={**TX_BODY, "category": "식비"}, headers=auth_headers)
    assert res.status_code == 200
    assert [row[1:] for row in _learned_rows()] == [("다이소", "식비")]


def test_put_with_same_category_is_not_learned(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    res = client.put(f"/transactions/{tx_id}", json={**TX_BODY, "amount": 99000}, headers=auth_headers)
    assert res.status_code == 200
    assert _learned_rows() == []


def test_relearning_same_merchant_overwrites(client, auth_headers):
    tx_id = client.post("/transactions", json={**TX_BODY, "category": "식비"}, headers=auth_headers).json()["id"]
    client.put(f"/transactions/{tx_id}", json={**TX_BODY, "category": "교통"}, headers=auth_headers)

    rows = _learned_rows()
    assert [row[1:] for row in rows] == [("다이소", "교통")]
    assert _parse_category(client, auth_headers, RULE_MERCHANT) == "교통"


def test_put_uses_new_merchant_as_key(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    client.put(
        f"/transactions/{tx_id}",
        json={**TX_BODY, "merchant": "다이소 강남점", "category": "식비"},
        headers=auth_headers,
    )
    assert [row[1:] for row in _learned_rows()] == [("다이소강남점", "식비")]


def test_income_transaction_is_not_learned_on_post_or_put(client, auth_headers):
    # 수입 거래는 제안값과 다른 category 로 생성해도, PUT 으로 category 를 바꿔도 저장 안 함
    income_body = {**TX_BODY, "type": "income", "category": "식비"}
    res = client.post("/transactions", json=income_body, headers=auth_headers)
    assert res.status_code == 201
    assert _learned_rows() == []

    tx_id = res.json()["id"]
    res = client.put(f"/transactions/{tx_id}", json={**income_body, "category": "교통"}, headers=auth_headers)
    assert res.status_code == 200
    assert _learned_rows() == []
    assert _parse_category(client, auth_headers, RULE_MERCHANT) == RULE_CATEGORY


# --- resolve_category / learn_user_category -------------------------------


def test_resolve_category_user_dictionary_precedes_rules(client, auth_headers):
    user_id = _user_id(client, auth_headers)
    db = TestingSessionLocal()
    try:
        db.add(UserMerchantCategory(user_id=user_id, merchant_name="다이소", category="식비"))
        db.commit()
        assert resolve_category(db, "다이소", user_id=user_id) == "식비"
        assert resolve_category(db, "다이소", user_id=user_id + 1) == RULE_CATEGORY
        assert resolve_category(db, "다이소") == RULE_CATEGORY
    finally:
        db.close()


def test_resolve_category_allow_llm_false_skips_llm_and_cache_write(monkeypatch):
    llm = MagicMock(return_value="교통")
    monkeypatch.setattr(cm, "classify_category", llm)
    db = TestingSessionLocal()
    try:
        assert resolve_category(db, "정체불명상호 111", allow_llm=False) is None
        llm.assert_not_called()
        assert db.query(MerchantCategoryMap).count() == 0
    finally:
        db.close()


def test_learn_user_category_swallows_db_errors():
    # 학습 저장 실패는 rollback + 로그만 하고 예외를 올리지 않는다.
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit.side_effect = RuntimeError("db down")

    learn_user_category(db, 1, "expense", "다이소", "식비")

    db.rollback.assert_called_once()


def test_learn_user_category_skips_invalid_category_and_empty_merchant():
    db = MagicMock()
    learn_user_category(db, 1, "expense", "다이소", "없는카테고리")
    learn_user_category(db, 1, "expense", "   ", "식비")
    learn_user_category(db, 1, "expense", None, "식비")
    learn_user_category(db, 1, "income", "다이소", "식비")
    db.query.assert_not_called()
    db.add.assert_not_called()
