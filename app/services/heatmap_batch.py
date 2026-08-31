"""히트맵 피크 요일/시간대 진입 알림 배치 (시간대 경계마다 실행: 06/11/14/19/23시).

이번 달 소비 패턴에서 가장 소비가 잦은 요일·시간대(heatmap_report의 peak)에
실제로 진입한 시점에 푸시 알림을 보낸다. 하루에 한 번만 걸리도록 당일
같은 type의 Notification이 이미 있으면 건너뛴다(멱등).
"""
import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.services import report as report_service
from app.services.common import DAY_NAMES, get_time_slot
from app.services.web_push import notify_active_subscribers

logger = logging.getLogger(__name__)

PUSH_NOTIFICATION_TYPE = "히트맵알림"


def process_heatmap_alerts(db: Session) -> int:
    """지금이 사용자의 이번 달 소비 피크 요일/시간대와 일치하면 알림 발송. 발송 건수 반환."""
    now = datetime.now()
    today_name = DAY_NAMES[now.weekday()]
    current_slot = get_time_slot(now.time())

    sent = 0
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    for user in users:
        report = report_service.heatmap_report(db, user.id, now.year, now.month)
        peak = report.get("peak")
        if not peak or peak["day"] != today_name or peak["time_slot"] != current_slot:
            continue

        notif_type = "heatmap_day" if peak["day"] in {"월", "금", "토", "일"} else "heatmap_time"
        already_sent = (
            db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.type == notif_type,
                func.date(Notification.created_at) == now.date(),
            )
            .first()
        )
        if already_sent:
            continue

        title = peak["notification_label"]
        message = f"{peak['day']}요일 {peak['time_slot']} 시간대는 평소 소비가 가장 잦은 때예요. 잠깐 멈춰볼까요?"
        db.add(Notification(user_id=user.id, type=notif_type, title=title, message=message))
        notify_active_subscribers(db, user.id, PUSH_NOTIFICATION_TYPE, title, message)
        sent += 1

    db.commit()
    logger.info("히트맵 알림 배치 완료: %d건 발송", sent)
    return sent
