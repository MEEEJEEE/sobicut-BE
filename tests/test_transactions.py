TX_BODY = {
    "amount": 10000,
    "type": "expense",
    "category": "식비",
    "merchant": "스타벅스",
    "description": "커피",
    "transaction_date": "2026-07-10",
    "transaction_time": "14:30",
}


def test_create_and_get(client, auth_headers):
    res = client.post("/transactions", json=TX_BODY, headers=auth_headers)
    assert res.status_code == 201
    tx_id = res.json()["id"]

    res = client.get(f"/transactions/{tx_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["amount"] == 10000
    assert data["category"] == "식비"
    assert "impulse_score" in data
    assert 0 <= data["impulse_score"] <= 100


def test_invalid_category(client, auth_headers):
    res = client.post("/transactions", json={**TX_BODY, "category": "없는카테고리"}, headers=auth_headers)
    assert res.status_code == 422


def test_invalid_type(client, auth_headers):
    res = client.post("/transactions", json={**TX_BODY, "type": "transfer"}, headers=auth_headers)
    assert res.status_code == 422


def test_list_with_filters(client, auth_headers):
    client.post("/transactions", json=TX_BODY, headers=auth_headers)
    client.post(
        "/transactions",
        json={**TX_BODY, "category": "교통", "transaction_date": "2026-06-01"},
        headers=auth_headers,
    )

    res = client.get("/transactions?year=2026&month=7", headers=auth_headers)
    assert len(res.json()) == 1
    res = client.get("/transactions?category=교통", headers=auth_headers)
    assert len(res.json()) == 1
    res = client.get("/transactions", headers=auth_headers)
    assert len(res.json()) == 2


def test_update_and_delete(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]

    res = client.put(f"/transactions/{tx_id}", json={**TX_BODY, "amount": 99000}, headers=auth_headers)
    assert res.status_code == 200
    assert client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["amount"] == 99000

    assert client.delete(f"/transactions/{tx_id}", headers=auth_headers).status_code == 200
    assert client.get(f"/transactions/{tx_id}", headers=auth_headers).status_code == 404


def test_emotion_tagging(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]

    emotions = client.get("/emotions", headers=auth_headers).json()
    assert len(emotions) == 6

    stress_id = next(e["id"] for e in emotions if e["name"] == "스트레스")
    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [stress_id]}, headers=auth_headers)
    assert res.status_code == 200

    tags = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["emotion_tags"]
    assert tags[0]["name"] == "스트레스"


def test_emotion_tagging_invalid_id(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [999]}, headers=auth_headers)
    assert res.status_code == 404


# 신한/삼성/현대/KB국민/NH농협은 kakao/credit-card-sms-parser의 실제 승인 문자
# 픽스처를 기준으로 검증한다 (현대카드는 원본에 날짜가 빠져 있어 보강함).
# 카카오뱅크는 공개된 실제 샘플이 없어 동일 구조로 추정한 포맷이다.
CARD_MESSAGE_CASES = [
    (
        "신한카드 승인되었습니다. [혜화역 카페] 5,500원 2026-08-22 14:32",
        {"amount": 5500, "merchant": "혜화역 카페", "transaction_date": "2026-08-22",
         "transaction_time": "14:32", "card_company": "신한카드"},
    ),
    (
        "[Web발신]\n신한카드승인 강*혜(9*0*) 04/27 21:31 (일시불)39,500원 (주)페어몬트 누적688,800원",
        {"amount": 39500, "merchant": "페어몬트", "card_company": "신한카드"},
    ),
    (
        "[Web발신]\n삼성가족카드승인9785\n03/24 18:45\n10,000원\n일시불\n소문난우동",
        {"amount": 10000, "merchant": "소문난우동", "card_company": "삼성카드"},
    ),
    (
        "[Web발신]\n[현대카드]-승인\n김재*님\n1,500원(일시불)\n04/22 19:56\n마노핀익스프레스신림\n누적:354,220원",
        {"amount": 1500, "merchant": "마노핀익스프레스신림", "card_company": "현대카드"},
    ),
    (
        "[Web발신]\nKB국민카드 2*5*\n정*욱님\n03/25 09:30\n2,200원\n미니스톱판교점\n누적 97,440원",
        {"amount": 2200, "merchant": "미니스톱판교점", "card_company": "KB국민카드"},
    ),
    (
        "[Web발신]\n농협BC(4*8*)오*름님.\n04/14 11:51.\n일시불81,400원.\n누적금액679,780원.\n버거킹 판교유스페",
        {"amount": 81400, "merchant": "버거킹 판교유스페", "card_company": "NH농협카드"},
    ),
    (
        "[Web발신]\n카카오뱅크 승인\n5,500원 일시불\n08/22 14:32\n혜화역 카페",
        {"amount": 5500, "merchant": "혜화역 카페", "card_company": "카카오뱅크"},
    ),
]


def test_parse_card_message(client, auth_headers):
    for message_text, expected in CARD_MESSAGE_CASES:
        res = client.post("/transactions/parse", json={"message_text": message_text}, headers=auth_headers)
        assert res.status_code == 200, res.text
        data = res.json()
        for key, value in expected.items():
            assert data[key] == value, f"{key} mismatch for: {message_text!r}"


def test_parse_card_message_unrecognized(client, auth_headers):
    res = client.post(
        "/transactions/parse", json={"message_text": "택배가 도착했습니다."}, headers=auth_headers
    )
    assert res.status_code == 422


def test_parse_card_message_requires_auth(client):
    res = client.post("/transactions/parse", json={"message_text": "신한카드 5,500원 2026-08-22 14:32"})
    assert res.status_code == 401
