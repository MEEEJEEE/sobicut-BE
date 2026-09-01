import datetime as dt

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

# 요일컷과 시간대컷이 서로 다른 (요일, 시간대)에서 각각 독립적으로 최댓값이 되도록
# 짠 같은 달 내 4일치 데이터. 실제 달력 요일이 뭔지는 중요하지 않고, 서로 다른 날짜라
# 자동으로 서로 다른 요일이 되는 것만 이용한다.
# DAY_DOMINANT_DATE는 반드시 실제 date.today()와 같아야 한다: Notification.created_at은
# 실제 시스템 시계로 찍히므로, 요일컷 멱등성 테스트에서 frozen "오늘"과 어긋나면
# _already_sent_today의 날짜 비교가 틀어져 버린다 (아래 _freeze_now/_freeze_heatmap_today 참고).
_TODAY = dt.date.today()
DAY_DOMINANT_DATE = _TODAY
_offsets = (1, 2, 3) if _TODAY.day <= 25 else (-1, -2, -3)
SLOT_DOMINANT_DATES = [_TODAY + dt.timedelta(days=i) for i in _offsets]  # 셋 다 "밤" 시간대에 지출, 같은 달 안에서 고름


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


def _freeze_heatmap_today(monkeypatch, when: dt.date):
    _FrozenDate._frozen = when
    monkeypatch.setattr(heatmap_batch, "date", _FrozenDate)


def _freeze_reminder_today(monkeypatch, when: dt.date):
    _FrozenDate._frozen = when
    monkeypatch.setattr(no_transaction_batch, "date", _FrozenDate)


def _setup_decoupled_heatmap_data(client, auth_headers):
    """요일컷(DAY_DOMINANT_DATE의 요일)과 시간대컷("밤")이 서로 다른 지점에서
    최댓값이 되도록 거래를 만든다. 리턴값: (peak_day_name, "밤")."""
    client.post(
        "/transactions",
        json={
            "amount": 1500, "type": "expense", "category": "식비", "merchant": "아침식사",
            "transaction_date": DAY_DOMINANT_DATE.isoformat(), "transaction_time": "07:00",
        },
        headers=auth_headers,
    )
    client.post(
        "/transactions",
        json={
            "amount": 1500, "type": "expense", "category": "식비", "merchant": "점심식사",
            "transaction_date": DAY_DOMINANT_DATE.isoformat(), "transaction_time": "12:00",
        },
        headers=auth_headers,
    )
    for d in SLOT_DOMINANT_DATES:
        client.post(
            "/transactions",
            json={
                "amount": 1000, "type": "expense", "category": "문화/여가", "merchant": "밤소비",
                "transaction_date": d.isoformat(), "transaction_time": "20:00",
            },
            headers=auth_headers,
        )
    return DAY_NAMES[DAY_DOMINANT_DATE.weekday()], "밤"


def test_heatmap_day_and_time_alerts_are_independent(client, auth_headers, monkeypatch):
    """요일컷이 뜨는 날에는 시간대컷이 안 뜨고, 시간대컷이 뜨는 시간에는 요일컷이 안 떠야 한다
    (같은 셀 하나로 양자택일하던 예전 방식이 아니라 완전히 독립된 두 지표라는 것 검증)."""
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=HEATMAP_SUBSCRIBE_BODY, headers=auth_headers)

    peak_day_name, peak_slot = _setup_decoupled_heatmap_data(client, auth_headers)

    db = TestingSessionLocal()
    try:
        # 요일컷 최다일에, 그 시간대컷과 무관한 아침 시간 -> 요일컷만 발동
        _freeze_heatmap_today(monkeypatch, DAY_DOMINANT_DATE)
        day_sent = heatmap_batch.process_heatmap_day_alerts(db)
        _freeze_now(monkeypatch, dt.datetime.combine(DAY_DOMINANT_DATE, dt.time(7, 0)))
        time_sent_on_day_peak = heatmap_batch.process_heatmap_time_alerts(db)
    finally:
        db.close()

    assert day_sent == 1
    assert time_sent_on_day_peak == 0  # 아침은 피크 시간대(밤)가 아니므로 안 뜸

    calls.clear()
    db = TestingSessionLocal()
    try:
        # 시간대컷 최다 시간(밤)이지만 요일컷 최다일이 아닌 다른 날 -> 시간대컷만 발동
        other_day = SLOT_DOMINANT_DATES[0]
        _freeze_now(monkeypatch, dt.datetime.combine(other_day, dt.time(20, 30)))
        time_sent = heatmap_batch.process_heatmap_time_alerts(db)
        _freeze_heatmap_today(monkeypatch, other_day)
        day_sent_on_time_peak = heatmap_batch.process_heatmap_day_alerts(db)
    finally:
        db.close()

    assert time_sent == 1
    assert day_sent_on_time_peak == 0  # other_day는 요일컷 최다일(DAY_DOMINANT_DATE)이 아니므로 안 뜸

    notifications = client.get("/notifications", headers=auth_headers).json()
    day_notifs = [n for n in notifications if n["type"] == "heatmap_day"]
    time_notifs = [n for n in notifications if n["type"] == "heatmap_time"]
    assert day_notifs and day_notifs[0]["title"] == f"{peak_day_name}요일에 소비가 가장 많아요"
    assert time_notifs and "야망" in time_notifs[0]["title"]  # 밤 = "야간 야망 컷"


def test_heatmap_day_alert_idempotent(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=HEATMAP_SUBSCRIBE_BODY, headers=auth_headers)
    _setup_decoupled_heatmap_data(client, auth_headers)

    _freeze_heatmap_today(monkeypatch, DAY_DOMINANT_DATE)
    db = TestingSessionLocal()
    try:
        first = heatmap_batch.process_heatmap_day_alerts(db)
        second = heatmap_batch.process_heatmap_day_alerts(db)
    finally:
        db.close()

    assert first == 1
    assert second == 0


def test_heatmap_alerts_not_sent_without_data(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=HEATMAP_SUBSCRIBE_BODY, headers=auth_headers)

    today = dt.date.today()
    _freeze_heatmap_today(monkeypatch, today)
    _freeze_now(monkeypatch, dt.datetime.combine(today, dt.time(7, 0)))

    db = TestingSessionLocal()
    try:
        day_sent = heatmap_batch.process_heatmap_day_alerts(db)
        time_sent = heatmap_batch.process_heatmap_time_alerts(db)
    finally:
        db.close()

    assert day_sent == 0
    assert time_sent == 0
    assert calls == []


def test_no_transaction_reminder_sent_when_no_tx_today(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(web_push_service, "webpush", lambda **kwargs: calls.append(kwargs))
    client.post("/notifications/subscribe", json=REMINDER_SUBSCRIBE_BODY, headers=auth_headers)

    today = dt.date.today()
    _freeze_reminder_today(monkeypatch, today)

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

    _freeze_reminder_today(monkeypatch, today)
    db = TestingSessionLocal()
    try:
        sent = no_transaction_batch.process_no_transaction_reminders(db)
    finally:
        db.close()

    assert sent == 0
    assert calls == []
