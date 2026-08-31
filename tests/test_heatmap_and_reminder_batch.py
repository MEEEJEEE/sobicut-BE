import datetime as dt

from app.models import Notification
from app.services import heatmap_batch, no_transaction_batch
from app.services import web_push as web_push_service
from app.services.common import DAY_NAMES
from tests.conftest import TestingSessionLocal

HEATMAP_SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/heatmap-test",
    "keys": {"p256dh": "k", "auth": "a"},
    "notification_type": "히트맵알림",
}
REMINDER_SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/reminder-test",
    "keys": {"p256dh": "k", "auth": "a"},
    "notification_type": "가계부기록도우미",
}


class _FrozenDateTime(dt.datetime):
    _frozen: dt.datetime = dt.datetime.now()

    @classmethod
    def now(cls, tz=None):
        return cls._frozen


class _FrozenDate(dt.date):
    _frozen: dt.date = dt.date.today()

    @classmethod
    def today(cls):
        return cls._frozen


def _freeze_now(monkeypatch, when: dt.datetime):
    """Notification.created_at은 실제 시스템 시계를 쓰므로(모듈 monkeypatch로 못 바꿈),
    when은 항상 date.today()와 같은 날짜를 써야 멱등성 체크(created_at 날짜 비교)가 맞물린다.
    """
    _FrozenDateTime._frozen = when
    monkeypatch.setattr(heatmap_batch, "datetime", _FrozenDateTime)


def _freeze_today(monkeypatch, when: dt.date):
    _FrozenDate._frozen = when
    monkeypatch.setattr(no_transaction_batch, "date", _FrozenDate)


def test_heatmap_alert_sent_when_now_matches_peak(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=HEATMAP_SUBSCRIBE_BODY, headers=auth_headers)

    today = dt.date.today()
    frozen = dt.datetime.combine(today, dt.time(7, 0))  # 아침(06~11) 시간대, 오늘 날짜

    # 이 (요일, 아침) 조합이 이번 달 최댓값이 되도록 큰 금액 하나 등록
    client.post(
        "/transactions",
        json={
            "amount": 500000, "type": "expense", "category": "쇼핑/패션", "merchant": "빅소비",
            "transaction_date": today.isoformat(), "transaction_time": "07:30",
        },
        headers=auth_headers,
    )

    _freeze_now(monkeypatch, frozen)
    db = TestingSessionLocal()
    try:
        sent = heatmap_batch.process_heatmap_alerts(db)
        assert sent == 1
        notif = db.query(Notification).order_by(Notification.id.desc()).first()
        assert notif.type in {"heatmap_day", "heatmap_time"}
    finally:
        db.close()

    assert len(calls) == 1

    # 멱등성: 같은 날 다시 돌려도 중복 발송 안 됨
    db = TestingSessionLocal()
    try:
        second = heatmap_batch.process_heatmap_alerts(db)
    finally:
        db.close()
    assert second == 0
    assert len(calls) == 1


def test_heatmap_alert_not_sent_when_no_match(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=HEATMAP_SUBSCRIBE_BODY, headers=auth_headers)

    # 거래 자체가 없으면 peak이 없어 알림도 없어야 한다
    today = dt.date.today()
    frozen = dt.datetime.combine(today, dt.time(7, 0))
    _freeze_now(monkeypatch, frozen)
    db = TestingSessionLocal()
    try:
        sent = heatmap_batch.process_heatmap_alerts(db)
    finally:
        db.close()
    assert sent == 0
    assert calls == []


def test_no_transaction_reminder_sent_when_no_tx_today(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=REMINDER_SUBSCRIBE_BODY, headers=auth_headers)

    today = dt.date.today()
    _freeze_today(monkeypatch, today)

    db = TestingSessionLocal()
    try:
        sent = no_transaction_batch.process_no_transaction_reminders(db)
        assert sent == 1
        second = no_transaction_batch.process_no_transaction_reminders(db)
        assert second == 0  # 멱등성
    finally:
        db.close()

    assert len(calls) == 1


def test_no_transaction_reminder_skipped_when_tx_exists(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=REMINDER_SUBSCRIBE_BODY, headers=auth_headers)

    today = dt.date.today()
    client.post(
        "/transactions",
        json={
            "amount": 5000, "type": "expense", "category": "식비", "merchant": "편의점",
            "transaction_date": today.isoformat(), "transaction_time": "12:00",
        },
        headers=auth_headers,
    )

    _freeze_today(monkeypatch, today)
    db = TestingSessionLocal()
    try:
        sent = no_transaction_batch.process_no_transaction_reminders(db)
    finally:
        db.close()

    assert sent == 0
    assert calls == []
