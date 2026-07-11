from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Notification, User
from app.schemas.auth import MessageResponse
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


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
