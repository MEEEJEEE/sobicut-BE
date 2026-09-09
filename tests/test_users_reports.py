def test_my_page(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    assert me["nickname"] == "미지"
    assert me["residence_type"] == "자취"

    level = client.get("/users/me/level", headers=auth_headers).json()
    assert level["level"] == 0
    assert level["level_name"] == "슬라임 커티"


def test_update_profile_fields(client, auth_headers):
    assert client.patch("/users/me/nickname", json={"nickname": "새닉네임"}, headers=auth_headers).status_code == 200
    assert client.patch("/users/me/residence-type", json={"residence_type": "기숙사"}, headers=auth_headers).status_code == 200
    assert client.patch("/users/me/income-level", json={"income_level": "60-100"}, headers=auth_headers).status_code == 200

    settings = client.get("/users/me/settings", headers=auth_headers).json()
    assert settings["nickname"] == "새닉네임"
    assert settings["residence_type"] == "기숙사"
    assert settings["is_kakao_account"] is False

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

    # /reports/scores는 year/month를 받지 않고 시스템 현재 날짜 기준으로 집계되므로,
    # 시스템 날짜와 무관하게 통과하도록 year=2026&month=7을 명시하는 개별 엔드포인트로 검증한다.
    scores = client.get("/reports/scores", headers=auth_headers).json()
    assert 0 <= scores["impulse_score"] <= 100

    wallet_temp = client.get("/reports/wallet-temperature?year=2026&month=7", headers=auth_headers).json()
    assert wallet_temp["my_temp"] == 30  # 150000/500000

    bpti = client.get("/reports/bpti?year=2026&month=7", headers=auth_headers).json()
    assert bpti["type"] == "FIRE"  # 주력 태그: 스트레스

    impulse = client.get("/reports/impulse?year=2026&month=7", headers=auth_headers).json()
    assert impulse["threshold"] == 67
    assert impulse["breakdown"]["time_abnormal"] == 1.0  # 새벽 2:30 소비
    assert len(impulse["top_impulse_transactions"]) == 1

    category = client.get("/reports/category?year=2026&month=7", headers=auth_headers).json()
    assert category["total_spent"] == 150000
    shopping = next(c for c in category["categories"] if c["category"] == "쇼핑/패션")
    assert shopping["ratio"] == 100.0

    heatmap = client.get("/reports/heatmap?year=2026&month=7", headers=auth_headers).json()
    assert heatmap["peak_time_slot"]["time_slot"] == "새벽"
    assert heatmap["peak_day"]["day"] == "일"  # 2026-07-05는 일요일

    status = client.get("/reports/budget-status?year=2026&month=7", headers=auth_headers).json()
    assert status["monthly"]["spent"] == 150000
    assert status["monthly"]["usage_rate"] == 30.0
    assert status["weekly_breakdown"][0]["spent"] == 150000  # 5일 → 1주차

    forecast = client.get("/reports/monthly-forecast?year=2026&month=7", headers=auth_headers).json()
    assert forecast["current_spent"] == 150000
    assert forecast["predicted_total"] >= 150000

    monthly_temp = client.get("/reports/wallet-temperature/monthly?year=2026&month=7", headers=auth_headers).json()
    assert monthly_temp["weekly_temps"][0]["temp"] == 120  # 150000/125000


def test_emotion_expense_ratio_is_independent_per_tag_unlike_breakdown(client, auth_headers):
    """emotion_breakdown(태그 부착 횟수 기준, 합계 100%)과 달리 emotion_expense_ratio는
    거래 하나에 태그가 여러 개 붙어도 태그별로 독립 집계되어 합계가 100%를 넘을 수 있다."""
    emotions = client.get("/emotions", headers=auth_headers).json()
    stress_id = next(e["id"] for e in emotions if e["name"] == "스트레스")
    impulsive_id = next(e["id"] for e in emotions if e["name"] == "즉흥성")

    tx1 = client.post(
        "/transactions",
        json={
            "amount": 50000, "type": "expense", "category": "쇼핑/패션", "merchant": "A",
            "transaction_date": "2026-07-05", "transaction_time": "14:00",
        },
        headers=auth_headers,
    ).json()["id"]
    client.post(f"/transactions/{tx1}/emotions", json={"emotion_tag_ids": [stress_id, impulsive_id]}, headers=auth_headers)

    tx2 = client.post(
        "/transactions",
        json={
            "amount": 30000, "type": "expense", "category": "식비", "merchant": "B",
            "transaction_date": "2026-07-06", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]
    client.post(f"/transactions/{tx2}/emotions", json={"emotion_tag_ids": [stress_id]}, headers=auth_headers)

    impulse = client.get("/reports/impulse?year=2026&month=7", headers=auth_headers).json()

    # emotion_breakdown: 태그 부착 횟수(스트레스 2회, 즉흥성 1회) 기준 분포, 합계 100%
    assert impulse["emotion_breakdown"]["스트레스"] == 0.67
    assert impulse["emotion_breakdown"]["즉흥성"] == 0.33
    assert round(sum(impulse["emotion_breakdown"].values()), 2) == 1.0

    # emotion_expense_ratio: 전체 지출 거래 2건 중 해당 태그가 붙은 거래 비율, 태그별 독립 집계
    assert impulse["emotion_expense_ratio"]["스트레스"] == 1.0  # 2건 다 스트레스 태그
    assert impulse["emotion_expense_ratio"]["즉흥성"] == 0.5  # 1건만 즉흥성 태그
    assert sum(impulse["emotion_expense_ratio"].values()) > 1.0  # 중복 집계라 100% 초과 가능


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
