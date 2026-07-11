def test_my_page(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    assert me["nickname"] == "미지"
    assert me["residence_type"] == "자취"

    level = client.get("/users/me/level", headers=auth_headers).json()
    assert level["level"] == 1
    assert level["level_name"] == "슬라임"


def test_update_profile_fields(client, auth_headers):
    assert client.patch("/users/me/nickname", json={"nickname": "새닉네임"}, headers=auth_headers).status_code == 200
    assert client.patch("/users/me/residence-type", json={"residence_type": "기숙사"}, headers=auth_headers).status_code == 200
    assert client.patch("/users/me/income-level", json={"income_level": "60-100"}, headers=auth_headers).status_code == 200

    settings = client.get("/users/me/settings", headers=auth_headers).json()
    assert settings["nickname"] == "새닉네임"
    assert settings["residence_type"] == "기숙사"

    # 잘못된 값 거부
    assert client.patch("/users/me/residence-type", json={"residence_type": "옥탑방"}, headers=auth_headers).status_code == 422


def test_password_change(client, auth_headers):
    res = client.patch(
        "/users/me/password",
        json={"current_password": "wrong1234", "new_password": "newpass123"},
        headers=auth_headers,
    )
    assert res.status_code == 401

    res = client.patch(
        "/users/me/password",
        json={"current_password": "test1234", "new_password": "newpass123"},
        headers=auth_headers,
    )
    assert res.status_code == 200


def _setup_spending(client, auth_headers):
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000,
            "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )
    emotions = client.get("/emotions", headers=auth_headers).json()
    stress_id = next(e["id"] for e in emotions if e["name"] == "스트레스")

    tx_id = client.post(
        "/transactions",
        json={
            "amount": 150000,
            "type": "expense",
            "category": "쇼핑/패션",
            "merchant": "쿠팡",
            "description": None,
            "transaction_date": "2026-07-05",
            "transaction_time": "02:30",
        },
        headers=auth_headers,
    ).json()["id"]
    client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": [stress_id]}, headers=auth_headers)
    return tx_id


def test_reports(client, auth_headers):
    _setup_spending(client, auth_headers)

    scores = client.get("/reports/scores", headers=auth_headers).json()
    assert 0 <= scores["impulse_score"] <= 100
    assert scores["wallet_temperature"]["my_temp"] == 30  # 150000/500000
    assert scores["bpti"]["type"] == "FIRE"  # 주력 태그: 스트레스

    impulse = client.get("/reports/impulse?year=2026&month=7", headers=auth_headers).json()
    assert impulse["threshold"] == 75
    assert impulse["breakdown"]["time_abnormal"] == 1.0  # 새벽 2:30 소비
    assert len(impulse["top_impulse_transactions"]) == 1

    category = client.get("/reports/category?year=2026&month=7", headers=auth_headers).json()
    assert category["total_spent"] == 150000
    shopping = next(c for c in category["categories"] if c["category"] == "쇼핑/패션")
    assert shopping["ratio"] == 100.0

    heatmap = client.get("/reports/heatmap?year=2026&month=7", headers=auth_headers).json()
    assert heatmap["peak"]["time_slot"] == "새벽"
    assert heatmap["peak"]["day"] == "일"  # 2026-07-05는 일요일

    status = client.get("/reports/budget-status?year=2026&month=7", headers=auth_headers).json()
    assert status["monthly"]["spent"] == 150000
    assert status["monthly"]["usage_rate"] == 30.0
    assert status["weekly_breakdown"][0]["spent"] == 150000  # 5일 → 1주차

    forecast = client.get("/reports/monthly-forecast?year=2026&month=7", headers=auth_headers).json()
    assert forecast["current_spent"] == 150000
    assert forecast["predicted_total"] >= 150000

    monthly_temp = client.get("/reports/wallet-temperature/monthly?year=2026&month=7", headers=auth_headers).json()
    assert monthly_temp["weekly_temps"][0]["temp"] == 120  # 150000/125000


def test_impulse_warning_notification(client, auth_headers):
    _setup_spending(client, auth_headers)
    notifications = client.get("/notifications", headers=auth_headers).json()
    types = {n["type"] for n in notifications}
    assert "budget_weekly" in types  # 1주차 예산 125000 < 150000

    # 읽음 처리
    if notifications:
        nid = notifications[0]["id"]
        assert client.put(f"/notifications/{nid}", headers=auth_headers).status_code == 200
        assert client.put("/notifications/read-all", headers=auth_headers).status_code == 200
        all_read = client.get("/notifications", headers=auth_headers).json()
        assert all(n["is_read"] for n in all_read)
