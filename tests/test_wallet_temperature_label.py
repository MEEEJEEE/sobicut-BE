"""_wallet_summary()가 status가 아니라 label을 내려주는지 확인하는 회귀 테스트.

label과 status는 소비율 80% 미만 구간(매우안정/안정/보통)에서는 문자열이 같아서
차이가 안 드러난다. 80% 이상 구간(임계 vs 주의, 초과 vs 위험, 과열 vs 매우위험)에서
써야 실제로 검증된다.
"""


def _put_budget(client, auth_headers, monthly_budget):
    client.put(
        "/budget",
        json={
            "monthly_budget": monthly_budget,
            "weekly_budget": monthly_budget // 4,
            "weekly_budgets": {
                "week_1": monthly_budget // 4,
                "week_2": monthly_budget // 4,
                "week_3": monthly_budget // 4,
                "week_4": monthly_budget // 4,
            },
        },
        headers=auth_headers,
    )


def _spend(client, auth_headers, amount, tx_date="2026-07-05"):
    client.post(
        "/transactions",
        json={
            "amount": amount, "type": "expense", "category": "식비", "merchant": "마트",
            "transaction_date": tx_date, "transaction_time": "12:00",
        },
        headers=auth_headers,
    )


def test_wallet_level_uses_label_not_status_at_critical_range(client, auth_headers):
    """소비율 85% -> label="임계" (status는 "주의"라 다름)"""
    _put_budget(client, auth_headers, 100000)
    _spend(client, auth_headers, 85000)

    wallet = client.get("/reports/wallet-temperature?year=2026&month=7", headers=auth_headers).json()
    assert wallet["my_temp"] == 85
    assert wallet["level"] == "임계"
    assert wallet["level"] != "주의"

    monthly = client.get("/reports/wallet-temperature/monthly?year=2026&month=7", headers=auth_headers).json()
    assert monthly["level"] == "임계"


def test_wallet_level_uses_label_not_status_at_overheat_range(client, auth_headers):
    """소비율 130% -> label="과열" (status는 "매우 위험"이라 다름)"""
    _put_budget(client, auth_headers, 100000)
    _spend(client, auth_headers, 130000)

    wallet = client.get("/reports/wallet-temperature?year=2026&month=7", headers=auth_headers).json()
    assert wallet["my_temp"] == 130
    assert wallet["level"] == "과열"
    assert wallet["level"] != "매우 위험"
