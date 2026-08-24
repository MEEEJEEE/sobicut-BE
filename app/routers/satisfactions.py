from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Satisfaction, Transaction, User
from app.schemas.satisfaction import (
    PendingSatisfactionOut,
    SatisfactionCreate,
    SatisfactionCreateResponse,
)
from app.services import level as level_service
from app.services.satisfaction import DAY_TYPES, due_satisfaction_targets

router = APIRouter(prefix="/satisfactions", tags=["Satisfaction"])


@router.post("", response_model=SatisfactionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_satisfaction(
    body: SatisfactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.day_type not in DAY_TYPES:
        raise HTTPException(status_code=422, detail="day_type은 '7일' 또는 '30일'이어야 합니다.")

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
    return SatisfactionCreateResponse(id=record.id, message="만족도 등록 완료")


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
            day_type=day_type,
            due_date=due,
        )
        for tx, day_type, due in due_satisfaction_targets(db, user.id)
    ]
