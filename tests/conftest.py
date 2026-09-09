import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_emotion_tags
from app.db.session import get_db
from app.main import app

# 테스트용 인메모리 SQLite
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_emotion_tags(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _no_llm_calls(monkeypatch):
    """테스트 중 실제 Gemini 호출을 전면 차단한다.

    category_matcher.resolve_category() 가 참조하는 심볼
    (category_matcher 모듈에 bound 된 이름)을 패치한다 — category_llm 쪽이 아니다.
    LLM 반환값이 필요한 테스트는 각자 monkeypatch 로 다시 덮어쓰면 된다.
    """
    monkeypatch.setattr("app.services.category_matcher.classify_category", lambda name: None)


@pytest.fixture
def client():
    return TestClient(app)


SIGNUP_BODY = {
    "email": "test@sookmyung.ac.kr",
    "password": "test1234",
    "nickname": "미지",
    "residence_type": "자취",
    "income_level": "30-60",
}


@pytest.fixture
def auth_headers(client):
    """회원가입 + 로그인 후 인증 헤더 반환"""
    client.post("/auth/signup", json=SIGNUP_BODY)
    res = client.post(
        "/auth/login",
        json={"email": SIGNUP_BODY["email"], "password": SIGNUP_BODY["password"]},
    )
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
