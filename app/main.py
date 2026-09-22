from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.scheduler import init_scheduler, shutdown_scheduler
from app.db.base import Base
from app.db.seed import seed_emotion_tags
from app.db.session import SessionLocal, engine
from app.routers import auth, budget, demo, reports, emotions, notifications, satisfactions, transactions, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 개발 편의를 위한 테이블 생성 (운영은 Alembic 마이그레이션 사용)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_emotion_tags(db)
    finally:
        db.close()

    init_scheduler()
    yield
    shutdown_scheduler()


class UTF8JSONResponse(JSONResponse):
    """Content-Type에 charset=utf-8을 명시해, 응답 헤더만 보고 인코딩을
    잘못 추측하는 일부 브라우저/뷰어에서 한글이 깨져 보이는 문제를 방지한다."""

    media_type = "application/json; charset=utf-8"


app = FastAPI(
    title="소비컷 (Sobicut) API",
    description="감정 기반 소비 분석으로 충동 소비를 줄이는 대학생 맞춤형 스마트 가계부",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(emotions.router)
app.include_router(budget.router)
app.include_router(satisfactions.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(demo.router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "소비컷 API 서버 실행 중"}
