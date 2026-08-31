import datetime as dt

from app.services import level as level_service
from app.services import level_batch
from tests.conftest import TestingSessionLocal


class _FrozenDate(dt.date):
    _frozen = dt.date(2026, 9, 1)

    @classmethod
    def today(cls):
        return cls._frozen


def _freeze(monkeypatch, frozen_date: dt.date):
    _FrozenDate._frozen = frozen_date
    monkeypatch.setattr(level_batch, "date", _FrozenDate)


def test_neutral_transaction_no_bonus_at_creation(client, auth_headers):
    """새 공식(bias=0)에서는 결제 전 변수만으로는 최저점이 50점이라, 생성 시점엔
    보너스가 안 나간다 (감정 태그가 없는 상태라 충분한숙고/장기적가치 같은 억제
    요인이 반영될 수 없음)."""
    level_before = client.get("/users/me/level", headers=auth_headers).json()

    res = client.post(
        "/transactions",
        json={
            "amount": 5000, "type": "expense", "category": "식비", "merchant": "편의점",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201

    level_after = client.get("/users/me/level", headers=auth_headers).json()
    gained = level_after["current_exp"] - level_before["current_exp"]
    assert gained == level_service.EXP_TRANSACTION


def test_low_impulse_bonus_granted_after_protective_tagging(client, auth_headers):
    """충분한숙고(-0.72)+장기적가치(-0.66) 태그를 붙이면 그제서야 점수가
    LOW_IMPULSE_THRESHOLD(30) 아래로 내려가서, 태깅 시점에 보너스가 지급된다."""
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 5000, "type": "expense", "category": "식비", "merchant": "편의점",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    emotions = client.get("/emotions", headers=auth_headers).json()
    ids = [e["id"] for e in emotions if e["name"] in ("충분한숙고", "장기적가치")]
    assert len(ids) == 2

    level_before = client.get("/users/me/level", headers=auth_headers).json()
    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": ids}, headers=auth_headers)
    assert res.status_code == 200
    level_after = client.get("/users/me/level", headers=auth_headers).json()

    gained = level_after["current_exp"] - level_before["current_exp"]
    assert gained == level_service.EXP_EMOTION_TAG + level_service.EXP_LOW_IMPULSE_BONUS


def test_low_impulse_bonus_not_granted_twice(client, auth_headers):
    """같은 거래를 재태깅해도 보너스는 한 번만 지급된다."""
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 5000, "type": "expense", "category": "식비", "merchant": "편의점",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    emotions = client.get("/emotions", headers=auth_headers).json()
    ids = [e["id"] for e in emotions if e["name"] in ("충분한숙고", "장기적가치")]

    client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": ids}, headers=auth_headers)
    level_before = client.get("/users/me/level", headers=auth_headers).json()

    # 재태깅(같은 태그 그대로 다시 보냄) -> 새 태그 추가가 없으니 EXP_EMOTION_TAG도 안 나가고,
    # 보너스도 이미 지급됐으니 또 안 나가야 함
    res = client.post(f"/transactions/{tx_id}/emotions", json={"emotion_tag_ids": ids}, headers=auth_headers)
    assert res.status_code == 200
    level_after = client.get("/users/me/level", headers=auth_headers).json()

    assert level_after["current_exp"] == level_before["current_exp"]


def test_high_impulse_transaction_no_bonus(client, auth_headers):
    client.put(
        "/budget",
        json={
            "monthly_budget": 100000, "weekly_budget": 25000,
            "weekly_budgets": {"week_1": 25000, "week_2": 25000, "week_3": 25000, "week_4": 25000},
        },
        headers=auth_headers,
    )
    level_before = client.get("/users/me/level", headers=auth_headers).json()

    res = client.post(
        "/transactions",
        json={
            "amount": 90000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
            "transaction_date": "2026-08-25", "transaction_time": "03:00",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201

    level_after = client.get("/users/me/level", headers=auth_headers).json()
    gained = level_after["current_exp"] - level_before["current_exp"]
    assert gained == level_service.EXP_TRANSACTION


def test_monthly_budget_bonus_granted_when_compliant(client, auth_headers, monkeypatch):
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000, "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )
    client.post(
        "/transactions",
        json={
            "amount": 100000, "type": "expense", "category": "식비", "merchant": "마트",
            "transaction_date": "2026-08-05", "transaction_time": "12:00",
        },
        headers=auth_headers,
    )

    level_before = client.get("/users/me/level", headers=auth_headers).json()

    _freeze(monkeypatch, dt.date(2026, 9, 1))
    db = TestingSessionLocal()
    try:
        granted = level_batch.process_monthly_budget_bonus(db)
    finally:
        db.close()

    assert granted == 1
    level_after = client.get("/users/me/level", headers=auth_headers).json()
    assert level_after["current_exp"] - level_before["current_exp"] == level_service.EXP_BUDGET_COMPLIANCE_BONUS


def test_monthly_budget_bonus_not_granted_when_exceeded(client, auth_headers, monkeypatch):
    client.put(
        "/budget",
        json={
            "monthly_budget": 50000, "weekly_budget": 12500,
            "weekly_budgets": {"week_1": 12500, "week_2": 12500, "week_3": 12500, "week_4": 12500},
        },
        headers=auth_headers,
    )
    client.post(
        "/transactions",
        json={
            "amount": 100000, "type": "expense", "category": "식비", "merchant": "마트",
            "transaction_date": "2026-08-05", "transaction_time": "12:00",
        },
        headers=auth_headers,
    )

    level_before = client.get("/users/me/level", headers=auth_headers).json()

    _freeze(monkeypatch, dt.date(2026, 9, 1))
    db = TestingSessionLocal()
    try:
        granted = level_batch.process_monthly_budget_bonus(db)
    finally:
        db.close()

    assert granted == 0
    level_after = client.get("/users/me/level", headers=auth_headers).json()
    assert level_after["current_exp"] == level_before["current_exp"]


def test_monthly_budget_bonus_idempotent(client, auth_headers, monkeypatch):
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000, "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )

    _freeze(monkeypatch, dt.date(2026, 9, 1))
    db = TestingSessionLocal()
    try:
        first = level_batch.process_monthly_budget_bonus(db)
        second = level_batch.process_monthly_budget_bonus(db)
    finally:
        db.close()

    assert first == 1
    assert second == 0


def test_monthly_budget_bonus_skips_when_not_first_of_month(client, auth_headers, monkeypatch):
    client.put(
        "/budget",
        json={
            "monthly_budget": 500000, "weekly_budget": 125000,
            "weekly_budgets": {"week_1": 125000, "week_2": 125000, "week_3": 125000, "week_4": 125000},
        },
        headers=auth_headers,
    )

    _freeze(monkeypatch, dt.date(2026, 8, 15))
    db = TestingSessionLocal()
    try:
        granted = level_batch.process_monthly_budget_bonus(db)
    finally:
        db.close()

    assert granted == 0
