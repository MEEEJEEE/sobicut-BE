from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Notification, PushSubscription, User
from app.schemas.auth import MessageResponse
from app.schemas.notification import (
    NotificationOut,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    VapidPublicKeyResponse,
)
from app.services.web_push import send_test_notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])

NOTIFICATION_SUBSCRIPTION_TYPES = {"소비컷알림", "만족도조사알림"}


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def get_vapid_public_key():
    """프론트가 pushManager.subscribe()의 applicationServerKey로 사용할 VAPID 공개키."""
    return VapidPublicKeyResponse(public_key=settings.VAPID_PUBLIC_KEY)


@router.post("/subscribe", response_model=MessageResponse)
def subscribe(
    body: PushSubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.notification_type not in NOTIFICATION_SUBSCRIPTION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"notification_type은 {sorted(NOTIFICATION_SUBSCRIPTION_TYPES)} 중 하나여야 합니다.",
        )

    existing = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.notification_type == body.notification_type,
        )
        .first()
    )
    if existing:
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.is_active = True
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
                notification_type=body.notification_type,
                is_active=True,
            )
        )
    db.commit()
    return MessageResponse(message="구독 등록 완료")


@router.post("/unsubscribe", response_model=MessageResponse)
def unsubscribe(
    body: PushUnsubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscription = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.notification_type == body.notification_type,
        )
        .first()
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="구독 정보를 찾을 수 없습니다.")
    subscription.is_active = False
    db.commit()
    return MessageResponse(message="구독 해제 완료")


@router.post("/test-push", response_model=MessageResponse)
def test_push(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    has_subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user.id, PushSubscription.is_active.is_(True))
        .first()
        is not None
    )
    if not has_subscription:
        raise HTTPException(status_code=404, detail="활성화된 웹 푸시 구독이 없습니다.")

    if not send_test_notification(db, user.id):
        raise HTTPException(status_code=502, detail="푸시 발송에 실패했습니다.")
    return MessageResponse(message="테스트 알림을 발송했습니다.")


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    type: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if type:
        q = q.filter(Notification.type == type)
    return q.order_by(Notification.created_at.desc()).all()


@router.put("/read-all", response_model=MessageResponse)
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()
    return MessageResponse(message="전체 읽음 처리 완료")


@router.put("/{notification_id}", response_model=MessageResponse)
def read_one(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    notification.is_read = True
    db.commit()
    return MessageResponse(message="읽음 처리 완료")
