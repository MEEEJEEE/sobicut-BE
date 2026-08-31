from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SatisfactionCreate(BaseModel):
    transaction_id: int
    day_type: str  # 1일 | 7일 | 30일
    score: int = Field(ge=1, le=5)


class SatisfactionCreateResponse(BaseModel):
    id: int
    transaction_id: int
    day_type: str
    message: str


class PendingSatisfactionOut(BaseModel):
    transaction_id: int
    merchant: str | None
    amount: int
    category: str
    day_type: str
    due_date: date


class SatisfactionRecordOut(BaseModel):
    """거래 하나에 대한 시점별 만족도 결과 (결과 페이지 비교 표시용)"""

    model_config = ConfigDict(from_attributes=True)

    day_type: str
    score: int
    submitted_at: datetime


class TransactionSatisfactionsOut(BaseModel):
    """거래 하나 + 그 거래에 제출된 만족도 목록 (월별 결과 페이지 일괄 조회용)"""

    transaction_id: int
    merchant: str | None
    amount: int
    category: str
    transaction_date: date
    satisfactions: list[SatisfactionRecordOut]
