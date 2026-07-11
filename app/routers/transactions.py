from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import EmotionTag, Transaction, TransactionEmotion, User
from app.schemas.auth import MessageResponse
from app.schemas.emotion import TagEmotionsRequest
from app.schemas.transaction import (
    TransactionCreate,
    TransactionCreateResponse,
    TransactionDetailOut,
    TransactionOut,
)
from app.services import level as level_service
from app.services import notification as notification_service
from app.services.impulse import transaction_impulse_score

router = APIRouter(prefix="/transactions", tags=["Transactions"])

TRANSACTION_TYPES = {"income", "expense"}
CATEGORIES = {"식비", "고정지출", "교통", "생활", "쇼핑/패션", "자기계발", "문화/여가", "모임/기타"}


def _get_owned_transaction(db: Session, user: User, transaction_id: int) -> Transaction:
    tx = (
        db.query(Transaction)
        .options(joinedload(Transaction.transaction_emotions).joinedload(TransactionEmotion.emotion_tag))
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .first()
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다.")
    return tx


def _validate_body(body: TransactionCreate) -> None:
    if body.type not in TRANSACTION_TYPES:
        raise HTTPException(status_code=422, detail="type은 income 또는 expense여야 합니다.")
    if body.type == "expense" and body.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail=f"카테고리는 {sorted(CATEGORIES)} 중 하나여야 합니다.")


@router.post("", response_model=TransactionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    body: TransactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_body(body)
    tx = Transaction(user_id=user.id, **body.model_dump())
    db.add(tx)
    db.flush()

    notification_service.check_after_transaction(db, user, tx)
    level_service.add_exp(db, user, level_service.EXP_TRANSACTION)
    db.commit()
    return TransactionCreateResponse(id=tx.id)


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    year: int | None = Query(None),
    month: int | None = Query(None),
    week: int | None = Query(None, description="ISO 주차"),
    type: str | None = Query(None),
    category: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Transaction)
        .options(joinedload(Transaction.transaction_emotions).joinedload(TransactionEmotion.emotion_tag))
        .filter(Transaction.user_id == user.id)
    )
    if year:
        q = q.filter(extract("year", Transaction.transaction_date) == year)
    if month:
        q = q.filter(extract("month", Transaction.transaction_date) == month)
    if type:
        q = q.filter(Transaction.type == type)
    if category:
        q = q.filter(Transaction.category == category)

    rows = q.order_by(Transaction.transaction_date.desc(), Transaction.transaction_time.desc()).all()

    if week:
        rows = [t for t in rows if t.transaction_date.isocalendar()[1] == week]
    return rows


@router.get("/{transaction_id}", response_model=TransactionDetailOut)
def get_transaction(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tx = _get_owned_transaction(db, user, transaction_id)
    detail = TransactionDetailOut.model_validate(tx, from_attributes=True)
    detail.impulse_score = transaction_impulse_score(db, tx, user)
    return detail


@router.put("/{transaction_id}", response_model=MessageResponse)
def update_transaction(
    transaction_id: int,
    body: TransactionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_body(body)
    tx = _get_owned_transaction(db, user, transaction_id)
    for key, value in body.model_dump().items():
        setattr(tx, key, value)
    db.commit()
    return MessageResponse(message="수정 완료")


@router.delete("/{transaction_id}", response_model=MessageResponse)
def delete_transaction(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tx = _get_owned_transaction(db, user, transaction_id)
    db.delete(tx)
    db.commit()
    return MessageResponse(message="삭제 완료")


@router.post("/{transaction_id}/emotions", response_model=MessageResponse)
def tag_emotions(
    transaction_id: int,
    body: TagEmotionsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tx = _get_owned_transaction(db, user, transaction_id)

    tags = db.query(EmotionTag).filter(EmotionTag.id.in_(body.emotion_tag_ids)).all()
    if len(tags) != len(set(body.emotion_tag_ids)):
        raise HTTPException(status_code=404, detail="존재하지 않는 감정 태그가 포함되어 있습니다.")

    existing = {te.emotion_tag_id for te in tx.transaction_emotions}
    added = False
    for tag in tags:
        if tag.id not in existing:
            db.add(TransactionEmotion(transaction_id=tx.id, emotion_tag_id=tag.id))
            added = True

    if added:
        level_service.add_exp(db, user, level_service.EXP_EMOTION_TAG)
    db.commit()
    return MessageResponse(message="감정 태그 등록 완료")
