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
    emotion_tags: list[EmotionTagOut]
    created_at: datetime


class TransactionDetailOut(TransactionOut):
    impulse_score: int = 0


class CardMessageParseRequest(BaseModel):
    message_text: str = Field(min_length=1)


class CardMessageParseResponse(BaseModel):
    amount: int
    merchant: str
    transaction_date: date
    transaction_time: str  # "HH:MM" (초 단위 없이 스펙 형식 그대로 유지)
    card_company: str
    category: str | None = None  # 규칙 기반 자동 매칭. 실패 시 null -> 프론트에서 수동 선택 유도
