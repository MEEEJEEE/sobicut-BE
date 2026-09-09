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


def _emotion_ids(client, auth_headers, *names):
    emotions = client.get("/emotions", headers=auth_headers).json()
    by_name = {e["name"]: e["id"] for e in emotions}
    return [by_name[n] for n in names]


def test_emotion_tagging_multi_select(client, auth_headers):
    """계획 여부(즉흥성) + 소비 특성(스트레스, 비교회피) = 3개 다중 선택"""
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    ids = _emotion_ids(client, auth_headers, "즉흥성", "스트레스", "비교회피")

    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": ids}, headers=auth_headers)
    assert res.status_code == 200

    tags = {t["name"] for t in client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["emotion_tags"]}
    assert tags == {"즉흥성", "스트레스", "비교회피"}


def test_emotion_tagging_max_4(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    ids = _emotion_ids(client, auth_headers, "스트레스", "즉흥성", "비교회피", "충분한숙고", "장기적가치")

    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": ids}, headers=auth_headers)
    assert res.status_code == 422


def test_emotion_tagging_duplicate_rejected(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    stress_id = _emotion_ids(client, auth_headers, "스트레스")[0]

    res = client.post(
        f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [stress_id, stress_id]}, headers=auth_headers
    )
    assert res.status_code == 422


def test_emotion_tagging_resend_replaces_selection(client, auth_headers):
    """다시 호출하면 이전에 보냈던 태그 중 이번에 빠진 건 삭제되고, 새로 온 것만 반영된다 (교체 방식)."""
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    stress_id, fog_id, lazy_id = _emotion_ids(client, auth_headers, "스트레스", "즉흥성", "비교회피")

    client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [stress_id, fog_id]}, headers=auth_headers)
    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [fog_id, lazy_id]}, headers=auth_headers)
    assert res.status_code == 200

    tags = {t["name"] for t in client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["emotion_tags"]}
    assert tags == {"즉흥성", "비교회피"}  # 스트레스는 빠졌으니 삭제, 비교회피는 새로 추가


def test_emotion_tagging_invalid_id(client, auth_headers):
    tx_id = client.post("/transactions", json=TX_BODY, headers=auth_headers).json()["id"]
    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [9999]}, headers=auth_headers)
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
    # 우리카드: "카드" 없이 "우리(0479)승인" 형태 + 앞머리 장식기호("- ")와
    # "우리카드 이용안내" 헤더가 노이즈로 걸러져야 한다.
    (
        "- 우리카드 이용안내\n우리(0479)승인\n김*환님\n84,000원 일시불\n09/05 19:19\n양평해장국\n누적830,630원",
        {"amount": 84000, "merchant": "양평해장국", "card_company": "우리카드"},
    ),
    # KB국민카드 회귀 방지: [6] 노이즈 보강(이용안내/장식기호)이 이 케이스를
    # 망가뜨리지 않는지 확인한다. merchant 는 "구주 서면점".
    (
        "[Web발신]\nKB국민카드 1004승인\n전*안님\n77,900원 일시불\n08/12 23:17\n구주 서면점\n누적101,800원",
        {"amount": 77900, "merchant": "구주 서면점", "card_company": "KB국민카드"},
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


# 삼성카드 승인 문자는 "삼성0000승인 ..." 처럼 "카드" 글자 없이 접두 4자리가 붙는
# 형태가 있어, _COMPANY_PATTERNS 가 "삼성카드" 문자열을 필수로 요구하면 인식 실패한다.
_SAMSUNG_NO_SUFFIX_MSG = (
    "삼성0000승인 김*원\n88,789원 일시불\n09/08 23:00 SSG.COM\n누적88,789원"
)


def test_parse_samsung_card_without_card_suffix(client, auth_headers):
    res = client.post(
        "/transactions/parse",
        json={"message_text": _SAMSUNG_NO_SUFFIX_MSG},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["card_company"] == "삼성카드"
    assert data["amount"] == 88789
    assert data["transaction_date"] == "2026-09-08"
    assert data["transaction_time"] == "23:00"


# merchant 는 "SSG.COM". 마스킹 이름("김*원")은 '*' 포함 + 줄바꿈 앞이라 _MASK_NAME_RE
# 로 제거되고, 도메인의 "."은 영숫자 사이라 구두점 정리 단계에서 보존된다.
def test_parse_samsung_card_merchant(client, auth_headers):
    res = client.post(
        "/transactions/parse",
        json={"message_text": _SAMSUNG_NO_SUFFIX_MSG},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["merchant"] == "SSG.COM"


# 다른 카드사 문자의 가맹점명에 "삼성"이 들어가도 삼성카드로 오인식하면 안 된다.
# ("삼성" 뒤에 4자리 숫자가 오는 승인 접두사 형태일 때만 삼성카드로 본다.)
def test_samsung_in_merchant_not_misdetected(client, auth_headers):
    cases = [
        ("[Web발신]\n신한카드승인 김*원(6997) 09/08 12:00 12,000원 삼성전자서비스", "신한카드"),
        ("[Web발신]\nKB국민카드 1234\n03/25 09:30\n3,000원\n삼성역김밥천국\n누적 10,000원", "KB국민카드"),
    ]
    for message_text, expected_company in cases:
        res = client.post(
            "/transactions/parse", json={"message_text": message_text}, headers=auth_headers
        )
        assert res.status_code == 200, res.text
        assert res.json()["card_company"] == expected_company, message_text


# 상호명에 "우리"가 들어가도(문맥 조건 없이) 우리카드로 오인식하면 안 된다.
def test_woori_in_merchant_not_misdetected(client, auth_headers):
    message_text = (
        "[Web발신]\n신한카드승인 김*원(6997) 09/08 12:00 12,000원 우리동네정육점"
    )
    res = client.post(
        "/transactions/parse", json={"message_text": message_text}, headers=auth_headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["card_company"] == "신한카드"
