import datetime as dt

from app.services import web_push as web_push_service


def _other_user_headers(client, email="other-demo@test.com"):
    client.post(
        "/auth/signup",
        json={
            "email": email, "password": "test1234", "nickname": "다른유저",
            "residence_type": "자취", "income_level": "30-60",
        },
    )
    res = client.post("/auth/login", json={"email": email, "password": "test1234"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_demo_trigger_requires_auth(client):
    for path in [
        "/demo/trigger/heatmap-day",
        "/demo/trigger/heatmap-time",
        "/demo/trigger/no-transaction-reminder",
        "/demo/trigger/satisfaction-reminder",
        "/demo/trigger/budget-bonus",
    ]:
        assert client.post(path).status_code == 401


def test_no_transaction_trigger_fires_and_force_repeats(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))

    res = client.post("/demo/trigger/no-transaction-reminder", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["sent"] == 1

    # 오늘 이미 보냈으므로 기본 호출은 멱등 — 다시 안 뜸
    res2 = client.post("/demo/trigger/no-transaction-reminder", headers=auth_headers)
    assert res2.json()["sent"] == 0

    # force=true면 리허설처럼 반복 시연 가능
    res3 = client.post("/demo/trigger/no-transaction-reminder?force=true", headers=auth_headers)
    assert res3.json()["sent"] == 1


def test_demo_trigger_scoped_to_caller_only(client, auth_headers):
    other_headers = _other_user_headers(client)

    res = client.post("/demo/trigger/no-transaction-reminder", headers=auth_headers)
    assert res.json()["sent"] == 1

    my_notifs = client.get("/notifications", headers=auth_headers).json()
    other_notifs = client.get("/notifications", headers=other_headers).json()
    assert any(n["type"] == "no_transaction_reminder" for n in my_notifs)
    assert not any(n["type"] == "no_transaction_reminder" for n in other_notifs)


def test_budget_bonus_trigger_works_with_force_on_any_day(client, auth_headers):
    today = dt.date.today()
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000,
            "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )

    if today.day == 1:
        res = client.post("/demo/trigger/budget-bonus", headers=auth_headers)
    else:
        res = client.post("/demo/trigger/budget-bonus?force=true", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json()["granted"], int)


def test_heatmap_trigger_endpoints_respond(client, auth_headers):
    res_day = client.post("/demo/trigger/heatmap-day", headers=auth_headers)
    res_time = client.post("/demo/trigger/heatmap-time", headers=auth_headers)
    assert res_day.status_code == 200
    assert res_time.status_code == 200
    assert res_day.json()["sent"] == 0  # 이번 달 소비 데이터가 없으니 피크도 없음
    assert res_time.json()["sent"] == 0


def test_satisfaction_trigger_responds(client, auth_headers):
    res = client.post("/demo/trigger/satisfaction-reminder", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["sent"] == 0  # 대상 거래 없음
