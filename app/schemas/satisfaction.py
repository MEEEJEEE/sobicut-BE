from datetime import date

from pydantic import BaseModel, Field


class SatisfactionCreate(BaseModel):
    transaction_id: int
    day_type: str  # 7일 | 30일
    score: int = Field(ge=1, le=5)


class SatisfactionCreateResponse(BaseModel):
    id: int
    message: str


class PendingSatisfactionOut(BaseModel):
    transaction_id: int
    merchant: str | None
    amount: int
    day_type: str
    due_date: date
