"""만족도 조사 알림 배치 (매일 1회 실행).

고가 소비 후 1일/7일/30일이 정확히 오늘인 대상에게 인앱 알림 + 웹 푸시를 발송한다.
`satisfaction_notification_logs`로 중복 발송을 막는다(멱등).
"""
import logging

from sqlalchemy.orm import Session

from app.models import Notification, SatisfactionNotificationLog
from app.services.satisfaction import due_satisfaction_targets
from app.services.web_push import notify_active_subscribers

logger = logging.getLogger(__name__)

PUSH_NOTIFICATION_TYPE = "만족도조사알림"

_TITLES = {
    "1일": "어제 구매, 지금 기분이 어떠세요? 🙂",
    "7일": "7일 전 구매, 만족하셨나요? ✨",
    "30일": "한 달 전 구매, 후회하진 않으셨나요? 🤔",
}


def process_satisfaction_reminders(db: Session) -> int:
    """오늘 마감인 만족도 조사 대상에 알림을 발송한다. 발송 건수를 반환한다."""
    sent = 0
    for tx, day_type, _due in due_satisfaction_targets(db, due_today_only=True):
        already_sent = (
            db.query(SatisfactionNotificationLog)
            .filter(
                SatisfactionNotificationLog.transaction_id == tx.id,
                SatisfactionNotificationLog.day_type == day_type,
            )
            .first()
        )
        if already_sent:
            continue

        title = _TITLES[day_type]
        message = f"{tx.merchant or '해당 소비'} {tx.amount:,}원, 만족도를 알려주세요."

        db.add(
            Notification(
                user_id=tx.user_id, type="satisfaction_request", title=title, message=message, transaction_id=tx.id
            )
        )
        db.add(SatisfactionNotificationLog(transaction_id=tx.id, day_type=day_type))
        notify_active_subscribers(
            db, tx.user_id, PUSH_NOTIFICATION_TYPE, title, message,
            notification_type="satisfaction_request", transaction_id=tx.id,
        )
        sent += 1

    db.commit()
    logger.info("만족도 조사 알림 배치 완료: %d건 발송", sent)
    return sent
