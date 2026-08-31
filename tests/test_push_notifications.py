import json

from pywebpush import WebPushException

from app.services import web_push as web_push_service

SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/fake-endpoint-id",
    "keys": {"p256dh": "fake-p256dh-key", "auth": "fake-auth-secret"},
    "notification_type": "충동지수예산초과알림",
}


def test_vapid_public_key_no_auth_required(client):
    res = client.get("/notifications/vapid-public-key")
    assert res.status_code == 200
    assert len(res.json()["public_key"]) > 0


def test_subscribe_invalid_type_rejected(client, auth_headers):
    res = client.post(
        "/notifications/subscribe",
        json={**SUBSCRIBE_BODY, "notification_type": "없는타입"},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_subscribe_unsubscribe_flow(client, auth_headers):
    res = client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)
    assert res.status_code == 200

    # 같은 endpoint+notification_type으로 재구독하면 기존 행을 갱신한다 (중복 생성 아님)
    res = client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)
    assert res.status_code == 200

    # 같은 endpoint라도 notification_type이 다르면 별도 구독으로 취급
    res = client.post(
        "/notifications/subscribe",
        json={**SUBSCRIBE_BODY, "notification_type": "만족도조사알림"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    res = client.post(
        "/notifications/unsubscribe",
        json={"endpoint": SUBSCRIBE_BODY["endpoint"], "notification_type": "충동지수예산초과알림"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    # 존재하지 않는 구독 해제는 404
    res = client.post(
        "/notifications/unsubscribe",
        json={"endpoint": "https://never-subscribed.example.com", "notification_type": "충동지수예산초과알림"},
        headers=auth_headers,
    )
    assert res.status_code == 404


def test_test_push_without_subscription(client, auth_headers):
    res = client.post("/notifications/test-push", headers=auth_headers)
    assert res.status_code == 404


def test_test_push_delivery_failure(client, auth_headers, monkeypatch):
    """푸시 서비스가 구독을 거부하는 경우(예: 만료/유효하지 않은 endpoint) 502를 반환해야 한다.

    실제 푸시 서비스로 네트워크 요청을 보내면 CI 환경에 따라 불안정해지므로 모킹한다.
    """
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    def _raise(**kwargs):
        raise WebPushException("Push failed: 410 Gone")

    monkeypatch.setattr(web_push_service, "webpush", _raise)

    res = client.post("/notifications/test-push", headers=auth_headers)
    assert res.status_code == 502


def test_test_push_success_when_delivery_succeeds(client, auth_headers, monkeypatch):
    """실제 브라우저 알림 수신은 이 테스트 환경에서 검증할 수 없어 pywebpush 호출을 모킹한다."""
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: None)

    res = client.post("/notifications/test-push", headers=auth_headers)
    assert res.status_code == 200


def test_budget_exceeded_transaction_triggers_push(client, auth_headers, monkeypatch):
    """예산 초과로 인앱 알림이 생성되는 시점에 실제 웹 푸시 발송까지 이어지는지 확인.

    check_after_transaction()이 Notification row만 만들고 push를 안 보내던 문제를
    notify_active_subscribers() 연결로 고친 회귀 테스트.
    """
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))

    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000,
            "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )

    res = client.post(
        "/transactions",
        json={
            "amount": 150000,
            "type": "expense",
            "category": "쇼핑/패션",
            "merchant": "쿠팡",
            "transaction_date": "2026-07-05",
            "transaction_time": "02:30",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201

    titles = {json.loads(c["data"])["title"] for c in calls}
    assert "주간 예산 초과" in titles

    payloads = [json.loads(c["data"]) for c in calls]
    budget_payload = next(p for p in payloads if p["title"] == "주간 예산 초과")
    assert budget_payload["type"] == "budget_weekly"
    assert "transaction_id" not in budget_payload  # 특정 거래 알림이 아니므로 없어야 함


def test_impulse_warning_push_includes_transaction_id(client, auth_headers, monkeypatch):
    """impulse_warning은 특정 거래에 대한 알림이므로 payload/응답에 transaction_id가 있어야 한다."""
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    client.put(
        "/budget",
        json={
            "monthly_budget": 100000, "weekly_budget": 25000,
            "weekly_budgets": {"week_1": 25000, "week_2": 25000, "week_3": 25000, "week_4": 25000},
        },
        headers=auth_headers,
    )
    # 같은 주 같은 카테고리 반복 소비(repeat_consumption)까지 겹쳐야 충동 점수가
    # 경고 임계치(75)를 넘는다 — 새벽 시간대 + 예산 대비 큰 금액만으로는 부족함.
    for _ in range(2):
        client.post(
            "/transactions",
            json={
                "amount": 90000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
                "transaction_date": "2026-08-25", "transaction_time": "03:00",
            },
            headers=auth_headers,
        )
    res = client.post(
        "/transactions",
        json={
            "amount": 90000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
            "transaction_date": "2026-08-25", "transaction_time": "03:00",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    tx_id = res.json()["id"]

    payloads = [json.loads(c["data"]) for c in calls]
    impulse_payload = next(p for p in payloads if p["type"] == "impulse_warning")
    assert impulse_payload["transaction_id"] == tx_id

    notifications = client.get("/notifications", headers=auth_headers).json()
    impulse_notifs = [n for n in notifications if n["type"] == "impulse_warning"]
    assert impulse_notifs and impulse_notifs[0]["transaction_id"] == tx_id


def test_transaction_without_subscription_does_not_error(client, auth_headers):
    """구독이 없는 사용자는 push 시도 없이 거래 생성이 그대로 성공해야 한다."""
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000,
            "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )
    res = client.post(
        "/transactions",
        json={
            "amount": 150000,
            "type": "expense",
            "category": "쇼핑/패션",
            "merchant": "쿠팡",
            "transaction_date": "2026-07-05",
            "transaction_time": "02:30",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
