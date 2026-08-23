from pywebpush import WebPushException

from app.services import web_push as web_push_service

SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/fake-endpoint-id",
    "keys": {"p256dh": "fake-p256dh-key", "auth": "fake-auth-secret"},
    "notification_type": "소비컷알림",
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
        json={"endpoint": SUBSCRIBE_BODY["endpoint"], "notification_type": "소비컷알림"},
        headers=auth_headers,
    )
    assert res.status_code == 200

    # 존재하지 않는 구독 해제는 404
    res = client.post(
        "/notifications/unsubscribe",
        json={"endpoint": "https://never-subscribed.example.com", "notification_type": "소비컷알림"},
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
