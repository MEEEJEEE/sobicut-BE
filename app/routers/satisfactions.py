from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Satisfaction, Transaction, User
from app.schemas.satisfaction import (
    PendingSatisfactionOut,
    SatisfactionCreate,
    SatisfactionCreateResponse,
    SatisfactionRecordOut,
    TransactionSatisfactionsOut,
)
from app.services import level as level_service
from app.services.satisfaction import DAY_TYPES, due_satisfaction_targets

router = APIRouter(prefix="/satisfactions", tags=["Satisfaction"])
_DAY_TYPE_ORDER = {name: i for i, name in enumerate(DAY_TYPES)}


@router.post("", response_model=SatisfactionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_satisfaction(
    body: SatisfactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.day_type not in DAY_TYPES:
        raise HTTPException(status_code=422, detail="day_type은 '1일', '7일', '30일' 중 하나여야 합니다.")

    tx = (
        db.query(Transaction)
        .filter(Transaction.id == body.transaction_id, Transaction.user_id == user.id)
        .first()
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다.")

    duplicate = (
        db.query(Satisfaction)
        .filter(
            Satisfaction.transaction_id == body.transaction_id,
            Satisfaction.day_type == body.day_type,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="이미 해당 시점의 만족도를 입력했습니다.")

    record = Satisfaction(
        transaction_id=body.transaction_id,
        day_type=body.day_type,
        score=body.score,
    )
    db.add(record)
    level_service.add_exp(db, user, level_service.EXP_SATISFACTION)
    db.commit()
    db.refresh(record)
    return SatisfactionCreateResponse(
        id=record.id, transaction_id=record.transaction_id, day_type=record.day_type, message="만족도 등록 완료"
    )


@router.get("", response_model=list[TransactionSatisfactionsOut])
def list_satisfactions(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """이번 달(또는 지정 월)에 제출된 만족도 결과를 거래 단위로 묶어서 일괄 조회.

    거래마다 GET /transactions/{id}/satisfactions를 반복 호출하지 않도록,
    결과 페이지에서 한 번에 쓰는 목록 API. year/month는 만족도 제출 시각(submitted_at)
    기준으로 필터링한다 (거래일 기준 아님 — "이번 달에 받은 응답").
    """
    today = date.today()
    year = year or today.year
    month = month or today.month

    records = (
        db.query(Satisfaction)
        .join(Transaction, Transaction.id == Satisfaction.transaction_id)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Satisfaction.submitted_at) == year,
            extract("month", Satisfaction.submitted_at) == month,
        )
        .all()
    )

    by_tx: dict[int, list[Satisfaction]] = {}
    for r in records:
        by_tx.setdefault(r.transaction_id, []).append(r)

    result = []
    for tx_id, sats in by_tx.items():
        sats.sort(key=lambda s: _DAY_TYPE_ORDER.get(s.day_type, 99))
        tx = sats[0].transaction
        result.append(
            TransactionSatisfactionsOut(
                transaction_id=tx_id,
                merchant=tx.merchant,
                amount=tx.amount,
                category=tx.category,
                transaction_date=tx.transaction_date,
                satisfactions=[SatisfactionRecordOut.model_validate(s, from_attributes=True) for s in sats],
            )
        )

    result.sort(key=lambda r: r.transaction_date, reverse=True)
    return result


@router.get("/pending", response_model=list[PendingSatisfactionOut])
def pending_satisfactions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """고가 소비(기준액 이상) 중 만족도 미입력 건 조회 (팝업 트리거용)"""
    return [
        PendingSatisfactionOut(
            transaction_id=tx.id,
            merchant=tx.merchant,
            amount=tx.amount,
            category=tx.category,
            day_type=day_type,
            due_date=due,
        )
        for tx, day_type, due in due_satisfaction_targets(db, user.id)
    ]
