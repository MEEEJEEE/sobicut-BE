"""'설문조사 기반 충동 점수 로직 재설정' 문서(v2) 반영 검증.

핵심 확인 사항:
- bias=0, β1(이상시간대)/β2(금액부담)/β3(또래대비소비) 3개만 결제 전 점수에 반영
- β2가 주관적 부담(subjective_burden) 입력 여부에 따라 달라짐
- β3가 또래 평균/표준편차 기반 z-score로 계산됨
- β4(구매후후회)/γ6(지속적만족)은 실시간 점수(z)에 절대 포함되지 않음
  (post_purchase_breakdown으로만 노출)
- risk_level 3단계(낮음/주의/경고) 임계값(60/67)
"""
from app.services.impulse import (
    _amount_burden,
    _peer_comparison,
    behavior_breakdown,
    post_purchase_breakdown,
    risk_level,
)
from tests.conftest import TestingSessionLocal


def test_risk_level_tiers():
    assert risk_level(0) == "낮음"
    assert risk_level(59) == "낮음"
    assert risk_level(60) == "주의"
    assert risk_level(66) == "주의"
    assert risk_level(67) == "경고"
    assert risk_level(100) == "경고"


def test_amount_burden_no_budget_is_zero(client, auth_headers):
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 90000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        from app.models import Transaction
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        assert _amount_burden(db, tx) == 0.0  # 예산 미설정
    finally:
        db.close()


def test_amount_burden_uses_subjective_input_over_default(client, auth_headers):
    """subjective_burden을 명시하면 R(객관적 비율)이 아니라 그 값을 B로 써서 결과가 달라져야 한다."""
    client.put(
        "/budget",
        json={
            "monthly_budget": 100000, "weekly_budget": 25000,
            "weekly_budgets": {"week_1": 25000, "week_2": 25000, "week_3": 25000, "week_4": 25000},
        },
        headers=auth_headers,
    )
    # amount=3000 -> ratio=3% -> R=0.10. subjective_burden=5(최대) -> B=1.0
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 3000, "type": "expense", "category": "식비", "merchant": "편의점",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
            "subjective_burden": 5,
        },
        headers=auth_headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        from app.models import Transaction
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        # x2 = 0.6*0.10 + 0.4*1.0 = 0.46 (subjective_burden 미입력 시 0.6*0.10+0.4*0.10=0.10과 다름)
        assert abs(_amount_burden(db, tx) - 0.46) < 1e-9
    finally:
        db.close()


def test_peer_comparison_zscore_zero_variance(client, auth_headers):
    """또래 지출이 전부 0(표준편차 0)이고 내 지출이 있으면 x3=1.0으로 바로 처리된다."""
    for i in range(2):
        client.post("/auth/signup", json={
            "email": f"peer_zscore_{i}@test.com", "password": "abcd1234", "nickname": f"pz{i}",
            "residence_type": "자취", "income_level": "30-60",
        })

    tx_id = client.post(
        "/transactions",
        json={
            "amount": 50000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        from app.models import Transaction, User
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        user = db.query(User).filter(User.id == tx.user_id).first()
        assert _peer_comparison(db, user, 2026, 8) == 1.0
    finally:
        db.close()


def test_peer_comparison_insufficient_peers_is_zero(client, auth_headers):
    """또래가 2명 미만이면 표준편차를 낼 수 없어 0을 반환한다."""
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 50000, "type": "expense", "category": "쇼핑/패션", "merchant": "쇼핑몰",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        from app.models import Transaction, User
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        user = db.query(User).filter(User.id == tx.user_id).first()
        assert _peer_comparison(db, user, 2026, 8) == 0.0
    finally:
        db.close()


def test_behavior_breakdown_excludes_repeat_and_regret(client, auth_headers):
    """새 공식엔 반복소비(repeat_consumption)가 없고, 구매후후회(regret_score)는
    결제 전 breakdown이 아니라 post_purchase_breakdown에만 있어야 한다."""
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 5000, "type": "expense", "category": "식비", "merchant": "편의점",
            "transaction_date": "2026-08-25", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        from app.models import Transaction, User
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        user = db.query(User).filter(User.id == tx.user_id).first()

        breakdown = behavior_breakdown(db, tx, user)
        assert set(breakdown.keys()) == {"time_abnormal", "amount_burden", "peer_comparison"}

        post = post_purchase_breakdown(db, tx)
        assert set(post.keys()) == {"regret_score", "sustained_satisfaction"}
    finally:
        db.close()


def test_regret_and_sustained_satisfaction_do_not_affect_live_score(client, auth_headers):
    """만족도를 아무리 낮게/높게 입력해도 실시간 impulse_score(GET /transactions/{id})는
    변하면 안 된다 -- 이미 끝난 구매의 사전 위험 점수를 사후에 재계산하지 않기 위함."""
    tx_id = client.post(
        "/transactions",
        json={
            "amount": 89000, "type": "expense", "category": "쇼핑/패션", "merchant": "무신사",
            "transaction_date": "2026-06-01", "transaction_time": "12:00",
        },
        headers=auth_headers,
    ).json()["id"]

    before = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["impulse_score"]

    client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "1일", "score": 1}, headers=auth_headers)
    client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "7일", "score": 1}, headers=auth_headers)
    client.post("/satisfactions", json={"transaction_id": tx_id, "day_type": "30일", "score": 1}, headers=auth_headers)

    after = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["impulse_score"]
    assert before == after
