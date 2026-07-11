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
    impulse_score: int
