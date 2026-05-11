import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ──────────────────────────────────────────
# 1. 정상 로그인
# ──────────────────────────────────────────
def test_login_success():
    response = client.post(
        "/auth/login",
        json={"email": "test@sookmyung.ac.kr", "password": "test1234"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


# ──────────────────────────────────────────
# 2. 비밀번호 틀림
# ──────────────────────────────────────────
def test_login_wrong_password():
    response = client.post(
        "/auth/login",
        json={"email": "test@sookmyung.ac.kr", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "비밀번호가 올바르지 않습니다."


# ──────────────────────────────────────────
# 3. 존재하지 않는 유저
# ──────────────────────────────────────────
def test_login_user_not_found():
    response = client.post(
        "/auth/login",
        json={"email": "notexist@test.com", "password": "any1234"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "존재하지 않는 사용자입니다."


# ──────────────────────────────────────────
# 4. 필드 누락 (이메일 없음)
# ──────────────────────────────────────────
def test_login_missing_email():
    response = client.post(
        "/auth/login",
        json={"password": "test1234"}
    )
    assert response.status_code == 422  # FastAPI validation error


# ──────────────────────────────────────────
# 5. 이메일 형식 오류
# ──────────────────────────────────────────
def test_login_invalid_email_format():
    response = client.post(
        "/auth/login",
        json={"email": "not-an-email", "password": "test1234"}
    )
    assert response.status_code == 422
