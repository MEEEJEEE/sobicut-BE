from app.models import User
from app.routers import auth as auth_router
from tests.conftest import TestingSessionLocal


def _fake_kakao_user(kakao_id="12345", email="kakao@test.com", verified=True):
    def _fetch(access_token):
        return {"kakao_id": kakao_id, "email": email, "email_verified": verified}
    return _fetch


def test_kakao_signup_creates_new_user(client, monkeypatch):
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _fake_kakao_user())

    res = client.post("/auth/kakao", json={
        "access_token": "fake-token",
        "nickname": "카카오유저",
        "residence_type": "자취",
        "income_level": "30-60",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["is_new_user"] is True
    assert "access_token" in body

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.kakao_id == "12345").first()
        assert user is not None
        assert user.email == "kakao@test.com"
        assert user.password is None
        assert user.nickname == "카카오유저"
    finally:
        db.close()


def test_kakao_signup_missing_profile_fields_rejected(client, monkeypatch):
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _fake_kakao_user())

    res = client.post("/auth/kakao", json={"access_token": "fake-token"})
    assert res.status_code == 422


def test_kakao_login_existing_user_ignores_profile_fields(client, monkeypatch):
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _fake_kakao_user())
    client.post("/auth/kakao", json={
        "access_token": "fake-token",
        "nickname": "카카오유저",
        "residence_type": "자취",
        "income_level": "30-60",
    })

    res = client.post("/auth/kakao", json={"access_token": "fake-token"})
    assert res.status_code == 200
    assert res.json()["is_new_user"] is False

    db = TestingSessionLocal()
    try:
        assert db.query(User).filter(User.kakao_id == "12345").count() == 1
    finally:
        db.close()


def test_kakao_login_auto_links_existing_email_account(client, monkeypatch, auth_headers):
    # auth_headers 픽스처가 test@sookmyung.ac.kr로 이미 일반 가입을 해뒀음
    monkeypatch.setattr(
        auth_router, "fetch_kakao_user",
        _fake_kakao_user(kakao_id="99999", email="test@sookmyung.ac.kr", verified=True),
    )

    res = client.post("/auth/kakao", json={"access_token": "fake-token"})
    assert res.status_code == 200
    assert res.json()["is_new_user"] is False

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@sookmyung.ac.kr").first()
        assert user.kakao_id == "99999"
        assert user.password is not None  # 기존 비밀번호는 그대로 유지
    finally:
        db.close()


def test_kakao_signup_blocked_when_email_taken_and_not_verified(client, monkeypatch, auth_headers):
    monkeypatch.setattr(
        auth_router, "fetch_kakao_user",
        _fake_kakao_user(kakao_id="88888", email="test@sookmyung.ac.kr", verified=False),
    )

    res = client.post("/auth/kakao", json={
        "access_token": "fake-token",
        "nickname": "카카오유저",
        "residence_type": "자취",
        "income_level": "30-60",
    })
    assert res.status_code == 409


def test_kakao_invalid_token_returns_401(client, monkeypatch):
    def _raise(access_token):
        raise auth_router.KakaoAuthError("bad token")
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _raise)

    res = client.post("/auth/kakao", json={"access_token": "garbage"})
    assert res.status_code == 401


def test_password_login_rejected_for_kakao_only_account(client, monkeypatch):
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _fake_kakao_user())
    client.post("/auth/kakao", json={
        "access_token": "fake-token",
        "nickname": "카카오유저",
        "residence_type": "자취",
        "income_level": "30-60",
    })

    res = client.post("/auth/login", json={"email": "kakao@test.com", "password": "whatever123"})
    assert res.status_code == 401
    assert "카카오" in res.json()["detail"]


def test_withdraw_works_without_password_for_kakao_only_account(client, monkeypatch):
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _fake_kakao_user())
    login_res = client.post("/auth/kakao", json={
        "access_token": "fake-token",
        "nickname": "카카오유저",
        "residence_type": "자취",
        "income_level": "30-60",
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = client.patch("/auth/withdraw", json={"password": ""}, headers=headers)
    assert res.status_code == 200


def test_first_password_set_works_without_current_password_for_kakao_only_account(client, monkeypatch):
    monkeypatch.setattr(auth_router, "fetch_kakao_user", _fake_kakao_user())
    login_res = client.post("/auth/kakao", json={
        "access_token": "fake-token",
        "nickname": "카카오유저",
        "residence_type": "자취",
        "income_level": "30-60",
    })
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = client.patch(
        "/users/me/password",
        json={"current_password": "", "new_password": "newpass123"},
        headers=headers,
    )
    assert res.status_code == 200

    # 이제 이메일/비밀번호 로그인도 가능해짐
    res2 = client.post("/auth/login", json={"email": "kakao@test.com", "password": "newpass123"})
    assert res2.status_code == 200
