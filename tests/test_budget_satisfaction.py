BUDGET_BODY = {
    "monthly_budget": 1000000,
    "weekly_budget": 250000,
    "weekly_budgets": {"week_1": 250000, "week_2": 250000, "week_3": 250000, "week_4": 250000},
}


def test_budget_default_and_update(client, auth_headers):
    res = client.get("/budget", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["monthly_budget"] == 0

    res = client.put("/budget", json=BUDGET_BODY, headers=auth_headers)
    assert res.status_code == 200
    data = client.get("/budget", headers=auth_headers).json()
    assert data["monthly_budget"] == 1000000
    assert data["weekly_budgets"]["week_2"] == 250000


def _create_high_price_tx(client, auth_headers, tx_date="2026-06-01"):
    return client.post(
        "/transactions",
        json={
            "amount": 89000,
            "type": "expense",
            "category": "쇼핑/패션",
            "merchant": "무신사",
            "description": None,
            "transaction_date": tx_date,
            "transaction_time": "23:30",
        },
        headers=auth_headers,
    ).json()["id"]


def test_satisfaction_flow(client, auth_headers):
    tx_id = _create_high_price_tx(client, auth_headers)

    # 1일/7일/30일 모두 경과 → pending 3건
    pending = client.get("/satisfactions/pending", headers=auth_headers).json()
    assert {p["day_type"] for p in pending} == {"1일", "7일", "30일"}

    res = client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "7일", "score": 2}, headers=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["transaction_id"] == tx_id
    assert data["day_type"] == "7일"

    # 중복 입력 차단
    res = client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "7일", "score": 3}, headers=auth_headers)
    assert res.status_code == 409

    # 입력 후 pending에서 제외
    pending = client.get("/satisfactions/pending", headers=auth_headers).json()
    assert {p["day_type"] for p in pending} == {"1일", "30일"}


def test_satisfaction_invalid_score(client, auth_headers):
    tx_id = _create_high_price_tx(client, auth_headers)
    res = client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "7일", "score": 6}, headers=auth_headers)
    assert res.status_code == 422


def test_satisfaction_invalid_day_type(client, auth_headers):
    tx_id = _create_high_price_tx(client, auth_headers)
    res = client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "3일", "score": 3}, headers=auth_headers)
    assert res.status_code == 422


def test_transaction_satisfactions_comparison(client, auth_headers):
    """결과 페이지용: 같은 거래의 1일/7일/30일 만족도를 day_type과 함께 비교 조회"""
    tx_id = _create_high_price_tx(client, auth_headers)

    client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "7일", "score": 5}, headers=auth_headers)
    client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "30일", "score": 3}, headers=auth_headers)

    res = client.get(f"/transactions/{tx_id}/satisfactions", headers=auth_headers)
    assert res.status_code == 200
    records = res.json()
    assert [(r["day_type"], r["score"]) for r in records] == [("7일", 5), ("30일", 3)]
