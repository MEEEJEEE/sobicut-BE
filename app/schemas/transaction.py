from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreate(BaseModel):
    amount: int = Field(gt=0)
    type: str  # income | expense
    category: str
    merchant: str | None = None
    description: str | None = None
    transaction_date: date
    transaction_time: time
    subjective_burden: int | None = Field(None, ge=1, le=5)  # 체감 경제적 부담(충동 점수 β2용)


class TransactionCreateResponse(BaseModel):
    id: int


class EmotionTagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    type: str
    category: str
    merchant: str | None
    description: str | None
    transaction_date: date
    transaction_time: time
    subjective_burden: int | None = None
    emotion_tags: list[EmotionTagOut]
    tags: list[str]  # 자유 텍스트 소비 태그 (기록용, 감정 태그와 별개, 충동 점수 미반영)
    created_at: datetime


class SetTagsRequest(BaseModel):
    tags: list[str]


class TransactionDetailOut(TransactionOut):
    impulse_score: int = 0
    risk_level: str = "낮음"  # "낮음" | "주의" | "경고" (충동 점수 구간)


class CardMessageParseRequest(BaseModel):
    message_text: str = Field(min_length=1)


class CardMessageParseResponse(BaseModel):
    amount: int
    merchant: str
    transaction_date: date
    transaction_time: str  # "HH:MM" (초 단위 없이 스펙 형식 그대로 유지)
    card_company: str
    category: str | None = None  # 규칙 기반 자동 매칭. 실패 시 null -> 프론트에서 수동 선택 유도
