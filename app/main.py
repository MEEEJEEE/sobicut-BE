from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.base import Base
from app.db.seed import seed_emotion_tags
from app.db.session import SessionLocal, engine
from app.routers import auth, budget, reports, emotions, notifications, satisfactions, transactions, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 개발 편의를 위한 테이블 생성 (운영은 Alembic 마이그레이션 사용)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_emotion_tags(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="소비컷 (Sobicut) API",
    description="감정 기반 소비 분석으로 충동 소비를 줄이는 대학생 맞춤형 스마트 가계부",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(emotions.router)
app.include_router(budget.router)
app.include_router(satisfactions.router)
app.include_router(notifications.router)
app.include_router(reports.router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "소비컷 API 서버 실행 중"}
