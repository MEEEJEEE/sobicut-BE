"""가계부 기록 도우미 알림 배치 (매일 22:00 실행).

오늘 등록된 거래(수입/지출 무관)가 하나도 없는 사용자에게 기록을 독려하는
알림을 보낸다. 당일 이미 발송했으면 건너뛴다(멱등).
"""
import logging
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Notification, Transaction, User
from app.services.web_push import notify_active_subscribers

logger = logging.getLogger(__name__)

PUSH_NOTIFICATION_TYPE = "가계부기록도우미"
NOTIFICATION_TYPE = "no_transaction_reminder"


def process_no_transaction_reminders(db: Session) -> int:
    """오늘 거래 기록이 없는 사용자에게 알림을 보낸다. 발송 건수를 반환한다."""
    today = date.today()
    sent = 0
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    for user in users:
        has_tx_today = (
            db.query(Transaction)
            .filter(Transaction.user_id == user.id, Transaction.transaction_date == today)
            .first()
            is not None
        )
        if has_tx_today:
            continue

        already_sent = (
            db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.type == NOTIFICATION_TYPE,
                func.date(Notification.created_at) == today,
            )
            .first()
        )
        if already_sent:
            continue

        title = "오늘의 소비, 아직 기록하지 않았어요"
        message = "지금 한 번 기록해 볼까요?"
        db.add(Notification(user_id=user.id, type=NOTIFICATION_TYPE, title=title, message=message))
        notify_active_subscribers(db, user.id, PUSH_NOTIFICATION_TYPE, title, message)
        sent += 1

    db.commit()
    logger.info("가계부 기록 도우미 배치 완료: %d건 발송", sent)
    return sent
