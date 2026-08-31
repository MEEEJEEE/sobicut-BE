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


def test_get_active_subscriptions(client, auth_headers):
    # 처음엔 구독 없음
    res = client.get("/notifications/subscriptions", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []

    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)
    client.post(
        "/notifications/subscribe",
        json={**SUBSCRIBE_BODY, "notification_type": "만족도조사알림"},
        headers=auth_headers,
    )

    res = client.get("/notifications/subscriptions", headers=auth_headers)
    assert set(res.json()) == {"충동지수예산초과알림", "만족도조사알림"}

    # 해제하면 목록에서 빠짐
    client.post(
        "/notifications/unsubscribe",
        json={"endpoint": SUBSCRIBE_BODY["endpoint"], "notification_type": "충동지수예산초과알림"},
        headers=auth_headers,
    )
    res = client.get("/notifications/subscriptions", headers=auth_headers)
    assert res.json() == ["만족도조사알림"]


def test_get_active_subscriptions_deduplicated_across_devices(client, auth_headers):
    """같은 종류를 여러 기기(endpoint)에서 구독해도 중복 없이 한 번만 나와야 한다."""
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)
    client.post(
        "/notifications/subscribe",
        json={**SUBSCRIBE_BODY, "endpoint": "https://fcm.googleapis.com/fcm/send/second-device"},
        headers=auth_headers,
    )

    res = client.get("/notifications/subscriptions", headers=auth_headers)
    assert res.json() == ["충동지수예산초과알림"]


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


def _setup_max_single_tx_impulse(client, auth_headers, tx_date="2026-08-25"):
    """단건 거래로 충동 지수를 약 75점(z=0.14+0.54+0.42=1.10)까지 끌어올리는 공통 셋업.

    이상시간대(새벽 03시, 0.14) + 금액부담(예산 대비 90% 이상, 0.54) +
    또래대비소비(또래 지출 0이라 표준편차 0 -> 바로 최댓값, 0.42) 조합.
    같은 그룹(자취/30-60) 또래 2명을 지출 없이 만들어야 또래대비소비가 최댓값이 된다.
    """
    for i in range(2):
        client.post("/auth/signup", json={
            "email": f"peer_impulse_{tx_date}_{i}@test.com", "password": "abcd1234", "nickname": f"peer{i}",
            "residence_type": "자취", "income_level": "30-60",
        })

    client.put(
        "/budget",
        json={
            "monthly_budget": 100000, "weekly_budget": 25000,
            "weekly_budgets": {"week_1": 25000, "week_2": 25000, "week_3": 25000, "week_4": 25000},
        },
        headers=auth_headers,
    )
    return client.post(
        "/transactions",
        json={
            "amount": 90000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
            "transaction_date": tx_date, "transaction_time": "03:00",
        },
        headers=auth_headers,
    )


def test_impulse_monthly_trend_alert_fires_at_75(client, auth_headers, monkeypatch):
    """건별 impulse_warning은 폐지됐고, 이번 달 평균 충동 지수가 75를 넘을 때만 1회 알린다.
    월간 트렌드 알림이라 특정 거래에 대한 게 아니므로 transaction_id는 없어야 한다.
    """
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    res = _setup_max_single_tx_impulse(client, auth_headers)
    assert res.status_code == 201

    payloads = [json.loads(c["data"]) for c in calls]
    trend_payload = next(p for p in payloads if p["type"] == "impulse_monthly_trend")
    assert "transaction_id" not in trend_payload

    notifications = client.get("/notifications", headers=auth_headers).json()
    trend_notifs = [n for n in notifications if n["type"] == "impulse_monthly_trend"]
    assert trend_notifs and trend_notifs[0]["transaction_id"] is None
    assert "75" in trend_notifs[0]["title"]


def test_impulse_monthly_trend_alert_not_repeated_same_tier(client, auth_headers, monkeypatch):
    """같은 달에 75 단계를 이미 알렸으면, 계속 75 이상이어도 다시 안 뜬다."""
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    _setup_max_single_tx_impulse(client, auth_headers)
    first_count = len([json.loads(c["data"]) for c in calls if json.loads(c["data"])["type"] == "impulse_monthly_trend"])
    assert first_count == 1

    # 같은 수준의 거래를 하나 더 등록해도 이미 75는 알렸으니 재발송 안 됨
    client.post(
        "/transactions",
        json={
            "amount": 90000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰2",
            "transaction_date": "2026-08-25", "transaction_time": "03:30",
        },
        headers=auth_headers,
    )
    second_count = len([json.loads(c["data"]) for c in calls if json.loads(c["data"])["type"] == "impulse_monthly_trend"])
    assert second_count == 1  # 늘지 않음


def test_impulse_monthly_trend_alert_escalates_to_higher_tier(client, auth_headers, monkeypatch):
    """75 알림을 받은 뒤 더 높은 90 단계를 넘으면 새로 알림이 가야 한다."""
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    res = _setup_max_single_tx_impulse(client, auth_headers)
    tx_id = res.json()["id"]

    # 감정 태그(즉흥성+스트레스, 가중치 0.72+0.33)를 추가로 붙여서 90 이상까지 끌어올린다
    emotions = client.get("/emotions", headers=auth_headers).json()
    ids = [e["id"] for e in emotions if e["name"] in ("즉흥성", "스트레스")]
    assert len(ids) == 2
    client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": ids}, headers=auth_headers)

    tiers_seen = [json.loads(c["data"])["title"] for c in calls if json.loads(c["data"])["type"] == "impulse_monthly_trend"]
    assert any("75" in t for t in tiers_seen)
    assert any("90" in t for t in tiers_seen)


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
