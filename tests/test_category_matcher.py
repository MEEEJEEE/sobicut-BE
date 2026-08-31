from app.services.category_matcher import guess_category


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
