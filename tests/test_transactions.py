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
