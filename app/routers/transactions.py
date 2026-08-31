from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import EmotionTag, Satisfaction, Transaction, TransactionEmotion, User
from app.schemas.auth import MessageResponse
from app.schemas.emotion import TagEmotionsRequest
from app.schemas.satisfaction import SatisfactionRecordOut
from app.schemas.transaction import (
    CardMessageParseRequest,
    CardMessageParseResponse,
    TransactionCreate,
    TransactionCreateResponse,
    TransactionDetailOut,
    TransactionOut,
)
from app.services import level as level_service
from app.services import notification as notification_service
from app.services.card_parser import CardParseError, CardParser
from app.services.category_matcher import guess_category
from app.services.impulse import transaction_impulse_score
from app.services.satisfaction import DAY_TYPES

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


@router.post("/parse", response_model=CardMessageParseResponse)
def parse_card_message(
    body: CardMessageParseRequest,
    user: User = Depends(get_current_user),
):
    try:
        result = CardParser().parse(body.message_text)
    except CardParseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    result["category"] = guess_category(result["merchant"])
    return result


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    year: int | None = Query(None),
    month: int | None = Query(None),
    week: int | None = Query(None, description="ISO 주차"),
    date: date_type | None = Query(None, description="YYYY-MM-DD 단건 조회"),
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
    if date:
        q = q.filter(Transaction.transaction_date == date)
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


@router.get("/{transaction_id}/satisfactions", response_model=list[SatisfactionRecordOut])
def get_transaction_satisfactions(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """거래 하나에 대해 시점별(1일/7일/30일)로 제출된 만족도 결과 비교 조회.

    day_type만으로는 프론트가 어느 시점 응답인지 구분하기 어려워서 만든 조회 전용 엔드포인트.
    (예: "7일 후 5점 -> 30일 후 3점" 같은 결과 페이지 비교 표시용)
    """
    _get_owned_transaction(db, user, transaction_id)  # 소유권 확인
    records = db.query(Satisfaction).filter(Satisfaction.transaction_id == transaction_id).all()
    order = {name: i for i, name in enumerate(DAY_TYPES)}
    records.sort(key=lambda s: order.get(s.day_type, 99))
    return records


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
    """거래에 구매 결정 심리특성 태그를 등록한다 (거래당 최대 4개, 중복 선택 불가).

    "계획 여부"(즉흥성/충분한숙고 중 1개) + "소비 특성"(스트레스/비교회피/장기적가치 중 최대 3개)를
    프론트가 emotion_tag_id로 매핑해서 그대로 보낸다. 매 호출은 "현재 선택 상태 전체"를
    의미하므로, 요청에 없는 기존 태그는 삭제하고 새로 추가된 태그만 insert한다(교체 방식).
    """
    tx = _get_owned_transaction(db, user, transaction_id)

    requested_ids = set(body.emotion_tag_ids)
    tags = db.query(EmotionTag).filter(EmotionTag.id.in_(requested_ids)).all()
    if len(tags) != len(requested_ids):
        raise HTTPException(status_code=404, detail="존재하지 않는 감정 태그가 포함되어 있습니다.")

    existing_ids = {te.emotion_tag_id for te in tx.transaction_emotions}

    for te in list(tx.transaction_emotions):
        if te.emotion_tag_id not in requested_ids:
            db.delete(te)

    added = False
    for tag_id in requested_ids - existing_ids:
        db.add(TransactionEmotion(transaction_id=tx.id, emotion_tag_id=tag_id))
        added = True

    if added:
        level_service.add_exp(db, user, level_service.EXP_EMOTION_TAG)
    db.commit()
    return MessageResponse(message="감정 태그 등록 완료")
