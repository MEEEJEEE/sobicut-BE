import json
from datetime import date, timedelta

from app.models import Notification, SatisfactionNotificationLog
from app.services import web_push as web_push_service
from app.services.satisfaction_batch import process_satisfaction_reminders
from tests.conftest import TestingSessionLocal

SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/satisfaction-batch-test",
    "keys": {"p256dh": "fake-p256dh-key", "auth": "fake-auth-secret"},
    "notification_type": "만족도조사알림",
}


def _create_high_price_tx(client, auth_headers, tx_date: str):
    return client.post(
        "/transactions",
        json={
            "amount": 89000,
            "type": "expense",
            "category": "쇼핑/패션",
            "merchant": "무신사",
            "transaction_date": tx_date,
            "transaction_time": "23:30",
        },
        headers=auth_headers,
    ).json()["id"]


def test_batch_sends_notification_when_due_today(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    due_today_date = (date.today() - timedelta(days=7)).isoformat()
    tx_id = _create_high_price_tx(client, auth_headers, due_today_date)

    db = TestingSessionLocal()
    try:
        sent = process_satisfaction_reminders(db)
        assert sent == 1

        noti = db.query(Notification).filter(Notification.type == "satisfaction_request").first()
        assert noti is not None
        assert "7일" in noti.title
        assert noti.transaction_id == tx_id  # 클릭 시 어느 거래인지 알아야 결과 페이지로 이동 가능

        log = (
            db.query(SatisfactionNotificationLog)
            .filter(SatisfactionNotificationLog.transaction_id == tx_id, SatisfactionNotificationLog.day_type == "7일")
            .first()
        )
        assert log is not None
    finally:
        db.close()

    assert len(calls) == 1
    payload = json.loads(calls[0]["data"])
    assert payload["type"] == "satisfaction_request"
    assert payload["transaction_id"] == tx_id

    # API 응답(GET /notifications)에도 transaction_id가 노출돼야 프론트가 클릭 라우팅에 쓸 수 있다
    notifications = client.get("/notifications", headers=auth_headers).json()
    satisfaction_notifs = [n for n in notifications if n["type"] == "satisfaction_request"]
    assert satisfaction_notifs and satisfaction_notifs[0]["transaction_id"] == tx_id

    assert len(calls) == 1
    assert json.loads(calls[0]["data"])["title"] == noti.title


def test_batch_is_idempotent(client, auth_headers, monkeypatch):
    """같은 배치를 두 번 돌려도 중복 발송되지 않아야 한다."""
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=SUBSCRIBE_BODY, headers=auth_headers)

    due_today_date = (date.today() - timedelta(days=30)).isoformat()
    _create_high_price_tx(client, auth_headers, due_today_date)

    db = TestingSessionLocal()
    try:
        first = process_satisfaction_reminders(db)
        second = process_satisfaction_reminders(db)
    finally:
        db.close()

    assert first == 1
    assert second == 0
    assert len(calls) == 1


def test_batch_ignores_not_yet_due_transactions(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))

    # 아직 3일밖에 안 지난 거래 → 오늘 발송 대상 아님
    not_due_date = (date.today() - timedelta(days=3)).isoformat()
    _create_high_price_tx(client, auth_headers, not_due_date)

    db = TestingSessionLocal()
    try:
        sent = process_satisfaction_reminders(db)
    finally:
        db.close()

    assert sent == 0
    assert calls == []


def test_batch_skips_already_submitted(client, auth_headers, monkeypatch):
    """이미 만족도를 제출한 건은 배치 대상에서 빠져야 한다."""
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))

    due_today_date = (date.today() - timedelta(days=7)).isoformat()
    tx_id = _create_high_price_tx(client, auth_headers, due_today_date)
    res = client.post(
        "/satisfactions", json={"transaction_id": tx_id, "day_type": "7일", "score": 4}, headers=auth_headers
    )
    assert res.status_code == 201

    db = TestingSessionLocal()
    try:
        sent = process_satisfaction_reminders(db)
    finally:
        db.close()

    assert sent == 0
    assert calls == []
