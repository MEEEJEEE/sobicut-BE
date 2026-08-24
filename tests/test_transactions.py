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


def test_emotion_list_has_5_characteristics(client, auth_headers):
    emotions = client.get("/emotions", headers=auth_headers).json()
    assert {e["name"] for e in emotions} == {"스트레스", "즉흥성", "비교회피", "충분한숙고", "장기적가치"}


def test_emotion_classify_preview(client, auth_headers):
    res = client.post(
        "/emotions/classify", json={"description": "스트레스받아서 마음 달래려고 샀음"}, headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["top"]["bpti_type"] == "FIRE"
    assert data["top"]["name"] == "스트레스"
    assert len(data["candidates"]) == 5
    assert data["confidence_level"] in {"auto", "top3", "manual"}


def test_emotion_tagging_auto_classify(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]

    res = client.post(
        f"/transactions/{tx_id}/emotions",
        json={"description": "가격 비교하고 리뷰 읽고 며칠 고민함"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    tags = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["emotion_tags"]
    assert tags[0]["name"] == "충분한숙고"


def test_emotion_tagging_manual_override(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]

    emotions = client.get("/emotions", headers=auth_headers).json()
    vision_id = next(e["id"] for e in emotions if e["name"] == "장기적가치")

    res = client.post(
        f"/transactions/{tx_id}/emotions",
        json={"description": "애매한 설명이지만 내가 직접 골랐음", "emotion_tag_id": vision_id},
        headers=auth_headers,
    )
    assert res.status_code == 200

    tags = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["emotion_tags"]
    assert tags[0]["name"] == "장기적가치"


def test_emotion_tagging_reclassify_overwrites(client, auth_headers):
    """같은 거래에 다시 호출하면 기존 분류를 덮어써야 한다 (거래당 분류 1개)."""
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]

    client.post(
        f"/transactions/{tx_id}/emotions",
        json={"description": "스트레스받아서 샀음"},
        headers=auth_headers,
    )
    res = client.post(
        f"/transactions/{tx_id}/emotions",
        json={"description": "그냥 눈에 띄어서 샀음"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    tags = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["emotion_tags"]
    assert len(tags) == 1
    assert tags[0]["name"] == "즉흥성"


def test_emotion_tagging_invalid_id(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    res = client.post(
        f"/transactions/{tx_id}/emotions",
        json={"description": "설명", "emotion_tag_id": 999},
        headers=auth_headers,
    )
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
    # 프론트 QA에서 실제 문자로 확인한 회귀 케이스 (계좌/출금/고객명/시각이 노이즈로
    # 안 걸러지던 문제 + "씨유(CU)"의 "씨유"가 마스킹된 이름으로 오인되던 문제)
    (
        "[카카오뱅크] 08/23 08:25\n유*원님(7702)계좌\n출금 1,200원\n(씨유(CU) 자양한솔점)",
        {"amount": 1200, "merchant": "씨유(CU) 자양한솔점", "card_company": "카카오뱅크"},
    ),
    (
        "KB국민카드0093\n승인\n6,800 원(일시불)\n씨유(CU) 자양한솔점\n고객명 유*원님\n승인시각 08/22 23:14\n누적 100,000원",
        {"amount": 6800, "merchant": "씨유(CU) 자양한솔점", "card_company": "KB국민카드"},
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
