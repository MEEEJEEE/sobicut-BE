from tests.conftest import SIGNUP_BODY


def test_signup_success(client):
    res = client.post("/auth/signup", json=SIGNUP_BODY)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == 1
    assert data["email"] == SIGNUP_BODY["email"]


def test_signup_duplicate_email(client):
    client.post("/auth/signup", json=SIGNUP_BODY)
    res = client.post("/auth/signup", json=SIGNUP_BODY)
    assert res.status_code == 409


def test_signup_weak_password(client):
    body = {**SIGNUP_BODY, "password": "1234"}
    res = client.post("/auth/signup", json=body)
    assert res.status_code == 422


def test_login_success(client):
    client.post("/auth/signup", json=SIGNUP_BODY)
    res = client.post(
        "/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": SIGNUP_BODY["password"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/auth/signup", json=SIGNUP_BODY)
    res = client.post(
        "/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": "wrongpassword1"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "비밀번호가 올바르지 않습니다."


def test_login_user_not_found(client):
    res = client.post("/auth/login", json={"email": "notexist@test.com", "password": "any1234x"})
    assert res.status_code == 404
    assert res.json()["detail"] == "존재하지 않는 사용자입니다."


def test_login_missing_email(client):
    res = client.post("/auth/login", json={"password": "test1234"})
    assert res.status_code == 422


def test_login_invalid_email_format(client):
    res = client.post("/auth/login", json={"email": "not-an-email", "password": "test1234"})
    assert res.status_code == 422


def test_check_email(client):
    res = client.post("/auth/check-email", json={"email": SIGNUP_BODY["email"]})
    assert res.json()["is_available"] is True
    client.post("/auth/signup", json=SIGNUP_BODY)
    res = client.post("/auth/check-email", json={"email": SIGNUP_BODY["email"]})
    assert res.json()["is_available"] is False


def test_validate_password(client):
    assert client.post("/auth/validate-password", json={"password": "abcd1234"}).json()["is_valid"] is True
    assert client.post("/auth/validate-password", json={"password": "short1"}).json()["is_valid"] is False
    assert client.post("/auth/validate-password", json={"password": "onlyletters"}).json()["is_valid"] is False


def test_logout_blocks_token(client, auth_headers):
    assert client.get("/users/me", headers=auth_headers).status_code == 200
    res = client.get("/auth/logout", headers=auth_headers)
    assert res.status_code == 200
    # 로그아웃된 토큰으로 접근 불가
    assert client.get("/users/me", headers=auth_headers).status_code == 401


def test_withdraw(client, auth_headers):
    res = client.request("PATCH", "/auth/withdraw", json={"password": "test1234"}, headers=auth_headers)
    assert res.status_code == 200
    # 탈퇴 후 로그인 불가
    res = client.post(
        "/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": SIGNUP_BODY["password"]},
    )
    assert res.status_code == 404


def test_protected_route_requires_token(client):
    assert client.get("/transactions").status_code == 401
