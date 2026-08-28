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


def test_low_impulse_transaction_grants_bonus_exp(client, auth_headers):
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
    assert gained == level_service.EXP_TRANSACTION + level_service.EXP_LOW_IMPULSE_BONUS


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
